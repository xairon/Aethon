"""Onglet Outils — outils function calling et serveur API."""

import logging

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from aethon.config import AethonConfig

log = logging.getLogger(__name__)


class ToolsTab(QWidget):
    """Onglet Outils : outils disponibles et serveur API."""

    def __init__(self, config: AethonConfig, parent=None):
        super().__init__(parent)
        self._config = config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # ══════════════════════════════════════════
        # Section Function Calling
        # ══════════════════════════════════════════
        fc_group = QGroupBox("Function Calling (Gemini)")
        fc_layout = QVBoxLayout(fc_group)

        fc_info = QLabel(
            "<small><i>Le function calling permet au LLM d'appeler des outils "
            "pour effectuer des actions concrètes (chercher sur le web, "
            "consulter l'heure, etc.). Nécessite le backend Gemini.</i></small>"
        )
        fc_info.setWordWrap(True)
        fc_layout.addWidget(fc_info)

        self._enable_tools = QCheckBox("Activer le function calling")
        self._enable_tools.setChecked(config.llm.enable_tools)
        fc_layout.addWidget(self._enable_tools)

        layout.addWidget(fc_group)

        # ══════════════════════════════════════════
        # Section Outils disponibles
        # ══════════════════════════════════════════
        tools_group = QGroupBox("Outils disponibles")
        tools_layout = QVBoxLayout(tools_group)

        # Google Search (grounding Gemini, toujours via enable_search)
        self._search_tool = QCheckBox("Google Search (recherche web)")
        self._search_tool.setChecked(config.llm.enable_search)
        self._search_tool.setToolTip(
            "Permet à l'assistant de chercher sur le web via Gemini search grounding. "
            "Pas besoin de function calling, intégré nativement dans Gemini."
        )
        tools_layout.addWidget(self._search_tool)

        # Date et heure
        self._datetime_tool = QCheckBox("Date et heure")
        self._datetime_tool.setChecked(config.tools.enable_datetime)
        self._datetime_tool.setToolTip(
            "Permet à l'assistant de consulter la date et l'heure actuelles. "
            "Utile quand l'utilisateur demande 'quelle heure est-il ?'."
        )
        tools_layout.addWidget(self._datetime_tool)

        # Infos système
        self._system_tool = QCheckBox("Informations système")
        self._system_tool.setChecked(config.tools.enable_system_info)
        self._system_tool.setToolTip(
            "Permet à l'assistant de consulter les infos du système (OS, RAM, GPU, disque). "
            "Utile quand l'utilisateur demande 'combien de mémoire ai-je ?'."
        )
        tools_layout.addWidget(self._system_tool)

        layout.addWidget(tools_group)

        # ══════════════════════════════════════════
        # Section Serveur API
        # ══════════════════════════════════════════
        api_group = QGroupBox("Serveur API HTTP")
        api_layout = QVBoxLayout(api_group)

        api_info = QLabel(
            "<small><i>Le serveur API permet de contrôler Aethon à distance "
            "via des requêtes HTTP (webhook, montre connectée, domotique, etc.).</i></small>"
        )
        api_info.setWordWrap(True)
        api_layout.addWidget(api_info)

        self._enable_api = QCheckBox("Activer le serveur API")
        self._enable_api.setChecked(config.tools.enable_api_server)
        self._enable_api.toggled.connect(self._on_api_toggled)
        api_layout.addWidget(self._enable_api)

        api_form = QFormLayout()

        self._api_port = QSpinBox()
        self._api_port.setRange(1024, 65535)
        self._api_port.setValue(config.tools.api_port)
        api_form.addRow("Port :", self._api_port)

        api_layout.addLayout(api_form)

        # Endpoints disponibles
        endpoints_label = QLabel(
            "<small>"
            "<b>Endpoints :</b><br>"
            "POST /api/command — Envoyer un texte<br>"
            "POST /api/wake — Activer Aethon<br>"
            "GET /api/status — État du pipeline<br>"
            "GET /api/tools — Lister les outils"
            "</small>"
        )
        endpoints_label.setWordWrap(True)
        api_layout.addWidget(endpoints_label)

        self._on_api_toggled(config.tools.enable_api_server)

        layout.addWidget(api_group)
        layout.addStretch()

    # ── Toggle serveur API ──

    def _on_api_toggled(self, enabled: bool):
        """Active/désactive le champ port."""
        self._api_port.setEnabled(enabled)

    # ── Application des changements ──

    def apply(self, config: AethonConfig):
        """Applique les valeurs du formulaire à la config."""
        # Function calling
        config.llm.enable_tools = self._enable_tools.isChecked()
        config.llm.enable_search = self._search_tool.isChecked()

        # Outils individuels
        config.tools.enable_datetime = self._datetime_tool.isChecked()
        config.tools.enable_system_info = self._system_tool.isChecked()

        # API
        config.tools.enable_api_server = self._enable_api.isChecked()
        config.tools.api_port = self._api_port.value()
