"""Aethon GUI application — QApplication + orchestration."""

import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from aethon.config import AethonConfig
from aethon.gui.main_window import MainWindow
from aethon.gui.state import PipelineState
from aethon.gui.theme import STYLESHEET
from aethon.gui.tray import AethonTray, _make_icon
from aethon.gui.worker import PipelineWorker

log = logging.getLogger(__name__)


class AethonApp:
    """Top-level GUI application orchestrating tray, window, and pipeline."""

    def __init__(self, argv: list[str]):
        # pythonw.exe sets stdout/stderr to None — redirect to log file
        if sys.stdout is None or sys.stderr is None:
            _app_dir = os.path.dirname(os.path.abspath(__file__))
            _log_path = os.path.join(_app_dir, "..", "..", "aethon.log")
            _log_file = open(os.path.abspath(_log_path), "w", encoding="utf-8")
            if sys.stdout is None:
                sys.stdout = _log_file
            if sys.stderr is None:
                sys.stderr = _log_file

        # Encodage UTF-8 sur Windows
        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

        # espeak-ng au PATH
        espeak_dir = r"C:\Program Files\eSpeak NG"
        if os.path.isdir(espeak_dir) and espeak_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + espeak_dir

        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

        # Logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            handlers=[logging.StreamHandler(sys.stderr)],
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("faster_whisper").setLevel(logging.WARNING)

        self._app = QApplication(argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setStyleSheet(STYLESHEET)

        # Config (safe load — fallback to defaults on corruption)
        try:
            self.config = AethonConfig.load()
        except Exception:
            log.warning("Config file corrupt or unreadable — using defaults.")
            self.config = AethonConfig()

        # Worker
        self.worker = PipelineWorker()
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.transcript_received.connect(self._on_transcript)
        self.worker.response_received.connect(self._on_response)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.audio_level_changed.connect(self._on_audio_level)

        # Tray
        self.tray = AethonTray(name=self.config.name)
        self.tray.start_requested.connect(self.start_pipeline)
        self.tray.stop_requested.connect(self.stop_pipeline)
        self.tray.toggle_window.connect(self._toggle_window)
        self.tray.quit_requested.connect(self.quit)
        self.tray.show()

        # Window
        self.window = MainWindow(self.config)
        self.window.setWindowIcon(_make_icon("#4f8fff"))
        self.window.start_requested.connect(self.start_pipeline)
        self.window.stop_requested.connect(self.stop_pipeline)
        self.window.text_submitted.connect(self.worker.send_text)
        self.window.save_and_restart.connect(self._save_and_restart)
        self.window.show()

    def _on_state_changed(self, state: PipelineState):
        self.tray.update_state(state)
        self.window.update_state(state)

    def _on_transcript(self, text: str):
        self.window.append_transcript(text)

    def _on_response(self, text: str):
        self.window.append_response(text)

    def _on_audio_level(self, level: float):
        self.window.update_audio_level(level)

    def _on_error(self, msg: str):
        log.error("Pipeline error: %s", msg)
        self.window.show_error(msg)

    def start_pipeline(self):
        if self.worker.isRunning():
            return
        self.worker.configure(self.config)
        self.worker.start()

    def stop_pipeline(self):
        if not self.worker.isRunning():
            return
        self.worker.stop_pipeline()
        if not self.worker.wait(5000):
            log.warning("Pipeline thread did not stop within 5s — terminating.")
            self.worker.terminate()
            self.worker.wait(2000)

    def _save_and_restart(self, new_config: AethonConfig):
        was_terminated = self._stop_pipeline_with_status()
        self.config = new_config
        self.config.save()
        self.tray.set_name(self.config.name)
        self.window.set_config(self.config)
        if was_terminated:
            # Après un terminate(), laisser le temps aux ressources GPU de se libérer
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self.start_pipeline)
        else:
            self.start_pipeline()

    def _stop_pipeline_with_status(self) -> bool:
        """Arrête le pipeline et retourne True si terminate() a été utilisé."""
        if not self.worker.isRunning():
            return False
        self.worker.stop_pipeline()
        if not self.worker.wait(5000):
            log.warning("Pipeline thread did not stop within 5s — terminating.")
            self.worker.terminate()
            self.worker.wait(2000)
            return True
        return False

    def _toggle_window(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def quit(self):
        self.stop_pipeline()
        self.tray.hide()
        self._app.quit()

    def exec(self) -> int:
        return self._app.exec()
