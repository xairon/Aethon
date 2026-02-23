"""System tray icon with state-colored indicator."""

from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from jarvis.gui.state import PipelineState, STATE_COLORS, STATE_LABELS


def _make_icon(color_hex: str, size: int = 64) -> QIcon:
    """Generate a colored circle icon programmatically."""
    pixmap = QPixmap(QSize(size, size))
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color_hex))
    painter.setPen(QColor(color_hex))
    margin = size // 8
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pixmap)


class JarvisTray(QSystemTrayIcon):
    """System tray icon that reflects pipeline state."""

    toggle_window = pyqtSignal()
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, name: str = "Jarvis", parent=None):
        super().__init__(parent)
        self._name = name
        self._state = PipelineState.STOPPED
        self._icons: dict[PipelineState, QIcon] = {
            state: _make_icon(color) for state, color in STATE_COLORS.items()
        }

        self.setIcon(self._icons[PipelineState.STOPPED])
        self.setToolTip(f"{self._name} \u2014 {STATE_LABELS[PipelineState.STOPPED]}")

        # Context menu
        self._menu = QMenu()
        self._start_action = QAction("D\u00e9marrer", self._menu)
        self._start_action.triggered.connect(self.start_requested.emit)
        self._stop_action = QAction("Arr\u00eater", self._menu)
        self._stop_action.triggered.connect(self.stop_requested.emit)
        self._stop_action.setEnabled(False)
        self._settings_action = QAction("Param\u00e8tres", self._menu)
        self._settings_action.triggered.connect(self.toggle_window.emit)
        self._quit_action = QAction("Quitter", self._menu)
        self._quit_action.triggered.connect(self.quit_requested.emit)

        self._menu.addAction(self._start_action)
        self._menu.addAction(self._stop_action)
        self._menu.addSeparator()
        self._menu.addAction(self._settings_action)
        self._menu.addSeparator()
        self._menu.addAction(self._quit_action)
        self.setContextMenu(self._menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_window.emit()

    def update_state(self, state: PipelineState):
        self._state = state
        self.setIcon(self._icons[state])
        self.setToolTip(f"{self._name} \u2014 {STATE_LABELS[state]}")

        running = state not in (PipelineState.STOPPED,)
        self._start_action.setEnabled(not running)
        self._stop_action.setEnabled(running)

    def set_name(self, name: str):
        self._name = name
        self.setToolTip(f"{self._name} \u2014 {STATE_LABELS[self._state]}")
