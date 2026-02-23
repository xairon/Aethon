"""QThread worker wrapping JarvisPipeline for GUI integration."""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from jarvis.config import JarvisConfig
from jarvis.gui.state import PipelineState
from jarvis.pipeline import JarvisPipeline

log = logging.getLogger(__name__)


class PipelineWorker(QThread):
    """Runs JarvisPipeline in a background thread with Qt signals."""

    state_changed = pyqtSignal(PipelineState)
    transcript_received = pyqtSignal(str)
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    audio_level_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pipeline: JarvisPipeline | None = None
        self._config: JarvisConfig | None = None

    def configure(self, config: JarvisConfig):
        self._config = config

    def run(self):
        if self._config is None:
            self.error_occurred.emit("Aucune configuration fournie.")
            return

        try:
            self._pipeline = JarvisPipeline(self._config)

            # Bridge callbacks → Qt signals
            self._pipeline.on_state_change = self._on_state
            self._pipeline.on_transcript = lambda t: self.transcript_received.emit(t)
            self._pipeline.on_response = lambda t: self.response_received.emit(t)
            self._pipeline.on_audio_level = lambda l: self.audio_level_changed.emit(l)

            self._pipeline.load_all()
            self._pipeline.run()
        except ConnectionError as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            log.exception("Erreur pipeline")
            self.error_occurred.emit(f"Erreur: {e}")
        finally:
            if self._pipeline:
                try:
                    self._pipeline.stop()
                except Exception:
                    pass
                self._pipeline = None
            self.state_changed.emit(PipelineState.STOPPED)

    def _on_state(self, state_str: str):
        try:
            state = PipelineState(state_str)
            self.state_changed.emit(state)
        except ValueError:
            log.warning("État pipeline inconnu ignoré : '%s'", state_str)

    def send_text(self, text: str):
        """Injecte du texte dans le pipeline (bypass STT). Thread-safe."""
        if self._pipeline:
            self._pipeline.send_text(text)

    def stop_pipeline(self):
        """Demande l'arrêt du pipeline de façon thread-safe."""
        if self._pipeline:
            self._pipeline.request_stop()
