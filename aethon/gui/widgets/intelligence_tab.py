"""Onglet Intelligence — backend LLM, paramètres Gemini/Ollama."""

import logging

import httpx
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from aethon.config import AethonConfig

log = logging.getLogger(__name__)

# Modèles Gemini disponibles
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


class _ModelFetcher(QThread):
    """Récupère la liste des modèles Ollama en arrière-plan."""

    models_ready = pyqtSignal(list)

    def __init__(self, base_url: str, parent=None):
        super().__init__(parent)
        self._base_url = base_url

    def run(self):
        try:
            r = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                self.models_ready.emit(models)
        except Exception:
            log.debug("Impossible de récupérer les modèles Ollama")


class IntelligenceTab(QWidget):
    """Onglet Intelligence : choix du backend LLM et paramètres."""

    def __init__(self, config: AethonConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._fetcher: _ModelFetcher | None = None

        # --- Conteneur scrollable ---
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)
        scroll.setWidget(container)

        # ══════════════════════════════════════════
        # Section Backend
        # ══════════════════════════════════════════
        backend_group = QGroupBox("Backend")
        backend_layout = QHBoxLayout(backend_group)

        self._radio_gemini = QRadioButton("Gemini (Cloud)")
        self._radio_ollama = QRadioButton("Ollama (Local)")

        self._backend_group = QButtonGroup(self)
        self._backend_group.addButton(self._radio_gemini, 0)
        self._backend_group.addButton(self._radio_ollama, 1)

        if config.llm.backend == "ollama":
            self._radio_ollama.setChecked(True)
        else:
            self._radio_gemini.setChecked(True)

        backend_layout.addWidget(self._radio_gemini)
        backend_layout.addWidget(self._radio_ollama)
        backend_layout.addStretch()

        self._radio_gemini.toggled.connect(self._on_backend_changed)
        self._radio_ollama.toggled.connect(self._on_backend_changed)

        layout.addWidget(backend_group)

        # ══════════════════════════════════════════
        # Section Gemini
        # ══════════════════════════════════════════
        self._gemini_group = QGroupBox("Gemini")
        gemini_form = QFormLayout(self._gemini_group)

        self._gemini_model = QComboBox()
        self._gemini_model.addItems(GEMINI_MODELS)
        self._gemini_model.setCurrentText(config.llm.model)
        gemini_form.addRow("Modèle :", self._gemini_model)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("Cl\u00e9 API Google AI Studio")
        self._api_key.setText(config.llm.api_key or "")
        gemini_form.addRow("Cl\u00e9 API :", self._api_key)

        self._thinking_budget = QSpinBox()
        self._thinking_budget.setRange(0, 24576)
        self._thinking_budget.setSingleStep(1024)
        self._thinking_budget.setValue(getattr(config.llm, "thinking_budget", 0))
        self._thinking_budget.setSpecialValueText("D\u00e9sactiv\u00e9")
        self._thinking_budget.setToolTip(
            "Budget de tokens pour le raisonnement Gemini 2.5.\n"
            "0 = d\u00e9sactiv\u00e9 (r\u00e9duit la latence de 1-3s).\n"
            "1024+ = active le raisonnement \u00e9tendu."
        )
        gemini_form.addRow("Budget thinking :", self._thinking_budget)

        layout.addWidget(self._gemini_group)

        # ══════════════════════════════════════════
        # Section Ollama
        # ══════════════════════════════════════════
        self._ollama_group = QGroupBox("Ollama")
        ollama_form = QFormLayout(self._ollama_group)

        # Modèle Ollama avec rafraîchissement
        model_row = QHBoxLayout()
        self._ollama_model = QComboBox()
        self._ollama_model.setEditable(True)
        self._ollama_model.setCurrentText(config.llm.ollama_model)
        model_row.addWidget(self._ollama_model)

        refresh_btn = QPushButton("Rafraîchir")
        refresh_btn.setFixedWidth(90)
        refresh_btn.clicked.connect(self._fetch_models_async)
        model_row.addWidget(refresh_btn)
        ollama_form.addRow("Modèle :", model_row)

        self._base_url = QLineEdit(config.llm.base_url)
        self._base_url.setPlaceholderText("http://localhost:11434")
        ollama_form.addRow("URL :", self._base_url)

        layout.addWidget(self._ollama_group)

        # ══════════════════════════════════════════
        # Section Commune
        # ══════════════════════════════════════════
        common_group = QGroupBox("Paramètres communs")
        common_form = QFormLayout(common_group)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.1)
        self._temperature.setDecimals(2)
        self._temperature.setValue(config.llm.temperature)
        common_form.addRow("Température :", self._temperature)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(50, 4096)
        self._max_tokens.setSingleStep(50)
        self._max_tokens.setValue(config.llm.max_tokens)
        common_form.addRow("Tokens max :", self._max_tokens)

        layout.addWidget(common_group)
        layout.addStretch()

        # --- État initial des groupes ---
        self._on_backend_changed()

        # --- Auto-fetch des modèles Ollama ---
        self._fetch_models_async()

    # ── Affichage conditionnel Gemini/Ollama ──

    def _on_backend_changed(self):
        """Affiche ou masque les sections selon le backend sélectionné."""
        is_gemini = self._radio_gemini.isChecked()
        self._gemini_group.setVisible(is_gemini)
        self._ollama_group.setVisible(not is_gemini)

    # ── Récupération des modèles Ollama ──

    def _fetch_models_async(self):
        """Lance la récupération asynchrone des modèles Ollama."""
        url = self._base_url.text().strip() or "http://localhost:11434"
        self._fetcher = _ModelFetcher(url, parent=self)
        self._fetcher.models_ready.connect(self._on_models_received)
        self._fetcher.start()

    def _on_models_received(self, models: list[str]):
        """Met à jour la liste déroulante avec les modèles récupérés."""
        current = self._ollama_model.currentText()
        self._ollama_model.clear()
        self._ollama_model.addItems(models)
        if current in models:
            self._ollama_model.setCurrentText(current)
        elif models:
            self._ollama_model.setCurrentIndex(0)
        self._fetcher = None

    # ── Application des changements ──

    def apply(self, config: AethonConfig):
        """Applique les valeurs du formulaire à la config."""
        # Backend
        if self._radio_ollama.isChecked():
            config.llm.backend = "ollama"
        else:
            config.llm.backend = "gemini"

        # Gemini
        config.llm.model = self._gemini_model.currentText()
        config.llm.api_key = self._api_key.text().strip()
        config.llm.thinking_budget = self._thinking_budget.value()
        # Ollama
        config.llm.ollama_model = self._ollama_model.currentText().strip()
        config.llm.base_url = self._base_url.text().strip() or "http://localhost:11434"

        # Commun
        config.llm.temperature = self._temperature.value()
        config.llm.max_tokens = self._max_tokens.value()
