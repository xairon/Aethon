"""Premium toast notification system with smooth animations."""

from PyQt6.QtCore import (
    QEasingCurve, QPropertyAnimation, QSequentialAnimationGroup,
    Qt,
)
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

from jarvis.gui.theme import (
    ACCENT, BG_SURFACE, BORDER_DEFAULT, GREEN, AMBER, RED, TEXT,
)


class ToastType:
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


_COLORS = {
    ToastType.INFO: ACCENT,
    ToastType.SUCCESS: GREEN,
    ToastType.WARNING: AMBER,
    ToastType.ERROR: RED,
}

_ICONS = {
    ToastType.INFO: "\u2139",     # ℹ
    ToastType.SUCCESS: "\u2713",  # ✓
    ToastType.WARNING: "\u26a0",  # ⚠
    ToastType.ERROR: "\u2717",    # ✗
}


class Toast(QWidget):
    """Auto-dismissing toast notification with premium styling."""

    def __init__(self, message: str, toast_type: str = ToastType.INFO,
                 duration_ms: int = 4000, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(52)

        accent = _COLORS.get(toast_type, ACCENT)
        icon_char = _ICONS.get(toast_type, "\u2139")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 20, 10)
        layout.setSpacing(12)

        icon = QLabel(icon_char)
        icon.setFixedWidth(20)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color: {accent}; font-weight: 700; font-size: 15px; "
            "background: transparent;"
        )
        layout.addWidget(icon)

        label = QLabel(message)
        label.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 500; "
            "background: transparent;"
        )
        layout.addWidget(label)

        self.setStyleSheet(
            f"background-color: {BG_SURFACE}; "
            f"border: 1px solid {BORDER_DEFAULT}; "
            f"border-left: 3px solid {accent}; "
            "border-radius: 10px;"
        )

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._duration = duration_ms
        self._anim_group: QSequentialAnimationGroup | None = None

    def show_animated(self, x: int, y: int):
        self.move(x, y)
        self.show()
        self.raise_()

        fade_in = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade_in.setDuration(220)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        hold = QPropertyAnimation(self._opacity_effect, b"opacity")
        hold.setDuration(max(self._duration - 440, 1000))
        hold.setStartValue(1.0)
        hold.setEndValue(1.0)

        fade_out = QPropertyAnimation(self._opacity_effect, b"opacity")
        fade_out.setDuration(220)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

        self._anim_group = QSequentialAnimationGroup(self)
        self._anim_group.addAnimation(fade_in)
        self._anim_group.addAnimation(hold)
        self._anim_group.addAnimation(fade_out)
        self._anim_group.finished.connect(self._on_finished)
        self._anim_group.start()

    def _on_finished(self):
        self.close()
        self.deleteLater()


class ToastManager:
    """Manages toast positioning and stacking."""

    def __init__(self, parent_widget: QWidget):
        self._parent = parent_widget
        self._active: list[Toast] = []
        self._spacing = 60

    def show_toast(self, message: str, toast_type: str = ToastType.INFO,
                   duration_ms: int = 4000):
        toast = Toast(message, toast_type, duration_ms, parent=self._parent)
        toast.setFixedWidth(min(self._parent.width() - 40, 420))

        rect = self._parent.rect()
        global_pos = self._parent.mapToGlobal(rect.topRight())
        x = global_pos.x() - toast.width() - 16
        y = global_pos.y() + 16 + len(self._active) * self._spacing

        self._active.append(toast)
        toast.destroyed.connect(lambda: self._remove(toast))
        toast.show_animated(x, y)

    def _remove(self, toast):
        if toast in self._active:
            self._active.remove(toast)

    def info(self, msg: str):
        self.show_toast(msg, ToastType.INFO)

    def success(self, msg: str):
        self.show_toast(msg, ToastType.SUCCESS)

    def warning(self, msg: str):
        self.show_toast(msg, ToastType.WARNING)

    def error(self, msg: str):
        self.show_toast(msg, ToastType.ERROR, duration_ms=6000)
