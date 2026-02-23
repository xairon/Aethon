"""Dialog d'import d'un fichier WAV dans la bibliotheque de voix."""

import logging
import os
import wave

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QVBoxLayout,
)

from jarvis.gui.theme import (
    ACCENT, BG_SURFACE, BORDER_DEFAULT, TEXT, TEXT_INVERSE, TEXT_SECONDARY,
)

log = logging.getLogger(__name__)

# Langues Chatterbox : francais en premier, puis ordre alphabetique
LANGUAGES = [
    ("Francais", "fr"),
    ("Allemand", "de"),
    ("Anglais", "en"),
    ("Arabe", "ar"),
    ("Chinois", "zh"),
    ("Coreen", "ko"),
    ("Danois", "da"),
    ("Espagnol", "es"),
    ("Finnois", "fi"),
    ("Grec", "el"),
    ("Hebreu", "he"),
    ("Hindi", "hi"),
    ("Italien", "it"),
    ("Japonais", "ja"),
    ("Malais", "ms"),
    ("Neerlandais", "nl"),
    ("Norvegien", "no"),
    ("Polonais", "pl"),
    ("Portugais", "pt"),
    ("Russe", "ru"),
    ("Suedois", "sv"),
    ("Swahili", "sw"),
    ("Turc", "tr"),
]


class VoiceImportDialog(QDialog):
    """Dialogue modal pour importer un fichier WAV comme voix."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importer une voix")
        self.setMinimumWidth(400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        # Lecture des infos du fichier WAV
        duration, sample_rate = 0.0, 0
        try:
            with wave.open(file_path, "rb") as wf:
                sample_rate = wf.getframerate()
                duration = wf.getnframes() / sample_rate
        except Exception as exc:
            log.warning("Impossible de lire le WAV : %s", exc)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # -- Infos fichier (lecture seule) --
        info_label = QLabel("Fichier source")
        info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: 600;")
        layout.addWidget(info_label)

        info_form = QFormLayout()
        info_form.setSpacing(6)
        info_form.addRow("Fichier :", QLabel(os.path.basename(file_path)))
        info_form.addRow("Duree :", QLabel(f"{duration:.1f} s"))
        info_form.addRow("Sample rate :", QLabel(f"{sample_rate} Hz"))
        layout.addLayout(info_form)

        # -- Separateur --
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
        layout.addWidget(sep)

        # -- Champs editables --
        form = QFormLayout()
        form.setSpacing(10)

        self._name_edit = QLineEdit()
        stem = os.path.splitext(os.path.basename(file_path))[0]
        self._name_edit.setText(stem)
        form.addRow("Nom :", self._name_edit)

        self._lang_combo = QComboBox()
        for display, code in LANGUAGES:
            self._lang_combo.addItem(display, code)
        form.addRow("Langue :", self._lang_combo)

        # Genre : radio buttons
        gender_layout = QHBoxLayout()
        gender_layout.setSpacing(14)
        self._gender_group = QButtonGroup(self)
        for label, value in [("Homme", "male"), ("Femme", "female"), ("Inconnu", "unknown")]:
            rb = QRadioButton(label)
            rb.setProperty("gender_value", value)
            self._gender_group.addButton(rb)
            gender_layout.addWidget(rb)
            if value == "unknown":
                rb.setChecked(True)
        gender_layout.addStretch()
        form.addRow("Genre :", gender_layout)

        layout.addLayout(form)
        layout.addStretch()

        # -- Boutons --
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            f"background-color: {BG_SURFACE}; color: {TEXT_SECONDARY}; "
            f"border: 1px solid {BORDER_DEFAULT}; border-radius: 8px; padding: 8px 20px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        import_btn = QPushButton("Importer")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setStyleSheet(
            f"background-color: {ACCENT}; color: {TEXT_INVERSE}; "
            f"border: none; border-radius: 8px; padding: 8px 20px; font-weight: 600;"
        )
        import_btn.clicked.connect(self.accept)
        btn_row.addWidget(import_btn)

        layout.addLayout(btn_row)
        self.adjustSize()
        self.setFixedHeight(self.sizeHint().height())

    # ── API publique ──────────────────────────────────────────

    def get_result(self) -> dict | None:
        """Retourne les donnees saisies si accepte, None sinon."""
        if self.result() != QDialog.DialogCode.Accepted:
            return None
        checked = self._gender_group.checkedButton()
        return {
            "name": self._name_edit.text().strip(),
            "lang": self._lang_combo.currentData(),
            "gender": checked.property("gender_value") if checked else "unknown",
        }
