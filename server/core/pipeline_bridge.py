"""Bridge thread/async — connecte AethonPipeline (synchrone) au serveur FastAPI (async).

Le pipeline tourne dans un thread dedie. Les callbacks (on_state_change, on_transcript,
on_response, on_audio_level) sont bridges vers l'event loop asyncio principal via
asyncio.run_coroutine_threadsafe() pour diffuser les messages WebSocket.
"""

import asyncio
import logging
import threading
import time

from aethon.config import AethonConfig
from aethon.pipeline import AethonPipeline
from server.core.connection_manager import ConnectionManager

log = logging.getLogger(__name__)

# Labels d'etat affiches dans le frontend
STATE_LABELS = {
    "stopped": "Arrete",
    "loading": "Chargement...",
    "idle": "Pret",
    "listening": "Ecoute...",
    "thinking": "Reflexion...",
    "speaking": "Parle...",
}


class PipelineBridge:
    """Pont entre AethonPipeline (thread synchrone) et FastAPI (async).

    Gere le cycle de vie du pipeline : creation, demarrage dans un thread,
    arret propre, et relay des callbacks vers les WebSocket clients.
    """

    def __init__(self, manager: ConnectionManager):
        self._manager = manager
        self._pipeline: AethonPipeline | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._config: AethonConfig = AethonConfig.load()
        self._current_state: str = "stopped"
        self._last_audio_level_time: float = 0.0
        self._start_lock: asyncio.Lock | None = None
        self._loop_none_warned: bool = False

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Enregistre l'event loop principal (appele au demarrage du serveur)."""
        self._loop = loop
        self._start_lock = asyncio.Lock()
        log.info("Event loop enregistre, bridge pret.")

    @property
    def config(self) -> AethonConfig:
        """Configuration actuelle."""
        return self._config

    @property
    def current_state(self) -> str:
        """Etat actuel du pipeline."""
        return self._current_state

    @property
    def is_running(self) -> bool:
        """True si le thread pipeline est actif."""
        return self._thread is not None and self._thread.is_alive()

    async def start(self):
        """Charge les modeles et demarre le pipeline dans un thread dedie.

        Utilise un asyncio.Lock pour garantir qu'un seul demarrage a la fois,
        meme si plusieurs coroutines appellent start() concurremment.
        """
        if self.is_running:
            log.warning("Pipeline deja en cours d'execution.")
            return

        # Garantir que le lock existe (set_loop devrait l'avoir cree)
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
            log.warning("_start_lock n'existait pas — cree a la volee.")

        if self._start_lock.locked():
            log.warning("Demarrage deja en cours (lock occupe).")
            return

        async with self._start_lock:
            if self.is_running:
                return  # Re-check apres acquisition du verrou
            try:
                log.info("Demarrage du pipeline...")

                # Recharger la config depuis le disque (l'utilisateur a pu la modifier)
                self._config = AethonConfig.load()
                log.info("Config chargee: tts=%s, llm=%s",
                         self._config.tts.backend, self._config.llm.backend)

                self._pipeline = AethonPipeline(self._config)

                # Brancher les callbacks (thread pipeline → broadcast WebSocket)
                self._pipeline.on_state_change = self._bridge_state
                self._pipeline.on_transcript = self._bridge_transcript
                self._pipeline.on_response = self._bridge_response
                self._pipeline.on_audio_level = self._bridge_audio_level

                # Broadcast "loading" avec await direct (on est sur l'event loop)
                await self._async_set_state("loading")

                log.info("Chargement des modeles (load_all)...")
                await asyncio.get_running_loop().run_in_executor(
                    None, self._pipeline.load_all
                )
                log.info("Modeles charges avec succes.")

                # Lancer la boucle principale dans un thread dedie
                self._thread = threading.Thread(
                    target=self._run_pipeline, daemon=True, name="aethon-pipeline"
                )
                self._thread.start()
                log.info("Pipeline demarre dans le thread '%s'.", self._thread.name)
            except Exception as e:
                log.error("Erreur demarrage pipeline: %s", e, exc_info=True)
                await self._async_set_state("stopped")
                self._pipeline = None
                raise

    def _run_pipeline(self):
        """Point d'entree du thread pipeline — appelle pipeline.run() (bloquant)."""
        try:
            self._pipeline.run()
        except Exception as e:
            log.error("Erreur fatale pipeline: %s", e, exc_info=True)
            self._bridge_toast(f"Erreur fatale pipeline: {e}", level="error")
        finally:
            self._bridge_state("stopped")
            log.info("Thread pipeline termine.")

    async def stop(self):
        """Arrete le pipeline proprement.

        Sequence : request_stop() → join thread → cleanup() si necessaire.
        Le thread pipeline appelle pipeline.run() qui boucle tant que _running=True.
        request_stop() met _running=False, le thread se termine, et le finally
        du thread appelle _bridge_state("stopped").
        """
        pipeline = self._pipeline
        if pipeline is None:
            log.info("stop() appele mais pas de pipeline actif.")
            return

        log.info("Arret du pipeline demande...")
        # Demander l'arret de facon thread-safe
        pipeline.request_stop()

        # Attendre la fin du thread (avec timeout)
        thread = self._thread
        if thread and thread.is_alive():
            await asyncio.get_running_loop().run_in_executor(
                None, thread.join, 10.0
            )
            if thread.is_alive():
                log.critical(
                    "Le thread pipeline ne s'est pas arrete apres 10s — "
                    "risque de fuite de ressources."
                )
                await self._manager.broadcast({
                    "type": "toast",
                    "message": "Le pipeline ne repond plus. Un redemarrage peut etre necessaire.",
                    "level": "warning",
                })

        # Nettoyage ressources (audio, TTS, memoire, etc.)
        if self._pipeline is not None:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    None, pipeline.stop
                )
            except Exception as e:
                log.warning("Erreur stop pipeline: %s", e)

        self._pipeline = None
        self._thread = None
        # Broadcast "stopped" avec await direct
        await self._async_set_state("stopped")
        log.info("Pipeline arrete.")

    def send_text(self, text: str):
        """Injecte du texte dans le pipeline (bypass STT). Thread-safe."""
        if self._pipeline:
            self._pipeline.send_text(text)

    def update_config(self, data: dict):
        """Met a jour la config depuis un dictionnaire partiel et sauvegarde.

        Merge les changements dans la config existante pour ne pas perdre
        les champs non envoyes par le client.
        Le pipeline doit etre redemarre pour que les changements prennent effet.
        """
        current = self._config.to_dict()
        for key, value in data.items():
            if key in current and isinstance(current[key], dict) and isinstance(value, dict):
                current[key].update(value)
            else:
                current[key] = value
        self._config = AethonConfig.from_dict(current)
        self._config.save()
        log.info("Configuration mise a jour et sauvegardee.")

    # ── Async broadcast (depuis le contexte async — event loop) ────

    async def _async_set_state(self, state: str):
        """Change et broadcast l'etat depuis le contexte async (event loop).

        Utilise await direct au lieu de run_coroutine_threadsafe — plus fiable
        quand on est deja sur l'event loop (pas de scheduling incertain).
        """
        if state == self._current_state:
            return
        self._current_state = state
        label = STATE_LABELS.get(state, state)
        log.info("Etat → %s (%s) [async broadcast direct]", state, label)
        await self._manager.broadcast({"type": "state", "state": state, "label": label})

    async def _async_toast(self, message: str, level: str = "info"):
        """Envoie un toast directement depuis le contexte async."""
        await self._manager.broadcast({
            "type": "toast",
            "message": message,
            "level": level,
        })

    # ── Callbacks bridges (thread pipeline → async event loop) ──────

    def _warn_no_loop(self) -> bool:
        """Verifie si l'event loop est disponible. Log un warning une seule fois si absent.

        Retourne True si l'event loop est pret, False sinon.
        """
        if self._loop and not self._loop.is_closed():
            return True
        if not self._loop_none_warned:
            log.warning("Event loop asyncio non disponible — les messages WebSocket sont ignores.")
            self._loop_none_warned = True
        return False

    def _safe_broadcast(self, payload: dict):
        """Envoie un message via run_coroutine_threadsafe avec gestion d'erreur.

        Tous les callbacks bridges passent par cette methode pour eviter
        les crashes si l'event loop est ferme ou en erreur.
        """
        if not self._warn_no_loop():
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._manager.broadcast(payload),
                self._loop,
            )
        except RuntimeError as e:
            log.warning("Bridge broadcast impossible (loop ferme?): %s", e)

    def _bridge_state(self, state: str):
        """Callback changement d'etat — thread pipeline → broadcast WebSocket.

        Deduplique les etats identiques consecutifs pour eviter les broadcasts inutiles.
        """
        if state == self._current_state:
            return
        self._current_state = state
        label = STATE_LABELS.get(state, state)
        self._safe_broadcast({"type": "state", "state": state, "label": label})

    def _bridge_transcript(self, text: str):
        """Callback transcription utilisateur — thread pipeline → broadcast WebSocket."""
        self._safe_broadcast({
            "type": "transcript",
            "text": text,
            "timestamp": time.time(),
        })

    def _bridge_response(self, text: str):
        """Callback reponse LLM — thread pipeline → broadcast WebSocket."""
        self._safe_broadcast({
            "type": "response",
            "text": text,
            "timestamp": time.time(),
        })

    def _bridge_toast(self, message: str, level: str = "info"):
        """Envoie une notification toast aux clients WebSocket depuis le thread pipeline."""
        self._safe_broadcast({
            "type": "toast",
            "message": message,
            "level": level,
        })

    def _bridge_audio_level(self, level: float):
        """Callback niveau audio — throttle a max 20 messages/seconde (50ms min)."""
        now = time.monotonic()
        if now - self._last_audio_level_time < 0.05:
            return
        self._last_audio_level_time = now
        self._safe_broadcast({"type": "audio_level", "level": round(level, 3)})
