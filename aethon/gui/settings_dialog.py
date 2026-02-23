"""Premium settings dialog with tabbed interface."""

import copy
import logging
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QTabWidget,
)

from aethon.config import AethonConfig
from aethon.gui.theme import ACCENT, BG_VOID, GREEN, TEXT, TEXT_INVERSE, TEXT_SECONDARY
from aethon.gui.widgets.persona_tab import PersonaTab
from aethon.gui.widgets.intelligence_tab import IntelligenceTab
from aethon.gui.widgets.tools_tab import ToolsTab
from aethon.gui.widgets.advanced_tab import AdvancedTab

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Premium settings dialog with 4 tabs."""

    save_and_restart = pyqtSignal(AethonConfig)

    def __init__(self, config: AethonConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Param\u00e8tres \u2014 {config.persona.name}")
        self.setMinimumSize(720, 600)
        self.resize(820, 680)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._config = copy.deepcopy(config)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── Tabs ──
        self._tabs = QTabWidget()
        self._persona_tab = PersonaTab(config)
        self._intelligence_tab = IntelligenceTab(config)
        self._tools_tab = ToolsTab(config)
        self._advanced_tab = AdvancedTab(config)

        self._tabs.addTab(self._persona_tab, "  Persona  ")
        self._tabs.addTab(self._intelligence_tab, "  Intelligence  ")
        self._tabs.addTab(self._tools_tab, "  Outils  ")
        self._tabs.addTab(self._advanced_tab, "  Avanc\u00e9  ")
        layout.addWidget(self._tabs)

        # ── Bottom buttons (custom for premium look) ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.setFixedWidth(120)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("\u2713  Sauvegarder")
        self._save_btn.setFixedWidth(160)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: {TEXT_INVERSE}; "
            f"font-weight: 700; font-size: 14px; border: none; "
            f"border-radius: 8px; padding: 10px 24px; }}"
            f"QPushButton:hover {{ background-color: #6aa0ff; }}"
            f"QPushButton:pressed {{ background-color: #3a6bc5; }}"
        )
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        """Apply changes and emit signal."""
        self._persona_tab.apply(self._config)
        self._intelligence_tab.apply(self._config)
        self._tools_tab.apply(self._config)
        self._advanced_tab.apply(self._config)
        self.save_and_restart.emit(self._config)
        self.accept()
