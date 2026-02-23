"""API HTTP — Point d'entree pour triggers externes (montre, webhook, etc.).

Endpoints :
    POST /api/command  → reponse texte JSON
    POST /api/speak    → reponse texte + audio WAV (pour Samsung Watch, etc.)
    POST /api/wake     → simule le wake word
    GET  /api/status   → etat du pipeline
    GET  /api/tools    → liste les outils disponibles
"""

import asyncio
import io
import json
import logging
import struct
import threading
import urllib.parse

import numpy as np
from aiohttp import web

log = logging.getLogger(__name__)


class AethonAPIServer:
    """Serveur API REST pour controler Aethon a distance.

    Endpoints :
        POST /api/command  {"text": "..."} → reponse texte JSON
        POST /api/speak    {"text": "..."} → reponse texte + audio WAV
        POST /api/wake     → active Aethon (simule le wake word)
        GET  /api/status   → etat du pipeline
        GET  /api/tools    → liste les outils disponibles
    """

    def __init__(self, pipeline, port: int = 8741):
        self._pipeline = pipeline
        self._port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._runner: web.AppRunner | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """Démarre le serveur dans un thread séparé."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="api-server")
        self._thread.start()

    def _run(self):
        """Thread principal du serveur."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._start_server())
            log.info("API Aethon démarrée sur http://127.0.0.1:%d", self._port)
            self._loop.run_forever()
        except Exception as e:
            log.error("Erreur serveur API: %s", e)
        finally:
            self._loop.close()

    async def _start_server(self):
        """Configure et lance le serveur aiohttp."""
        app = web.Application(client_max_size=64 * 1024)  # 64 KB max body
        app.router.add_post("/api/command", self._handle_command)
        app.router.add_post("/api/speak", self._handle_speak)
        app.router.add_post("/api/wake", self._handle_wake)
        app.router.add_get("/api/status", self._handle_status)
        app.router.add_get("/api/tools", self._handle_tools)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self._port)
        await site.start()

    async def _handle_command(self, request: web.Request) -> web.Response:
        """POST /api/command {"text": "quelle heure est-il"}

        Génère une réponse LLM et la retourne en texte JSON.
        Note : la réponse n'est PAS lue à voix haute (texte uniquement).
        Si le pipeline est occupé (THINKING/SPEAKING), retourne 409 Conflict.
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "JSON invalide"}, status=400
            )

        text = data.get("text", "").strip()
        if not text:
            return web.json_response(
                {"error": "Champ 'text' manquant ou vide"}, status=400
            )

        log.info("API command: '%s'", text)

        # Exécuter dans un thread pour ne pas bloquer l'event loop
        try:
            response = await asyncio.get_running_loop().run_in_executor(
                None, self._execute_command, text
            )
            if response is None:
                return web.json_response(
                    {"error": "Pipeline occupé, réessayez plus tard"}, status=409
                )
            return web.json_response({"response": response, "status": "ok"})
        except Exception as e:
            log.error("Erreur API command: %s", e)
            return web.json_response(
                {"error": str(e)}, status=500
            )

    def _execute_command(self, text: str) -> str | None:
        """Exécute une commande textuelle via le LLM (synchrone).

        Retourne None si le LLM est occupé (lock non acquis).
        Utilise le lock partagé du pipeline pour éviter les accès concurrents.
        """
        # Utiliser le lock partagé du pipeline (C1: évite la race avec _respond_streaming)
        acquired = self._pipeline._llm_lock.acquire(timeout=1.0)
        if not acquired:
            log.warning("API command ignorée: LLM occupé (lock timeout)")
            return None

        try:
            self._pipeline.llm.add_user_message(text)
            sentences = []
            for sentence in self._pipeline.llm.generate_stream():
                sentences.append(sentence)
            response = " ".join(sentences)

            # Sauvegarder en mémoire si activé
            if self._pipeline.config.memory.enabled:
                self._pipeline.memory.process_user_message(
                    text, self._pipeline._session_id
                )
                self._pipeline.memory.process_assistant_message(
                    response, self._pipeline._session_id
                )

            return response
        finally:
            self._pipeline._llm_lock.release()

    async def _handle_speak(self, request: web.Request) -> web.Response:
        """POST /api/speak {"text": "bonjour aethon"}

        Genere une reponse LLM, synthetise le TTS, et retourne :
        - Header X-Response-Text : texte de la reponse
        - Body : audio WAV 24kHz mono 16-bit PCM

        Ideal pour les clients legers (montre, webhook) qui veulent
        la reponse vocale directement.
        """
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "JSON invalide"}, status=400)

        text = data.get("text", "").strip()
        if not text:
            return web.json_response(
                {"error": "Champ 'text' manquant ou vide"}, status=400
            )

        log.info("API speak: '%s'", text)

        try:
            try:
                result = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        None, self._execute_speak, text
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                return web.json_response(
                    {"error": "Timeout generation TTS"}, status=504
                )
            if result is None:
                return web.json_response(
                    {"error": "Pipeline occupe, reessayez plus tard"}, status=409
                )

            response_text, wav_bytes = result
            headers = {
                "X-Response-Text": urllib.parse.quote(response_text, safe=""),
                "X-Response-Text-Encoding": "url",
            }
            return web.Response(
                body=wav_bytes,
                content_type="audio/wav",
                headers=headers,
            )
        except Exception as e:
            log.error("Erreur API speak: %s", e)
            return web.json_response({"error": str(e)}, status=500)

    def _execute_speak(self, text: str) -> tuple[str, bytes] | None:
        """Genere reponse LLM + audio TTS (synchrone).

        Retourne (response_text, wav_bytes) ou None si LLM occupe.
        """
        acquired = self._pipeline._llm_lock.acquire(timeout=1.0)
        if not acquired:
            log.warning("API speak ignoree: LLM occupe (lock timeout)")
            return None

        try:
            from aethon.tts.emotion import parse_emotion_tags, strip_emotion_tags
            from aethon.tts.text_prep import prepare_for_tts

            self._pipeline.llm.add_user_message(text)

            # Collecter la reponse LLM
            sentences = []
            for sentence in self._pipeline.llm.generate_stream():
                sentences.append(sentence)
            response = " ".join(strip_emotion_tags(s) for s in sentences)

            # Synthetiser le TTS avec pipeline d'emotion
            audio_chunks = []
            for sentence in sentences:
                for seg in parse_emotion_tags(sentence):
                    prepared = prepare_for_tts(seg.text)
                    if not prepared:
                        continue
                    for chunk in self._pipeline.tts.synthesize_stream(
                        prepared, emotion_params=seg.preset,
                    ):
                        audio_chunks.append(chunk)

            # Sauvegarder en memoire
            if self._pipeline.config.memory.enabled:
                self._pipeline.memory.process_user_message(
                    text, self._pipeline._session_id
                )
                self._pipeline.memory.process_assistant_message(
                    response, self._pipeline._session_id
                )

            # Encoder en WAV
            if audio_chunks:
                audio = np.concatenate(audio_chunks)
                wav_bytes = self._encode_wav(audio, self._pipeline.tts.SAMPLE_RATE)
            else:
                wav_bytes = self._encode_wav(np.array([], dtype=np.float32), self._pipeline.tts.SAMPLE_RATE)

            return response, wav_bytes
        finally:
            self._pipeline._llm_lock.release()

    @staticmethod
    def _encode_wav(audio: np.ndarray, sample_rate: int) -> bytes:
        """Encode un array float32 en WAV PCM 16-bit mono."""
        if audio.dtype == np.float32:
            audio_i16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        else:
            audio_i16 = audio.astype(np.int16)

        buf = io.BytesIO()
        num_samples = len(audio_i16)
        data_size = num_samples * 2  # 16-bit = 2 bytes per sample
        # RIFF header
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        # fmt chunk
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))  # chunk size
        buf.write(struct.pack("<H", 1))   # PCM format
        buf.write(struct.pack("<H", 1))   # mono
        buf.write(struct.pack("<I", sample_rate))
        buf.write(struct.pack("<I", sample_rate * 2))  # byte rate
        buf.write(struct.pack("<H", 2))   # block align
        buf.write(struct.pack("<H", 16))  # bits per sample
        # data chunk
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(audio_i16.tobytes())
        return buf.getvalue()

    async def _handle_wake(self, request: web.Request) -> web.Response:
        """POST /api/wake — Active Aethon (simule un wake word).

        Si le wake word est désactivé, Aethon est déjà actif en permanence.
        """
        if not self._pipeline.config.persona.wake_enabled:
            return web.json_response({
                "status": "already_active",
                "message": "Wake word désactivé, Aethon écoute en permanence.",
            })

        was_active = self._pipeline._active.is_set()
        self._pipeline._active.set()

        if was_active:
            log.info("API wake: Aethon était déjà actif.")
            return web.json_response({"status": "already_active"})

        log.info("API wake: Aethon activé à distance.")
        # Émettre le changement d'état si un callback est configuré
        if self._pipeline.on_state_change:
            self._pipeline.on_state_change("idle")

        return web.json_response({"status": "active"})

    async def _handle_status(self, request: web.Request) -> web.Response:
        """GET /api/status — État actuel du pipeline."""
        status = {
            "running": self._pipeline._running,
            "active": self._pipeline._active.is_set(),
            "session": self._pipeline._session_id,
            "llm_backend": self._pipeline.config.llm.backend,
            "tts_backend": self._pipeline.config.tts.backend,
            "wake_enabled": self._pipeline.config.persona.wake_enabled,
            "memory_enabled": self._pipeline.config.memory.enabled,
        }

        # Ajouter les outils si disponibles
        if self._pipeline._tool_registry:
            status["tools"] = [
                t.name for t in self._pipeline._tool_registry.list_tools()
            ]

        return web.json_response(status)

    async def _handle_tools(self, request: web.Request) -> web.Response:
        """GET /api/tools — Liste les outils disponibles."""
        tools = []
        if self._pipeline._tool_registry:
            for t in self._pipeline._tool_registry.list_tools():
                tools.append({
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                })
        return web.json_response({"tools": tools})

    def stop(self):
        """Arrête le serveur proprement."""
        if self._loop and self._runner:
            # Planifier le cleanup dans l'event loop du serveur
            future = asyncio.run_coroutine_threadsafe(
                self._runner.cleanup(), self._loop
            )
            try:
                future.result(timeout=5)
            except Exception:
                pass

            self._loop.call_soon_threadsafe(self._loop.stop)
            log.info("API Aethon arrêtée.")

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
