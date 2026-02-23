"""Pipeline Aethon — Orchestre STT → LLM → TTS avec barge-in et wake word."""

import logging
import queue
import re
import threading
import time
import uuid
from collections.abc import Callable

import numpy as np

from aethon.config import AethonConfig
from aethon.audio.manager import AudioManager
from aethon.stt.transcriber import Transcriber
from aethon.memory.store import MemoryStore
from aethon.tts.emotion import parse_emotion_tags, strip_emotion_tags
from aethon.tts.text_prep import prepare_for_tts

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factories — instanciation des backends LLM et TTS selon la config
# ---------------------------------------------------------------------------

def _create_llm(config: AethonConfig):
    """Factory : crée le backend LLM selon la config."""
    if config.llm.backend == "gemini":
        from aethon.llm.gemini import GeminiLLM
        return GeminiLLM(config.llm)
    else:
        from aethon.llm.ollama import OllamaLLM
        return OllamaLLM(config.llm)


def _create_tts(config: AethonConfig):
    """Factory : crée le backend TTS selon la config."""
    if config.tts.backend == "chatterbox":
        from aethon.tts.chatterbox import ChatterboxSynthesizer
        return ChatterboxSynthesizer(config)
    else:
        from aethon.tts.kokoro import KokoroSynthesizer
        return KokoroSynthesizer(config.tts)


def _create_wake_detector(config: AethonConfig):
    """Factory : crée le détecteur de wake word selon le mode configuré."""
    if config.persona.wake_mode == "whisper":
        from aethon.wakeword.whisper_detector import WhisperWakeDetector
        return WhisperWakeDetector(config)
    else:
        from aethon.wakeword.detector import WakeWordDetector
        return WakeWordDetector(config)


def _clean_for_tts(text: str) -> str:
    """Nettoie le texte avant synthese TTS — delegue a text_prep.prepare_for_tts."""
    return prepare_for_tts(text)


class AethonPipeline:
    """Pipeline vocal complet avec gestion des interruptions."""

    def __init__(self, config: AethonConfig):
        self.config = config
        self.audio = AudioManager(config.audio)
        self.stt = Transcriber(config.stt)
        self.tts = _create_tts(config)
        self.llm = _create_llm(config)
        self.memory = MemoryStore(config.memory)
        self.wake_word = _create_wake_detector(config)

        self._running = False
        self._stop_event = threading.Event()  # Signale l'arrêt demandé (thread-safe)
        self._active = threading.Event()  # Set après wake word ou si wake word désactivé
        self._session_id = ""
        self._vad_model = None
        self._barge_in_detected = threading.Event()
        self._barge_in_audio: list[np.ndarray] = []
        self._barge_in_lock = threading.Lock()  # Protège _barge_in_audio (cross-thread)
        self._response_done = threading.Event()  # Signale la fin de la réponse au monitor
        self._vad_lock = threading.Lock()  # Protège l'inférence VAD (thread pipeline + barge-in)
        self._llm_lock = threading.Lock()  # Protège l'accès concurrent au LLM (pipeline + API)
        self._text_queue: queue.Queue[str] = queue.Queue()  # Texte injecté depuis la GUI (bypass STT)
        self._tool_registry = None  # ToolRegistry (Phase 3)
        self._api_server = None     # AethonAPIServer (Phase 3)

        # Callbacks pour la GUI (appelés depuis le thread pipeline)
        self.on_state_change: Callable[[str], None] | None = None
        self.on_transcript: Callable[[str], None] | None = None
        self.on_response: Callable[[str], None] | None = None
        self.on_audio_level: Callable[[float], None] | None = None

    def _emit_state(self, state: str):
        if self.on_state_change:
            self.on_state_change(state)

    def _emit_audio_level(self, chunk: np.ndarray):
        """Compute RMS of audio chunk and emit as normalized 0..1 level."""
        if self.on_audio_level is None:
            return
        audio = chunk.astype(np.float32)
        if chunk.dtype == np.int16:
            audio /= 32768.0
        rms = float(np.sqrt(np.mean(audio ** 2)))
        level = min(rms / 0.1, 1.0)
        self.on_audio_level(level)

    def load_all(self):
        """Charge tous les modèles."""
        self._emit_state("loading")
        log.info("=== Chargement des modèles ===")

        # Vérifier le backend LLM
        if not self.llm.check_connection():
            backend = self.config.llm.backend
            if backend == "ollama":
                log.error(
                    "Ollama non accessible sur %s. "
                    "Lance 'ollama serve' et 'ollama pull %s'.",
                    self.config.llm.base_url,
                    self.config.llm.ollama_model,
                )
            else:
                log.error("Backend LLM '%s' non accessible.", backend)
            raise ConnectionError(f"Backend LLM ({backend}) non accessible")
        log.info("Backend LLM connecté (%s)", self.config.llm.backend)

        # Charger les modèles GPU
        # IMPORTANT : TTS (PyTorch/cuDNN) AVANT STT (CTranslate2/cuDNN).
        # Si CTranslate2 initialise cuDNN en premier, PyTorch ne trouve plus
        # le symbole cudnnGetLibConfig → crash exit 127.
        self.tts.load()
        self.stt.load()

        # Charger Silero VAD
        self._load_vad()

        # Charger wake word
        if self.config.persona.wake_enabled:
            self.wake_word.load()
            # Injecter les modèles partagés pour le mode Whisper
            if hasattr(self.wake_word, "set_shared_models"):
                self.wake_word.set_shared_models(self.stt, self._vad_model)

        # Charger mémoire
        if self.config.memory.enabled:
            self.memory.load()

        # Initialiser contexte LLM
        memories = self.memory.get_recent_memories() if self.config.memory.enabled else []
        system_prompt = (
            self.config.llm.system_prompt_override
            if self.config.llm.system_prompt_override
            else self.config.persona.build_system_prompt()
        )
        self.llm.set_context(system_prompt, memories)

        # Charger les outils (function calling, Gemini uniquement)
        self._load_tools()

        # Démarrer le serveur API si activé
        if self.config.tools.enable_api_server:
            self._start_api_server()

        self._session_id = uuid.uuid4().hex[:8]
        log.info("=== Tous les modèles chargés. Session: %s ===", self._session_id)

    def _start_api_server(self):
        """Démarre le serveur API HTTP dans un thread séparé."""
        from aethon.api.server import AethonAPIServer
        port = self.config.tools.api_port
        self._api_server = AethonAPIServer(self, port=port)
        self._api_server.start()

    def _load_tools(self):
        """Charge et enregistre les outils disponibles (function calling)."""
        if not getattr(self.config.llm, "enable_tools", False):
            return
        if self.config.llm.backend != "gemini":
            log.info("Tools désactivés (backend %s ne supporte pas le function calling).",
                     self.config.llm.backend)
            return

        from aethon.tools.registry import ToolRegistry

        self._tool_registry = ToolRegistry()

        if self.config.tools.enable_datetime:
            from aethon.tools.datetime_tool import DateTimeTool
            self._tool_registry.register(DateTimeTool())

        if self.config.tools.enable_system_info:
            from aethon.tools.system_tool import SystemInfoTool
            self._tool_registry.register(SystemInfoTool())

        # Configurer le function calling dans le LLM
        self.llm.set_tools(
            declarations=self._tool_registry.to_gemini_declarations(),
            executor=lambda name, args: self._tool_registry.execute(name, args),
        )
        tool_names = [t.name for t in self._tool_registry.list_tools()]
        log.info("Tools chargés : %s", ", ".join(tool_names))

    def _load_vad(self):
        """Charge le modèle Silero VAD."""
        import torch
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )
        self._vad_model = model
        log.info("Silero VAD chargé.")

    def _is_speech(self, audio_chunk: np.ndarray, threshold: float = 0.5) -> bool:
        """Détecte la parole dans un chunk audio via Silero VAD.

        Args:
            audio_chunk: Audio int16 ou float32.
            threshold: Seuil de confiance VAD (0.0-1.0). Plus élevé = moins
                       de faux positifs. Défaut 0.5 pour la détection normale,
                       utiliser 0.65+ pour le barge-in (filtre l'écho speaker).
        """
        import torch
        if self._vad_model is None:
            return True

        try:
            # Silero attend du float32 normalisé, 16kHz
            if audio_chunk.dtype == np.int16:
                audio_f32 = audio_chunk.astype(np.float32) / 32768.0
            else:
                audio_f32 = audio_chunk.astype(np.float32)

            tensor = torch.from_numpy(audio_f32)
            with self._vad_lock:
                confidence = self._vad_model(tensor, self.config.audio.sample_rate).item()
            return confidence > threshold
        except Exception as e:
            log.warning("Erreur VAD: %s", e)
            return True  # En cas d'erreur, considérer comme parole

    def run(self):
        """Boucle principale du pipeline."""
        self._running = True
        self.audio.start_capture()
        self._emit_state("idle")

        # Log des paramètres audio pour le debug
        acfg = self.config.audio
        log.info(
            "Audio: gain=%.1fx, AGC=%s (cible RMS=%.3f), device=%s",
            acfg.input_gain,
            "ON" if acfg.auto_gain else "OFF",
            acfg.auto_gain_target_rms,
            acfg.input_device or "défaut",
        )

        if not self.config.persona.wake_enabled:
            self._active.set()
            log.info("Wake word désactivé — %s écoute en permanence.", self.config.name)
        else:
            log.info(
                "Dis '%s' pour activer (mode=%s, seuil=%.2f)...",
                self.config.persona.wake_phrase,
                self.config.persona.wake_mode,
                self.config.persona.wake_threshold,
            )

        try:
            while self._running:
                # Vérifier les messages texte injectés (bypass STT)
                try:
                    injected_text = self._text_queue.get_nowait()
                    if injected_text and injected_text.strip():
                        self._handle_text_input(injected_text.strip())
                        self._emit_state("idle")
                        continue
                except queue.Empty:
                    pass

                chunk = self.audio.get_audio_chunk(timeout=0.1)
                if chunk is None:
                    continue

                # Phase 1 : Wake word (si activé)
                if not self._active.is_set():
                    if self.wake_word.detect(chunk):
                        self._active.set()
                        self.wake_word.reset()
                        self._play_activation_sound()
                        log.info("%s activé! Je t'écoute...", self.config.name)
                    continue

                # Phase 2 : Écoute et collecte de la parole
                speech_audio = self._collect_speech(chunk)
                if speech_audio is None:
                    continue

                # Phase 3 : Transcription
                self._emit_state("thinking")
                text = self.stt.transcribe(speech_audio, self.config.audio.sample_rate)
                if not text or len(text.strip()) < 2:
                    self._emit_state("idle")
                    continue

                log.info("Toi: %s", text)
                if self.on_transcript:
                    self.on_transcript(text)

                # Sauvegarder en mémoire
                if self.config.memory.enabled:
                    self.memory.process_user_message(text, self._session_id)

                # Phase 4 : Génération de réponse + TTS streaming
                with self._llm_lock:
                    self.llm.add_user_message(text)
                    self._respond_streaming()

                # Bug 3 : si un barge-in a capturé de l'audio, l'utiliser comme
                # début de la prochaine collecte de parole.
                with self._barge_in_lock:
                    barge_audio = list(self._barge_in_audio)
                    self._barge_in_audio.clear()
                if barge_audio:
                    continued_speech = self._collect_speech(initial_chunks=barge_audio)
                    if continued_speech is not None:
                        self._emit_state("thinking")
                        text2 = self.stt.transcribe(continued_speech, self.config.audio.sample_rate)
                        if text2 and len(text2.strip()) >= 2:
                            log.info("Toi (barge-in): %s", text2)
                            if self.on_transcript:
                                self.on_transcript(text2)
                            if self.config.memory.enabled:
                                self.memory.process_user_message(text2, self._session_id)
                            with self._llm_lock:
                                self.llm.add_user_message(text2)
                                self._respond_streaming()

                self._emit_state("idle")

        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur.")
        finally:
            self.stop()

    def _collect_speech(self, first_chunk: np.ndarray = None, initial_chunks: list[np.ndarray] = None) -> np.ndarray | None:
        """Collecte l'audio tant que l'utilisateur parle.

        Utilise Silero VAD pour détecter le début et la fin de parole.
        Retourne None si pas assez de parole détectée.

        Args:
            first_chunk: Premier chunk audio (détection VAD normale ou wake word).
            initial_chunks: Liste de chunks pré-capturés (barge-in). Prioritaire sur first_chunk.
        """
        if initial_chunks:
            # Mode continuation (barge-in) : démarre avec des chunks pré-existants
            self._emit_state("listening")
            chunks = list(initial_chunks)
            speech_ms = len(initial_chunks) * self.config.audio.chunk_duration_ms
            for c in initial_chunks:
                self._emit_audio_level(c)
        elif first_chunk is not None:
            # Mode normal : démarre avec un seul chunk détecté par VAD
            if not self._is_speech(first_chunk):
                return None
            self._emit_state("listening")
            self._emit_audio_level(first_chunk)
            chunks = [first_chunk]
            speech_ms = self.config.audio.chunk_duration_ms
        else:
            return None

        silence_ms = 0
        timeout_ms = self.config.audio.silence_timeout_ms
        min_speech = self.config.audio.min_speech_ms

        while self._running:
            chunk = self.audio.get_audio_chunk(timeout=0.15)
            if chunk is None:
                silence_ms += 150
                if silence_ms >= timeout_ms:
                    break
                continue

            chunks.append(chunk)
            self._emit_audio_level(chunk)

            if self._is_speech(chunk):
                silence_ms = 0
                speech_ms += self.config.audio.chunk_duration_ms
            else:
                silence_ms += self.config.audio.chunk_duration_ms
                if silence_ms >= timeout_ms:
                    break

        if speech_ms < min_speech:
            return None

        combined = np.concatenate(chunks)
        peak = int(np.max(np.abs(combined)))
        rms = float(np.sqrt(np.mean((combined.astype(np.float32) / 32768.0) ** 2)))
        log.debug(
            "Parole collectée: %.1fs, peak=%d/32768 (%.1f%%), RMS=%.4f",
            len(combined) / self.config.audio.sample_rate,
            peak,
            peak / 327.68,
            rms,
        )
        return combined

    def _respond_streaming(self):
        """G\u00e9n\u00e8re la r\u00e9ponse LLM en streaming et joue le TTS en pipeline parall\u00e8le.

        Architecture producteur-consommateur :
        - Thread principal : LLM streaming \u2192 yield phrases \u2192 tts_queue
        - Thread TTS : synth\u00e9tise chaque phrase \u2192 audio_queue
        - Thread Audio : joue les chunks audio au fur et \u00e0 mesure

        Cela permet de synth\u00e9tiser la phrase N+1 pendant que la phrase N est lue.
        """
        self._barge_in_detected.clear()
        self._response_done.clear()
        with self._barge_in_lock:
            self._barge_in_audio.clear()
        full_response = ""

        # Queues pour le pipeline parallele
        # tts_queue transporte des tuples (texte, emotion_preset_or_None) ou None (sentinel)
        _SENTINEL = None  # Marqueur de fin
        tts_queue: queue.Queue[tuple[str, object] | None] = queue.Queue(maxsize=8)
        audio_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=8)

        # Thread de surveillance du barge-in pendant la lecture
        barge_in_thread = threading.Thread(
            target=self._monitor_barge_in, daemon=True
        )
        barge_in_thread.start()

        def _tts_worker():
            """Thread TTS : consomme des segments (texte, emotion), produit des chunks audio.

            Chaque segment porte son propre EmotionPreset qui override les
            parametres Chatterbox (exaggeration, cfg_weight, temperature)
            pour un rendu expressif dynamique.
            """
            fade_samples = int(self.tts.SAMPLE_RATE * 0.05)  # 50ms fade
            try:
                while True:
                    item = tts_queue.get()
                    if item is _SENTINEL or self._barge_in_detected.is_set():
                        break

                    segment_text, emotion_preset = item

                    # Collecter tout l'audio de ce segment
                    segment_chunks = []
                    try:
                        for chunk in self.tts.synthesize_stream(
                            segment_text, emotion_params=emotion_preset,
                        ):
                            if self._barge_in_detected.is_set():
                                break
                            segment_chunks.append(chunk)
                    except Exception as e:
                        log.error("Erreur TTS synthesize_stream: %s", e, exc_info=True)
                        break

                    if not segment_chunks or self._barge_in_detected.is_set():
                        continue

                    segment_audio = np.concatenate(segment_chunks)

                    # Fade-in/out leger pour eviter les clics aux jointures
                    n = min(fade_samples, len(segment_audio) // 2)
                    if n > 0:
                        segment_audio[:n] *= np.linspace(0.0, 1.0, n, dtype=np.float32)
                        segment_audio[-n:] *= np.linspace(1.0, 0.0, n, dtype=np.float32)

                    self._emit_audio_level(segment_audio)
                    audio_queue.put(segment_audio)
            finally:
                audio_queue.put(_SENTINEL)

        def _audio_worker():
            """Thread Audio : joue les chunks au fur et \u00e0 mesure."""
            def _chunk_gen():
                while True:
                    # Timeout loop pour éviter un blocage infini si les workers sont signalés
                    while True:
                        try:
                            chunk = audio_queue.get(timeout=2.0)
                            break
                        except queue.Empty:
                            if self._barge_in_detected.is_set() or not self._running:
                                return
                            continue
                    if chunk is _SENTINEL or self._barge_in_detected.is_set():
                        return
                    if chunk.dtype != np.float32:
                        chunk = chunk.astype(np.float32)
                    yield chunk

            self._emit_state("speaking")
            self.audio.play_audio_stream(_chunk_gen(), self.tts.SAMPLE_RATE)

        # D\u00e9marrer les workers
        tts_thread = threading.Thread(target=_tts_worker, daemon=True)
        audio_thread = threading.Thread(target=_audio_worker, daemon=True)
        tts_thread.start()
        audio_thread.start()

        try:
            for sentence in self.llm.generate_stream():
                if self._barge_in_detected.is_set():
                    log.info("Barge-in! Réponse interrompue.")
                    self.llm.cancel()
                    break

                # Retirer les tags d'emotion pour l'affichage/memoire
                display_text = strip_emotion_tags(sentence)
                full_response += display_text + " "
                log.info("%s: %s", self.config.name, display_text)
                if self.on_response:
                    self.on_response(display_text)

                # Parser les emotions et preparer chaque segment pour le TTS
                segments = parse_emotion_tags(sentence)
                for seg in segments:
                    prepared = prepare_for_tts(seg.text)
                    if prepared:
                        self._emit_state("speaking")
                        tts_queue.put((prepared, seg.preset))

        finally:
            # Signaler la fin au pipeline TTS
            tts_queue.put(_SENTINEL)
            tts_thread.join(timeout=10)
            audio_thread.join(timeout=10)

            # Signaler au monitor que la r\u00e9ponse est termin\u00e9e
            self._response_done.set()

            # Si la r\u00e9ponse est vide (barge-in pr\u00e9coce), r\u00e9cup\u00e9rer la r\u00e9ponse partielle
            response_to_save = full_response.strip()
            if not response_to_save:
                response_to_save = self.llm.get_partial_response()

            # Si barge-in précoce et réponse vide, retirer le message utilisateur orphelin
            if not response_to_save and self._barge_in_detected.is_set():
                if hasattr(self.llm, 'pop_last_user_message'):
                    self.llm.pop_last_user_message()

            if response_to_save and self.config.memory.enabled:
                self.memory.process_assistant_message(
                    response_to_save, self._session_id
                )

            # Vider la queue audio (echo residuel du speaker)
            self.audio.drain_capture_queue()
            # Attendre que l'echo se dissipe avant de reprendre l'ecoute
            time.sleep(0.15)
            self.audio.drain_capture_queue()

    def _monitor_barge_in(self):
        """Surveille le micro pendant que Aethon parle. Détecte les interruptions.

        Le thread tourne tant que ``_response_done`` n'est pas set (toute la
        durée de la réponse LLM + TTS). La détection de parole n'est active
        que lorsque de l'audio est effectivement en lecture (``is_playing``),
        pour éviter les faux positifs pendant la synthèse TTS.

        Protection anti-écho (speaker feedback) :
        - Seuil VAD élevé (0.65 vs 0.5) pour filtrer l'écho amplifié par l'AGC.
        - 5 chunks consécutifs (~160ms) requis — l'écho est souvent intermittent.
        - Gate d'énergie RMS : ignore les chunks faibles (écho atténué < 0.02).
        """
        consecutive_speech = 0
        required_chunks = 10  # 10 chunks de 32ms = ~320ms pour confirmer (filtre echo)
        speech_chunks: list[np.ndarray] = []
        barge_in_vad_threshold = 0.75  # Tres strict (echo speaker passe facilement 0.65)
        min_energy_rms = 0.05  # Echo Pebble V3 a 1m ~ 0.02-0.04 RMS
        playback_warmup = 10  # Ignorer les 10 premiers chunks (~320ms) apres debut lecture
        warmup_counter = 0
        was_playing = False

        while not self._barge_in_detected.is_set() and not self._response_done.is_set():
            chunk = self.audio.get_audio_chunk(timeout=0.05)
            if chunk is None:
                consecutive_speech = 0
                speech_chunks.clear()
                continue

            # Ne detecter le barge-in que pendant la lecture audio
            if not self.audio.is_playing:
                consecutive_speech = 0
                speech_chunks.clear()
                was_playing = False
                warmup_counter = 0
                continue

            # Cooldown au debut de la lecture (echo initial du speaker)
            if not was_playing:
                was_playing = True
                warmup_counter = 0
            warmup_counter += 1
            if warmup_counter <= playback_warmup:
                continue

            # Energy gate : filtrer les chunks faibles (echo speaker)
            if chunk.dtype == np.int16:
                audio_f32 = chunk.astype(np.float32) / 32768.0
            else:
                audio_f32 = chunk.astype(np.float32)
            rms = float(np.sqrt(np.mean(audio_f32 ** 2)))

            if rms > min_energy_rms and self._is_speech(chunk, threshold=barge_in_vad_threshold):
                consecutive_speech += 1
                speech_chunks.append(chunk)
                if consecutive_speech >= required_chunks:
                    log.debug(
                        "Barge-in confirme: %d chunks, RMS=%.4f",
                        consecutive_speech, rms,
                    )
                    with self._barge_in_lock:
                        self._barge_in_audio = speech_chunks.copy()
                    self._barge_in_detected.set()
                    self.audio.stop_playback()
                    return
            else:
                consecutive_speech = 0
                speech_chunks.clear()

    def send_text(self, text: str):
        """Injecte du texte dans le pipeline (bypass STT). Thread-safe."""
        self._text_queue.put(text)

    def _handle_text_input(self, text: str):
        """Traite un message texte injecté (meme flux que la parole, sans STT)."""
        log.info("Toi (texte): %s", text)
        self._emit_state("thinking")
        if self.on_transcript:
            self.on_transcript(text)

        if self.config.memory.enabled:
            self.memory.process_user_message(text, self._session_id)

        with self._llm_lock:
            self.llm.add_user_message(text)
            self._respond_streaming()

    def _play_activation_sound(self):
        """Joue un petit son pour confirmer l'activation."""
        # Bip court synthétique
        sr = self.config.audio.playback_sample_rate
        duration = 0.15
        t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
        tone = 0.3 * np.sin(2 * np.pi * 800 * t)
        # Fade in/out
        fade = int(sr * 0.02)
        tone[:fade] *= np.linspace(0, 1, fade)
        tone[-fade:] *= np.linspace(1, 0, fade)
        self.audio.play_audio(tone, sr)

    def request_stop(self):
        """Demande l'arrêt du pipeline de façon thread-safe.

        Méthode publique utilisable depuis n'importe quel thread (GUI, API).
        Utilise un threading.Event pour la synchronisation inter-threads.
        """
        self._stop_event.set()
        self._running = False

    def stop(self):
        """Arrête proprement le pipeline."""
        log.info("Arrêt de %s...", self.config.name)
        self._stop_event.set()
        self._running = False
        self._emit_state("stopped")

        # Arrêter le serveur API
        if self._api_server:
            self._api_server.stop()
            self._api_server = None

        # Signaler aux workers (barge-in monitor, audio worker) de s'arrêter
        self._barge_in_detected.set()
        self._response_done.set()

        self.audio.cleanup()
        self.tts.unload()
        self.wake_word.unload()
        self.memory.cleanup()
        self.llm.cleanup()
        log.info("%s arrêté.", self.config.name)
