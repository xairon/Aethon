"""Premium chat conversation view with styled bubbles."""

import time

from PyQt6.QtCore import (
    QEasingCurve, QPropertyAnimation, Qt, QTimer,
)
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QScrollArea, QVBoxLayout, QWidget,
)

from aethon.gui.theme import (
    ACCENT, BG_ELEVATED, BG_RAISED, BG_SURFACE, TEXT, TEXT_MUTED,
    TEXT_SECONDARY, GREEN, BORDER_DEFAULT,
)


class ChatBubble(QFrame):
    """A single chat message bubble with entrance animation."""

    def __init__(self, text: str, is_user: bool, name: str = "", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)

        if not is_user:
            bubble = self._make_bubble(text, name, is_user)
            outer.addWidget(bubble)
            outer.addStretch()
        else:
            outer.addStretch()
            bubble = self._make_bubble(text, name, is_user)
            outer.addWidget(bubble)

        # Entrance fade-in animation
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._fade_anim = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # Retirer l'effet après l'animation pour éviter le compositing pixmap intermédiaire
        self._fade_anim.finished.connect(lambda: self.setGraphicsEffect(None))
        self._fade_anim.start()

    def _make_bubble(self, text: str, name: str, is_user: bool) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        if name:
            name_label = QLabel(name)
            color = ACCENT if not is_user else GREEN
            name_label.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: 600; "
                "background: transparent; letter-spacing: 0.3px;"
            )
            layout.addWidget(name_label)

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; background: transparent; "
            "line-height: 1.4;"
        )
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(msg)

        ts = QLabel(time.strftime("%H:%M"))
        ts.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 10px; background: transparent;"
        )
        ts.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(ts)

        # User: slightly lighter, Assistant: darker surface
        bg = BG_ELEVATED if is_user else BG_SURFACE
        border = BORDER_DEFAULT
        container.setStyleSheet(
            f"background-color: {bg}; border-radius: 14px; "
            f"border: 1px solid {border};"
        )
        container.setMaximumWidth(480)

        return container


class ChatWidget(QScrollArea):
    """Scrollable chat view with premium bubbles."""

    MAX_MESSAGES = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: transparent;")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(6)
        self._layout.addStretch()
        self.setWidget(self._container)

        self._message_count = 0
        self._assistant_name = "Aethon"

    def set_assistant_name(self, name: str):
        self._assistant_name = name

    def add_user_message(self, text: str):
        self._add_bubble(text, is_user=True, name="Toi")

    def add_assistant_message(self, text: str):
        self._add_bubble(text, is_user=False, name=self._assistant_name)

    def _add_bubble(self, text: str, is_user: bool, name: str):
        if not text or not text.strip():
            return
        bubble = ChatBubble(text, is_user, name, parent=self._container)

        # Insert before the bottom stretch
        count = self._layout.count()
        self._layout.insertWidget(count - 1, bubble)
        self._message_count += 1

        # Prune old messages
        if self._message_count > self.MAX_MESSAGES:
            # Le stretch est a l'index 0, les bulles commencent a l'index 1
            for i in range(self._layout.count()):
                item = self._layout.itemAt(i)
                if item and item.widget():
                    item.widget().deleteLater()
                    self._layout.removeItem(item)
                    self._message_count -= 1
                    break

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vbar = self.verticalScrollBar()
        vbar.setValue(vbar.maximum())
