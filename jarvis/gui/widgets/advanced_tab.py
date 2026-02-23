"""Onglet Avancé — audio, transcription STT, mémoire."""

import logging
from pathlib import Path

import sounddevice as sd
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from jarvis.config import JarvisConfig

log = logging.getLogger(__name__)

# Modèles Whisper disponibles (du plus léger au plus lourd)
WHISPER_MODELS = [
    "tiny",
    "base",
    "small",
    "medium",
    "large-v2",
    "large-v3",
    "large-v3-turbo",
]


class AdvancedTab(QWidget):
    """Onglet Avancé : audio, STT et mémoire regroupés."""

    def __init__(self, config: JarvisConfig, parent=None):
        super().__init__(parent)
        self._config = config

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
        # Section Audio
        # ══════════════════════════════════════════
        audio_group = QGroupBox("Audio")
        audio_form = QFormLayout(audio_group)

        # Périphériques
        self._input_device = QComboBox()
        self._output_device = QComboBox()

        self._input_device.addItem("Défaut système", userData=None)
        self._output_device.addItem("Défaut système", userData=None)

        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                name = d["name"]
                if d["max_input_channels"] > 0:
                    self._input_device.addItem(name, userData=i)
                    if config.audio.input_device == i:
                        self._input_device.setCurrentIndex(
                            self._input_device.count() - 1
                        )
                if d["max_output_channels"] > 0:
                    self._output_device.addItem(name, userData=i)
                    if config.audio.output_device == i:
                        self._output_device.setCurrentIndex(
                            self._output_device.count() - 1
                        )
        except Exception as e:
            log.warning("Impossible d'énumérer les périphériques audio: %s", e)

        audio_form.addRow("Entrée (micro) :", self._input_device)
        audio_form.addRow("Sortie (HP) :", self._output_device)

        # Gain d'entrée
        self._input_gain = QDoubleSpinBox()
        self._input_gain.setRange(0.5, 20.0)
        self._input_gain.setSingleStep(0.5)
        self._input_gain.setDecimals(1)
        self._input_gain.setSuffix("x")
        self._input_gain.setValue(config.audio.input_gain)
        self._input_gain.setToolTip(
            "Multiplicateur de gain appliqué au signal micro.\n"
            "Augmenter si le micro capte trop faiblement."
        )
        audio_form.addRow("Gain d'entrée :", self._input_gain)

        # AGC automatique
        self._auto_gain = QCheckBox("Gain automatique (AGC)")
        self._auto_gain.setChecked(config.audio.auto_gain)
        self._auto_gain.setToolTip(
            "Ajuste automatiquement le gain pour atteindre un niveau\n"
            "audio cible. Recommandé pour les micros à faible niveau."
        )
        audio_form.addRow(self._auto_gain)

        agc_hint = QLabel(
            "<small><i>L'AGC compense les micros faibles en amplifiant "
            "automatiquement le signal.</i></small>"
        )
        agc_hint.setWordWrap(True)
        audio_form.addRow("", agc_hint)

        # Timing
        self._silence_timeout = QSpinBox()
        self._silence_timeout.setRange(300, 5000)
        self._silence_timeout.setSingleStep(100)
        self._silence_timeout.setSuffix(" ms")
        self._silence_timeout.setValue(config.audio.silence_timeout_ms)
        audio_form.addRow("Timeout silence :", self._silence_timeout)

        self._min_speech = QSpinBox()
        self._min_speech.setRange(100, 2000)
        self._min_speech.setSingleStep(50)
        self._min_speech.setSuffix(" ms")
        self._min_speech.setValue(config.audio.min_speech_ms)
        audio_form.addRow("Parole minimum :", self._min_speech)

        layout.addWidget(audio_group)

        # ══════════════════════════════════════════
        # Section Transcription (STT)
        # ══════════════════════════════════════════
        stt_group = QGroupBox("Transcription (STT)")
        stt_form = QFormLayout(stt_group)

        self._stt_model = QComboBox()
        self._stt_model.addItems(WHISPER_MODELS)
        self._stt_model.setCurrentText(config.stt.model)
        stt_form.addRow("Modèle :", self._stt_model)

        self._stt_device = QComboBox()
        self._stt_device.addItems(["cuda", "cpu"])
        self._stt_device.setCurrentText(config.stt.device)
        stt_form.addRow("Device :", self._stt_device)

        self._stt_compute = QComboBox()
        self._stt_compute.addItems(["float16", "int8", "float32"])
        self._stt_compute.setCurrentText(config.stt.compute_type)
        stt_form.addRow("Précision :", self._stt_compute)

        self._stt_lang = QComboBox()
        self._stt_lang.addItems(["fr", "en", "es", "de", "it", "pt", "ja", "zh"])
        self._stt_lang.setCurrentText(config.stt.language)
        stt_form.addRow("Langue :", self._stt_lang)

        layout.addWidget(stt_group)

        # ══════════════════════════════════════════
        # Section Mémoire
        # ══════════════════════════════════════════
        memory_group = QGroupBox("Mémoire longue (SQLite)")
        memory_form = QFormLayout(memory_group)

        self._mem_enabled = QCheckBox("Activée")
        self._mem_enabled.setChecked(config.memory.enabled)
        self._mem_enabled.toggled.connect(self._on_memory_toggled)
        memory_form.addRow(self._mem_enabled)

        self._max_memories = QSpinBox()
        self._max_memories.setRange(1, 50)
        self._max_memories.setValue(config.memory.max_context_memories)
        memory_form.addRow("Mémoires en contexte :", self._max_memories)

        self._max_turns = QSpinBox()
        self._max_turns.setRange(5, 100)
        self._max_turns.setValue(config.memory.max_conversation_turns)
        memory_form.addRow("Tours de conversation max :", self._max_turns)

        # Bouton reset
        reset_row = QHBoxLayout()
        self._reset_btn = QPushButton("Réinitialiser la mémoire")
        self._reset_btn.setFixedWidth(220)
        self._reset_btn.clicked.connect(self._reset_memory)
        reset_row.addWidget(self._reset_btn)
        reset_row.addStretch()
        memory_form.addRow("", reset_row)

        self._on_memory_toggled(config.memory.enabled)

        layout.addWidget(memory_group)
        layout.addStretch()

    # ── Toggle mémoire ──

    def _on_memory_toggled(self, enabled: bool):
        """Active/désactive les champs mémoire."""
        self._max_memories.setEnabled(enabled)
        self._max_turns.setEnabled(enabled)

    # ── Reset mémoire ──

    def _reset_memory(self):
        """Supprime la base de données de mémoire après confirmation."""
        reply = QMessageBox.question(
            self,
            "Réinitialiser la mémoire",
            "Supprimer tous les souvenirs ? Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db_path = Path(self._config.memory.db_path)
            if db_path.exists():
                try:
                    db_path.unlink()
                except PermissionError:
                    log.warning("Impossible de supprimer la BDD — pipeline actif ?")
                    QMessageBox.warning(
                        self, "Mémoire",
                        "Impossible de supprimer la base de données.\n"
                        "Arrêtez le pipeline d'abord."
                    )
                    return
                log.info("Mémoire réinitialisée.")
                QMessageBox.information(
                    self, "Mémoire", "Mémoire supprimée avec succès."
                )
            else:
                QMessageBox.information(
                    self, "Mémoire", "Aucune base de données trouvée."
                )

    # ── Application des changements ──

    def apply(self, config: JarvisConfig):
        """Applique les valeurs du formulaire à la config."""
        # Audio
        config.audio.input_device = self._input_device.currentData()
        config.audio.output_device = self._output_device.currentData()
        config.audio.input_gain = self._input_gain.value()
        config.audio.auto_gain = self._auto_gain.isChecked()
        config.audio.silence_timeout_ms = self._silence_timeout.value()
        config.audio.min_speech_ms = self._min_speech.value()

        # STT
        config.stt.model = self._stt_model.currentText()
        config.stt.device = self._stt_device.currentText()
        config.stt.compute_type = self._stt_compute.currentText()
        config.stt.language = self._stt_lang.currentText()

        # Mémoire
        config.memory.enabled = self._mem_enabled.isChecked()
        config.memory.max_context_memories = self._max_memories.value()
        config.memory.max_conversation_turns = self._max_turns.value()
