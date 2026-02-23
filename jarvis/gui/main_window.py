"""Main window — premium layout with animated orb, chat, and controls."""

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QVBoxLayout, QWidget,
)

from jarvis.config import JarvisConfig
from jarvis.gui.settings_dialog import SettingsDialog
from jarvis.gui.state import PipelineState, STATE_COLORS, STATE_LABELS
from jarvis.gui.theme import (
    ACCENT, ACCENT_HOVER, BG_BASE, BG_ELEVATED, BG_RAISED, BG_SURFACE, BG_VOID,
    BORDER_DEFAULT, BORDER_DIM,
    TEXT, TEXT_INVERSE, TEXT_MUTED, TEXT_SECONDARY,
)
from jarvis.gui.widgets.chat_widget import ChatWidget
from jarvis.gui.widgets.level_meter import LevelMeter
from jarvis.gui.widgets.orb_widget import OrbWidget
from jarvis.gui.widgets.toast import ToastManager


class MainWindow(QMainWindow):
    """Jarvis main window with animated orb, chat, and controls."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    text_submitted = pyqtSignal(str)
    save_and_restart = pyqtSignal(JarvisConfig)

    def __init__(self, config: JarvisConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._state = PipelineState.STOPPED

        self.setWindowTitle(config.name)
        self.setMinimumSize(500, 720)
        self.resize(540, 860)

        self._build_ui()
        self._setup_shortcuts()
        self._toast = ToastManager(self)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 28, 24, 18)
        root.setSpacing(0)

        # ── Title ──
        self._title = QLabel(self.config.name.upper())
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color: {TEXT}; font-size: 22px; font-weight: 300; "
            "letter-spacing: 14px; "
            "font-family: 'Segoe UI Variable Display', 'Segoe UI', sans-serif; "
            "background: transparent; padding-left: 14px;"
        )
        root.addWidget(self._title)
        root.addSpacing(20)

        # ── Orb ──
        orb_container = QHBoxLayout()
        orb_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._orb = OrbWidget()
        orb_container.addWidget(self._orb)
        root.addLayout(orb_container)
        root.addSpacing(6)

        # ── State indicator (dot + label) ──
        state_row = QHBoxLayout()
        state_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state_row.setSpacing(8)

        self._state_dot = QLabel()
        self._state_dot.setFixedSize(8, 8)
        self._state_dot.setStyleSheet(
            f"background-color: {STATE_COLORS[PipelineState.STOPPED]}; "
            "border-radius: 4px;"
        )
        state_row.addWidget(self._state_dot)

        self._state_label = QLabel(STATE_LABELS[PipelineState.STOPPED])
        self._state_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 500; "
            "background: transparent; letter-spacing: 0.5px;"
        )
        state_row.addWidget(self._state_label)

        root.addLayout(state_row)
        root.addSpacing(6)

        # ── Level meter ──
        meter_container = QHBoxLayout()
        meter_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._meter = LevelMeter()
        self._meter.setFixedWidth(180)
        self._meter.setVisible(False)
        meter_container.addWidget(self._meter)
        root.addLayout(meter_container)
        root.addSpacing(14)

        # ── Separator ──
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
        root.addWidget(sep)
        root.addSpacing(14)

        # ── Chat ──
        self._chat = ChatWidget()
        self._chat.set_assistant_name(self.config.name)
        root.addWidget(self._chat, stretch=1)
        root.addSpacing(10)

        # ── Text input ──
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._text_input = QLineEdit()
        self._text_input.setObjectName("textInput")
        self._text_input.setPlaceholderText("Taper un message (bypass STT)...")
        self._text_input.setFixedHeight(38)
        self._text_input.setStyleSheet(
            f"QLineEdit#textInput {{"
            f"  background-color: {BG_RAISED};"
            f"  color: {TEXT};"
            f"  border: 1px solid {BORDER_DEFAULT};"
            f"  border-radius: 10px;"
            f"  padding: 8px 14px;"
            f"  font-size: 13px;"
            f"}}"
            f"QLineEdit#textInput:focus {{"
            f"  border-color: {ACCENT};"
            f"  background-color: {BG_ELEVATED};"
            f"}}"
            f"QLineEdit#textInput:disabled {{"
            f"  background-color: {BG_SURFACE};"
            f"  color: {TEXT_MUTED};"
            f"  border-color: {BORDER_DIM};"
            f"}}"
        )
        self._text_input.setEnabled(False)
        self._text_input.returnPressed.connect(self._on_text_submit)
        input_row.addWidget(self._text_input)

        self._send_btn = QPushButton("\u27a4")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setFixedSize(38, 38)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setEnabled(False)
        self._send_btn.setStyleSheet(
            f"QPushButton#sendBtn {{"
            f"  background-color: {ACCENT};"
            f"  color: {TEXT_INVERSE};"
            f"  border: none;"
            f"  border-radius: 10px;"
            f"  font-size: 16px;"
            f"  font-weight: 700;"
            f"  padding: 0;"
            f"}}"
            f"QPushButton#sendBtn:hover {{"
            f"  background-color: {ACCENT_HOVER};"
            f"}}"
            f"QPushButton#sendBtn:disabled {{"
            f"  background-color: {BG_RAISED};"
            f"  color: {TEXT_MUTED};"
            f"}}"
        )
        self._send_btn.clicked.connect(self._on_text_submit)
        input_row.addWidget(self._send_btn)

        root.addLayout(input_row)
        root.addSpacing(10)

        # ── Bottom bar ──
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self._settings_btn = QPushButton("\u2699  Param\u00e8tres")
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.setFixedWidth(130)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.clicked.connect(self._open_settings)
        bottom.addWidget(self._settings_btn)

        bottom.addStretch()

        self._start_btn = QPushButton("\u25b6  D\u00e9marrer")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setFixedWidth(140)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self.start_requested.emit)
        bottom.addWidget(self._start_btn)

        self._stop_btn = QPushButton("\u25a0  Arr\u00eater")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setFixedWidth(140)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        bottom.addWidget(self._stop_btn)

        root.addLayout(bottom)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(
            self.start_requested.emit
        )
        QShortcut(QKeySequence("Ctrl+."), self).activated.connect(
            self.stop_requested.emit
        )
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(
            self._open_settings
        )

    # ── Public API (called by JarvisApp) ──

    def set_config(self, config: JarvisConfig):
        self.config = config
        self._title.setText(config.name.upper())
        self.setWindowTitle(config.name)
        self._chat.set_assistant_name(config.name)
        self._toast.success("Configuration sauvegard\u00e9e")

    def update_state(self, state: PipelineState):
        self._state = state
        self._orb.set_state(state)

        # State label + dot
        color = STATE_COLORS[state]
        self._state_label.setText(STATE_LABELS[state])
        self._state_label.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: 500; "
            "background: transparent; letter-spacing: 0.5px;"
        )
        self._state_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 4px;"
        )

        # Buttons
        running = state != PipelineState.STOPPED
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)

        # Text input — actif uniquement quand le pipeline tourne
        self._text_input.setEnabled(running)
        self._send_btn.setEnabled(running)

        # Level meter visibility
        self._meter.setVisible(
            state in (PipelineState.LISTENING, PipelineState.SPEAKING)
        )
        if state not in (PipelineState.LISTENING, PipelineState.SPEAKING):
            self._meter.set_level(0.0)

    def update_audio_level(self, level: float):
        self._orb.set_audio_level(level)
        self._meter.set_level(level)

    def append_transcript(self, text: str):
        self._chat.add_user_message(text)

    def append_response(self, text: str):
        self._chat.add_assistant_message(text)

    def show_error(self, msg: str):
        self._toast.error(msg)

    def _on_text_submit(self):
        """Envoie le texte tape au pipeline (bypass STT)."""
        text = self._text_input.text().strip()
        if not text:
            return
        self._text_input.clear()
        self.text_submitted.emit(text)

    # ── Internal ──

    def _open_settings(self):
        dialog = SettingsDialog(self.config, parent=self)
        dialog.save_and_restart.connect(self.save_and_restart.emit)
        dialog.exec()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
