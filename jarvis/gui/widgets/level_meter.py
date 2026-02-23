"""Premium audio level meter with gradient fill and glow."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QWidget


class LevelMeter(QWidget):
    """Horizontal audio level bar with gradient and subtle glow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.setMinimumWidth(120)
        self._level = 0.0

    def set_level(self, level: float):
        self._level = max(0.0, min(1.0, level))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        r = h / 2

        # Background track
        painter.setBrush(QColor("#151a26"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, r, r)

        # Filled portion
        fill_w = int(w * self._level)
        if fill_w > 1:
            gradient = QLinearGradient(0, 0, w, 0)
            gradient.setColorAt(0.0, QColor("#34d399"))
            gradient.setColorAt(0.6, QColor("#4f8fff"))
            gradient.setColorAt(0.85, QColor("#fbbf24"))
            gradient.setColorAt(1.0, QColor("#f87171"))
            painter.setBrush(gradient)
            painter.drawRoundedRect(0, 0, fill_w, h, r, r)

        painter.end()
