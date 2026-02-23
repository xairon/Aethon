"""Onglet Persona — identite, voix, instructions de l'assistant."""

import logging
import os

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jarvis.config import JarvisConfig, Instruction
from jarvis.gui.theme import (
    ACCENT, BG_ELEVATED, BG_RAISED, BG_SURFACE,
    BORDER_DEFAULT, GREEN, TEXT, TEXT_INVERSE, TEXT_SECONDARY,
)
from jarvis.voices.library import VoiceLibrary, VoiceMeta

log = logging.getLogger(__name__)

# Voix Kokoro : (nom affiché, code langue, identifiant)
KOKORO_VOICES = [
    ("Siwis (FR, femme)", "f", "ff_siwis"),
    ("Heart (EN, femme)", "a", "af_heart"),
    ("Bella (EN, femme)", "a", "af_bella"),
    ("Nicole (EN, femme)", "a", "af_nicole"),
    ("Sarah (EN, femme)", "a", "af_sarah"),
    ("Sky (EN, femme)", "a", "af_sky"),
    ("Alloy (EN, homme)", "a", "am_alloy"),
    ("Echo (EN, homme)", "a", "am_echo"),
    ("Michael (EN, homme)", "a", "am_michael"),
    ("Puck (EN, homme)", "a", "am_puck"),
]

# Modèles de wake word disponibles
WAKE_MODELS = ["hey_jarvis", "alexa", "hey_mycroft", "ok_google"]


class _KokoroPreviewWorker(QThread):
    """Prévisualisation TTS Kokoro dans un thread séparé."""

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, lang: str, voice: str, speed: float, parent=None):
        super().__init__(parent)
        self._lang = lang
        self._voice = voice
        self._speed = speed

    def run(self):
        try:
            from kokoro import KPipeline
            import torch

            sample = (
                "Bonjour, je suis votre assistant."
                if self._lang == "f"
                else "Hello, I am your assistant."
            )
            with torch.device("cpu"):
                pipe = KPipeline(lang_code=self._lang, device="cpu")
            chunks = []
            for _gs, _ps, audio in pipe(
                sample, voice=self._voice, speed=self._speed
            ):
                if audio is not None:
                    chunks.append(audio)
            if chunks:
                audio_full = np.concatenate(chunks)
                sd.play(audio_full, samplerate=24000)
                sd.wait()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class _ChatterboxPreviewWorker(QThread):
    """Prévisualisation TTS Chatterbox dans un thread séparé — tous paramètres."""

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self._params = params

    def run(self):
        try:
            import torch

            # Vérifier qu'il y a assez de VRAM avant de charger un 2e modèle
            if torch.cuda.is_available():
                free_vram = torch.cuda.mem_get_info()[0] / (1024 ** 3)  # GB
                if free_vram < 3.0:
                    self.error.emit(
                        f"VRAM insuffisante ({free_vram:.1f} GB libre). "
                        "Arrêtez le pipeline avant de faire un preview Chatterbox."
                    )
                    return

            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            p = self._params
            log.info("Chatterbox preview: chargement du modèle...")
            model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")

            sample = (
                "Bonjour, je suis votre assistant vocal."
                if p["language"] == "fr"
                else "Hello, I am your voice assistant."
            )

            kwargs = {"language_id": p["language"]}
            if p.get("ref_audio") and os.path.exists(p["ref_audio"]):
                kwargs["audio_prompt_path"] = p["ref_audio"]

            kwargs["exaggeration"] = p.get("exaggeration", 0.5)
            kwargs["cfg_weight"] = p.get("cfg_weight", 0.5)
            kwargs["temperature"] = p.get("temperature", 0.8)
            kwargs["repetition_penalty"] = p.get("repetition_penalty", 2.0)
            kwargs["top_p"] = p.get("top_p", 1.0)
            kwargs["min_p"] = p.get("min_p", 0.05)

            seed = p.get("seed", -1)
            if seed >= 0:
                import torch as _torch
                _torch.manual_seed(seed)

            wav = model.generate(sample, **kwargs)

            if wav is not None:
                audio = wav.squeeze().cpu().numpy().astype(np.float32)
                sd.play(audio, samplerate=model.sr)
                sd.wait()

            del model
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class _VoicePreviewWorker(QThread):
    """Joue un fichier audio de voix dans un thread separe."""

    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, wav_path: str, parent=None):
        super().__init__(parent)
        self._path = wav_path

    def run(self):
        try:
            import wave as _wave
            with _wave.open(self._path, "rb") as wf:
                sr = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(audio, samplerate=sr)
            sd.wait()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class _VoiceListItem(QWidget):
    """Widget custom pour un item de la liste de voix locale."""

    play_clicked = pyqtSignal(str)   # voice_id
    delete_clicked = pyqtSignal(str)  # voice_id

    def __init__(self, meta: VoiceMeta, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.voice_id = meta.id
        self._meta = meta

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Nom (gras)
        name_lbl = QLabel(meta.name)
        name_lbl.setStyleSheet(f"font-weight: bold; color: {TEXT}; font-size: 13px;")
        layout.addWidget(name_lbl)

        # Tags (langue | genre | duree | source)
        gender_map = {"male": "homme", "female": "femme", "unknown": ""}
        parts = [meta.lang]
        if meta.gender in gender_map and gender_map[meta.gender]:
            parts.append(gender_map[meta.gender])
        if meta.duration_s > 0:
            parts.append(f"{meta.duration_s:.1f}s")
        parts.append(meta.source)
        tags_lbl = QLabel(" | ".join(parts))
        tags_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(tags_lbl)

        layout.addStretch()

        # Bouton play
        play_btn = QPushButton("\u25b6")
        play_btn.setFixedSize(28, 28)
        play_btn.setToolTip("Ecouter cette voix")
        play_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 6px; color: {TEXT}; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {BG_ELEVATED}; }}"
        )
        play_btn.clicked.connect(lambda: self.play_clicked.emit(meta.id))
        layout.addWidget(play_btn)

        # Bouton delete (seulement pour les voix locales, pas kyutai)
        if meta.source == "local":
            del_btn = QPushButton("\u2715")
            del_btn.setFixedSize(28, 28)
            del_btn.setToolTip("Supprimer cette voix")
            del_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {BORDER_DEFAULT}; "
                f"border-radius: 6px; color: {TEXT_SECONDARY}; font-size: 11px; }}"
                f"QPushButton:hover {{ background: {BG_ELEVATED}; color: #f87171; }}"
            )
            del_btn.clicked.connect(lambda: self.delete_clicked.emit(meta.id))
            layout.addWidget(del_btn)

        # Style actif
        if is_active:
            self.setStyleSheet(
                f"_VoiceListItem {{ border-left: 3px solid {ACCENT}; "
                f"background: {BG_RAISED}; }}"
            )


class PersonaTab(QWidget):
    """Onglet Persona : identite, voix et instructions."""

    def __init__(self, config: JarvisConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._preview_worker: QThread | None = None
        self._instruction_checkboxes: list[tuple[Instruction, QCheckBox]] = []

        # Bibliotheque de voix
        self._voice_library = VoiceLibrary(config.persona.voices_path)
        self._voices: list[VoiceMeta] = []
        self._selected_voice_id: str = config.persona.active_voice_id or ""

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
        # Section Identité
        # ══════════════════════════════════════════
        identity_group = QGroupBox("Identité")
        identity_form = QFormLayout(identity_group)

        self._name = QLineEdit(config.persona.name)
        self._name.setPlaceholderText("Nom de l'assistant")
        identity_form.addRow("Nom :", self._name)

        self._language = QComboBox()
        self._language.addItem("Français", "fr")
        self._language.addItem("English", "en")
        for i in range(self._language.count()):
            if self._language.itemData(i) == config.persona.language:
                self._language.setCurrentIndex(i)
                break
        identity_form.addRow("Langue :", self._language)

        # Wake word
        self._wake_enabled = QCheckBox("Activé")
        self._wake_enabled.setChecked(config.persona.wake_enabled)
        self._wake_enabled.toggled.connect(self._on_wake_toggled)
        identity_form.addRow("Wake word :", self._wake_enabled)

        # Mode de détection
        self._wake_mode = QComboBox()
        self._wake_mode.addItem("OpenWakeWord (rapide)", "openwakeword")
        self._wake_mode.addItem("Whisper (phrase libre)", "whisper")
        for i in range(self._wake_mode.count()):
            if self._wake_mode.itemData(i) == config.persona.wake_mode:
                self._wake_mode.setCurrentIndex(i)
                break
        self._wake_mode.currentIndexChanged.connect(self._on_wake_mode_changed)
        identity_form.addRow("Mode :", self._wake_mode)

        # Phrase : stack OpenWakeWord (combo) / Whisper (texte libre)
        self._phrase_stack = QStackedWidget()

        self._wake_phrase = QComboBox()
        self._wake_phrase.setEditable(True)
        self._wake_phrase.addItems(WAKE_MODELS)
        self._wake_phrase.setCurrentText(config.persona.wake_phrase)
        self._phrase_stack.addWidget(self._wake_phrase)

        self._whisper_phrase = QLineEdit()
        self._whisper_phrase.setPlaceholderText("Ex: Salut Jarvis, Bonjour assistant...")
        if config.persona.wake_mode == "whisper":
            self._whisper_phrase.setText(config.persona.wake_phrase)
        else:
            self._whisper_phrase.setText(
                config.persona.wake_phrase.replace("_", " ")
            )
        self._phrase_stack.addWidget(self._whisper_phrase)

        identity_form.addRow("Phrase :", self._phrase_stack)

        self._wake_threshold = QDoubleSpinBox()
        self._wake_threshold.setRange(0.1, 0.99)
        self._wake_threshold.setSingleStep(0.05)
        self._wake_threshold.setDecimals(2)
        self._wake_threshold.setValue(config.persona.wake_threshold)
        identity_form.addRow("Seuil :", self._wake_threshold)

        self._whisper_hint = QLabel(
            "<small><i>Whisper transcrit la parole et compare au texte ci-dessus. "
            "Fonctionne avec n'importe quelle phrase, en français ou anglais.</i></small>"
        )
        self._whisper_hint.setWordWrap(True)
        identity_form.addRow("", self._whisper_hint)

        self._on_wake_toggled(config.persona.wake_enabled)
        self._on_wake_mode_changed(self._wake_mode.currentIndex())

        layout.addWidget(identity_group)

        # ══════════════════════════════════════════
        # Section Voix
        # ══════════════════════════════════════════
        voice_group = QGroupBox("Voix")
        voice_layout = QVBoxLayout(voice_group)

        # Backend TTS — Kokoro (CPU) ou Chatterbox (GPU)
        backend_row = QHBoxLayout()
        backend_label = QLabel("Backend TTS :")
        backend_row.addWidget(backend_label)
        self._radio_kokoro = QRadioButton("Kokoro (CPU)")
        self._radio_chatterbox = QRadioButton("Chatterbox (GPU)")
        if config.persona.tts_backend == "chatterbox":
            self._radio_chatterbox.setChecked(True)
        else:
            self._radio_kokoro.setChecked(True)
        backend_row.addWidget(self._radio_kokoro)
        backend_row.addWidget(self._radio_chatterbox)
        backend_row.addStretch()
        voice_layout.addLayout(backend_row)

        # --- Sous-groupe Kokoro ---
        self._kokoro_group = QGroupBox("Kokoro (CPU)")
        kokoro_form = QFormLayout(self._kokoro_group)

        self._voice = QComboBox()
        for display, lang, vid in KOKORO_VOICES:
            self._voice.addItem(display, userData=(lang, vid))
        for i, (_, lang, vid) in enumerate(KOKORO_VOICES):
            if vid == config.persona.voice_id:
                self._voice.setCurrentIndex(i)
                break
        kokoro_form.addRow("Voix :", self._voice)

        voice_layout.addWidget(self._kokoro_group)

        # --- Sous-groupe Chatterbox ---
        self._chatterbox_group = QGroupBox(
            "Chatterbox (GPU) — Resemble AI, #1 TTS Arena"
        )
        cb_layout = QVBoxLayout(self._chatterbox_group)

        cb_info = QLabel(
            "<small><i>TTS multilingue SOTA (23 langues, français natif). "
            "Clonage de voix zero-shot avec quelques secondes d'audio de référence. "
            "Contrôle complet : expressivité, sampling, reproductibilité.</i></small>"
        )
        cb_info.setWordWrap(True)
        cb_layout.addWidget(cb_info)

        # ── Bibliotheque de voix ──
        lib_group = QGroupBox("Bibliotheque de voix")
        lib_layout = QVBoxLayout(lib_group)

        # Label voix active
        self._active_voice_label = QLabel("Aucune voix selectionnee")
        self._active_voice_label.setStyleSheet(
            f"background: {BG_ELEVATED}; border-radius: 6px; padding: 8px 12px; "
            f"color: {TEXT}; font-weight: bold; font-size: 13px;"
        )
        lib_layout.addWidget(self._active_voice_label)

        # Liste des voix locales
        self._voice_list = QListWidget()
        self._voice_list.setMaximumHeight(220)
        self._voice_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._voice_list.setStyleSheet(
            f"QListWidget {{ background: {BG_SURFACE}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 6px; }}"
            f"QListWidget::item {{ border-bottom: 1px solid {BORDER_DEFAULT}; padding: 2px; }}"
            f"QListWidget::item:selected {{ background: {BG_RAISED}; }}"
            f"QListWidget::item:hover {{ background: {BG_ELEVATED}; }}"
        )
        self._voice_list.itemClicked.connect(self._on_voice_item_clicked)
        lib_layout.addWidget(self._voice_list)

        # Boutons : Importer + Telecharger depuis HF
        lib_btn_row = QHBoxLayout()
        lib_btn_row.setSpacing(10)

        self._import_btn = QPushButton("Importer un WAV")
        self._import_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: 8px; padding: 7px 16px; color: {TEXT}; font-weight: 500; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}"
        )
        self._import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_btn.clicked.connect(self._import_wav)
        lib_btn_row.addWidget(self._import_btn)

        self._hf_btn = QPushButton("Telecharger depuis HF")
        self._hf_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: {TEXT_INVERSE}; border: none; "
            f"border-radius: 8px; padding: 7px 16px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: #6aa0ff; }}"
        )
        self._hf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hf_btn.clicked.connect(self._open_hf_browser)
        lib_btn_row.addWidget(self._hf_btn)

        lib_btn_row.addStretch()
        lib_layout.addLayout(lib_btn_row)

        lib_hint = QLabel(
            "<small><i>Selectionnez une voix pour le clonage zero-shot. "
            "Sans voix, Chatterbox utilise sa voix par defaut.</i></small>"
        )
        lib_hint.setWordWrap(True)
        lib_layout.addWidget(lib_hint)

        cb_layout.addWidget(lib_group)

        # Charger la liste des voix
        self._refresh_voice_list()

        # ── Expressivité & Prosodie ──
        expr_group = QGroupBox("Expressivité && Prosodie")
        expr_form = QFormLayout(expr_group)

        # Expressivité (exaggeration)
        self._cb_exaggeration = QDoubleSpinBox()
        self._cb_exaggeration.setRange(0.0, 2.0)
        self._cb_exaggeration.setSingleStep(0.05)
        self._cb_exaggeration.setDecimals(2)
        self._cb_exaggeration.setValue(config.tts.chatterbox_exaggeration)
        self._cb_exaggeration.setToolTip(
            "Expressivité émotionnelle de la voix.\n"
            "0.25 = neutre et posé\n"
            "0.50 = normal (défaut)\n"
            "0.70 = dramatique et vivant\n"
            "2.00 = maximum (peut être instable)"
        )
        expr_form.addRow("Expressivité :", self._cb_exaggeration)

        # Adhérence (cfg_weight)
        self._cb_cfg_weight = QDoubleSpinBox()
        self._cb_cfg_weight.setRange(0.0, 1.0)
        self._cb_cfg_weight.setSingleStep(0.05)
        self._cb_cfg_weight.setDecimals(2)
        self._cb_cfg_weight.setValue(config.tts.chatterbox_cfg_weight)
        self._cb_cfg_weight.setToolTip(
            "Classifier-Free Guidance — contrôle le pacing et l'adhérence.\n"
            "0.00 = libre (recommandé pour transfert cross-langue)\n"
            "0.30 = rapide et naturel\n"
            "0.50 = équilibré (défaut)\n"
            "1.00 = strict (colle au maximum à la référence)\n\n"
            "Astuce : mettre à 0 quand la langue de la ref audio\n"
            "diffère de la langue cible (évite l'accent bleed)."
        )
        expr_form.addRow("Adhérence (CFG) :", self._cb_cfg_weight)

        cb_layout.addWidget(expr_group)

        # ── Paramètres de sampling ──
        sampling_group = QGroupBox("Sampling")
        sampling_form = QFormLayout(sampling_group)

        # Temperature
        self._cb_temperature = QDoubleSpinBox()
        self._cb_temperature.setRange(0.1, 2.0)
        self._cb_temperature.setSingleStep(0.05)
        self._cb_temperature.setDecimals(2)
        self._cb_temperature.setValue(config.tts.chatterbox_temperature)
        self._cb_temperature.setToolTip(
            "Température de sampling.\n"
            "Plus bas = voix plus prévisible et stable.\n"
            "Plus haut = plus de variation et de naturel.\n"
            "0.80 = défaut recommandé."
        )
        sampling_form.addRow("Température :", self._cb_temperature)

        # Repetition penalty
        self._cb_rep_penalty = QDoubleSpinBox()
        self._cb_rep_penalty.setRange(1.0, 5.0)
        self._cb_rep_penalty.setSingleStep(0.1)
        self._cb_rep_penalty.setDecimals(1)
        self._cb_rep_penalty.setValue(config.tts.chatterbox_repetition_penalty)
        self._cb_rep_penalty.setToolTip(
            "Pénalité de répétition — évite les boucles et bégaiements.\n"
            "1.0 = pas de pénalité\n"
            "2.0 = défaut multilingual (recommandé)\n"
            "Plus haut = moins de répétitions mais peut dégrader la qualité."
        )
        sampling_form.addRow("Anti-répétition :", self._cb_rep_penalty)

        # Top-P (nucleus)
        self._cb_top_p = QDoubleSpinBox()
        self._cb_top_p.setRange(0.1, 1.0)
        self._cb_top_p.setSingleStep(0.05)
        self._cb_top_p.setDecimals(2)
        self._cb_top_p.setValue(config.tts.chatterbox_top_p)
        self._cb_top_p.setToolTip(
            "Nucleus sampling (Top-P).\n"
            "1.0 = désactivé (recommandé par Resemble AI)\n"
            "Plus bas = choix de tokens plus restreints.\n"
            "Min-P est préféré à Top-P pour Chatterbox."
        )
        sampling_form.addRow("Top-P :", self._cb_top_p)

        # Min-P
        self._cb_min_p = QDoubleSpinBox()
        self._cb_min_p.setRange(0.0, 0.5)
        self._cb_min_p.setSingleStep(0.01)
        self._cb_min_p.setDecimals(2)
        self._cb_min_p.setValue(config.tts.chatterbox_min_p)
        self._cb_min_p.setToolTip(
            "Min-P sampling — filtre les tokens peu probables.\n"
            "0.00 = désactivé\n"
            "0.05 = défaut (recommandé)\n"
            "0.02-0.10 = plage recommandée\n"
            "Gère mieux les hautes températures que Top-P."
        )
        sampling_form.addRow("Min-P :", self._cb_min_p)

        cb_layout.addWidget(sampling_group)

        # ── Reproductibilité ──
        repro_group = QGroupBox("Reproductibilité")
        repro_form = QFormLayout(repro_group)

        self._cb_seed = QSpinBox()
        self._cb_seed.setRange(-1, 999999999)
        self._cb_seed.setValue(config.tts.chatterbox_seed)
        self._cb_seed.setToolTip(
            "Seed pour rendre la génération reproductible.\n"
            "-1 = aléatoire (défaut)\n"
            "Tout autre nombre = résultat identique à chaque fois\n"
            "pour le même texte et les mêmes paramètres."
        )
        repro_form.addRow("Seed :", self._cb_seed)

        seed_hint = QLabel(
            "<small><i>-1 = aléatoire. Fixer un seed pour reproduire "
            "exactement le même résultat.</i></small>"
        )
        seed_hint.setWordWrap(True)
        repro_form.addRow("", seed_hint)

        cb_layout.addWidget(repro_group)

        voice_layout.addWidget(self._chatterbox_group)

        # --- Paramètres communs ---
        common_form = QFormLayout()

        self._speed = QDoubleSpinBox()
        self._speed.setRange(0.5, 2.0)
        self._speed.setSingleStep(0.1)
        self._speed.setDecimals(1)
        self._speed.setValue(config.persona.voice_speed)
        common_form.addRow("Vitesse :", self._speed)

        preview_row = QHBoxLayout()
        self._preview_btn = QPushButton("Preview voix")
        self._preview_btn.setFixedWidth(150)
        self._preview_btn.clicked.connect(self._preview)
        preview_row.addWidget(self._preview_btn)
        preview_row.addStretch()
        common_form.addRow("", preview_row)

        voice_layout.addLayout(common_form)

        # Connecter les radios
        self._radio_kokoro.toggled.connect(lambda: self._on_tts_backend_changed())
        self._radio_chatterbox.toggled.connect(lambda: self._on_tts_backend_changed())
        self._on_tts_backend_changed()

        layout.addWidget(voice_group)

        # ══════════════════════════════════════════
        # Section Instructions
        # ══════════════════════════════════════════
        instr_group = QGroupBox("Instructions")
        instr_layout = QVBoxLayout(instr_group)

        instr_desc = QLabel(
            "Sélectionnez les instructions actives pour le system prompt :"
        )
        instr_desc.setWordWrap(True)
        instr_layout.addWidget(instr_desc)

        self._instruction_checkboxes = []
        for instr in config.persona.instructions:
            cb = QCheckBox(instr.label)
            cb.setChecked(instr.enabled)
            cb.setToolTip(instr.content)
            instr_layout.addWidget(cb)
            self._instruction_checkboxes.append((instr, cb))

        add_row = QHBoxLayout()
        self._add_instr_btn = QPushButton("+ Ajouter une instruction")
        self._add_instr_btn.setFixedWidth(220)
        self._add_instr_btn.clicked.connect(self._add_custom_instruction)
        add_row.addWidget(self._add_instr_btn)
        add_row.addStretch()
        instr_layout.addLayout(add_row)

        instr_layout.addSpacing(8)
        override_label = QLabel("Override du system prompt (vide = auto-généré) :")
        override_label.setWordWrap(True)
        instr_layout.addWidget(override_label)

        self._prompt_override = QTextEdit()
        self._prompt_override.setPlaceholderText(
            "Laissez vide pour utiliser le prompt auto-généré depuis les instructions..."
        )
        self._prompt_override.setPlainText(
            config.llm.system_prompt_override or ""
        )
        self._prompt_override.setMinimumHeight(80)
        self._prompt_override.setMaximumHeight(120)
        instr_layout.addWidget(self._prompt_override)

        layout.addWidget(instr_group)
        layout.addStretch()

    # ── Wake word toggle ──

    def _on_wake_toggled(self, enabled: bool):
        self._wake_mode.setEnabled(enabled)
        self._phrase_stack.setEnabled(enabled)
        is_whisper = self._wake_mode.currentData() == "whisper"
        self._wake_threshold.setEnabled(enabled and not is_whisper)

    def _on_wake_mode_changed(self, index: int):
        mode = self._wake_mode.currentData()
        is_whisper = (mode == "whisper")
        self._phrase_stack.setCurrentIndex(1 if is_whisper else 0)
        self._wake_threshold.setVisible(not is_whisper)
        self._whisper_hint.setVisible(is_whisper)
        enabled = self._wake_enabled.isChecked()
        self._wake_threshold.setEnabled(enabled and not is_whisper)

    # ── TTS backend toggle ──

    def _on_tts_backend_changed(self):
        is_kokoro = self._radio_kokoro.isChecked()
        self._kokoro_group.setVisible(is_kokoro)
        self._chatterbox_group.setVisible(not is_kokoro)

    # ── Voice library ──

    def _refresh_voice_list(self):
        """Re-scanne le dossier voices/ et met a jour la QListWidget."""
        self._voices = self._voice_library.scan_local()
        self._voice_list.clear()

        for meta in self._voices:
            is_active = meta.id == self._selected_voice_id
            item_widget = _VoiceListItem(meta, is_active=is_active)
            item_widget.play_clicked.connect(self._play_voice)
            item_widget.delete_clicked.connect(self._delete_voice)

            item = QListWidgetItem(self._voice_list)
            item.setSizeHint(item_widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, meta.id)
            self._voice_list.addItem(item)
            self._voice_list.setItemWidget(item, item_widget)

            if is_active:
                self._voice_list.setCurrentItem(item)

        self._update_active_label()

    def _on_voice_item_clicked(self, item: QListWidgetItem):
        """Selection d'une voix dans la liste."""
        voice_id = item.data(Qt.ItemDataRole.UserRole)
        if voice_id:
            self._selected_voice_id = voice_id
            self._refresh_voice_list()

    def _update_active_label(self):
        """Met a jour le label de la voix active."""
        if not self._selected_voice_id:
            self._active_voice_label.setText(
                "Aucune voix selectionnee (voix par defaut)"
            )
            return
        for v in self._voices:
            if v.id == self._selected_voice_id:
                gender_map = {"male": "homme", "female": "femme", "unknown": ""}
                parts = [v.lang]
                g = gender_map.get(v.gender, "")
                if g:
                    parts.append(g)
                if v.duration_s > 0:
                    parts.append(f"{v.duration_s:.1f}s")
                self._active_voice_label.setText(
                    f"{v.name}  ({' | '.join(parts)})"
                )
                return
        self._active_voice_label.setText(
            "Voix introuvable — selectionnez-en une"
        )
        self._selected_voice_id = ""

    def _play_voice(self, voice_id: str):
        """Joue le fichier audio d'une voix."""
        if self._preview_worker is not None:
            return
        path = self._voice_library.get_voice_path(voice_id)
        if not path:
            return
        self._preview_worker = _VoicePreviewWorker(path, parent=self)
        self._preview_worker.finished.connect(self._on_preview_done)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _delete_voice(self, voice_id: str):
        """Supprime une voix apres confirmation."""
        reply = QMessageBox.question(
            self,
            "Supprimer la voix",
            "Supprimer cette voix de la bibliotheque ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._voice_library.delete_voice(voice_id):
                if self._selected_voice_id == voice_id:
                    self._selected_voice_id = ""
                self._refresh_voice_list()

    def _import_wav(self):
        """Ouvre un dialog pour importer un fichier WAV."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selectionner un fichier audio",
            "",
            "Audio WAV (*.wav);;Tous (*)",
        )
        if not path:
            return

        from jarvis.gui.widgets.voice_import_dialog import VoiceImportDialog

        dlg = VoiceImportDialog(path, parent=self)
        if dlg.exec() == VoiceImportDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result:
                meta = self._voice_library.import_wav(
                    path, result["name"], result["lang"], result["gender"]
                )
                self._selected_voice_id = meta.id
                self._refresh_voice_list()

    def _open_hf_browser(self):
        """Ouvre le navigateur de voix HuggingFace."""
        from jarvis.gui.widgets.voice_browser import VoiceBrowserDialog

        dlg = VoiceBrowserDialog(self._voice_library, parent=self)
        dlg.voices_changed.connect(self._refresh_voice_list)
        dlg.exec()

    # ── Voice preview ──

    def _get_selected_voice(self) -> tuple[str, str]:
        data = self._voice.currentData()
        if data:
            return data
        return "f", self._config.persona.voice_id

    def _preview(self):
        speed = self._speed.value()

        if self._radio_chatterbox.isChecked():
            # Utiliser la voix selectionnee dans la bibliotheque
            ref_path = ""
            if self._selected_voice_id:
                ref_path = self._voice_library.get_voice_path(
                    self._selected_voice_id
                ) or ""
            params = {
                "ref_audio": ref_path,
                "language": self._language.currentData() or "fr",
                "exaggeration": self._cb_exaggeration.value(),
                "cfg_weight": self._cb_cfg_weight.value(),
                "temperature": self._cb_temperature.value(),
                "repetition_penalty": self._cb_rep_penalty.value(),
                "top_p": self._cb_top_p.value(),
                "min_p": self._cb_min_p.value(),
                "seed": self._cb_seed.value(),
            }

            self._preview_btn.setEnabled(False)
            self._preview_btn.setText("Chargement GPU...")
            self._preview_worker = _ChatterboxPreviewWorker(params, parent=self)
        else:
            lang, voice = self._get_selected_voice()
            self._preview_btn.setEnabled(False)
            self._preview_btn.setText("Chargement...")
            self._preview_worker = _KokoroPreviewWorker(
                lang, voice, speed, parent=self
            )

        self._preview_worker.finished.connect(self._on_preview_done)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _on_preview_error(self, msg: str):
        log.error("TTS preview: %s", msg)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            self,
            "Erreur Preview",
            f"Erreur lors de la prévisualisation :\n{msg[:300]}",
        )

    def _on_preview_done(self):
        self._preview_btn.setEnabled(True)
        self._preview_btn.setText("Preview voix")
        self._preview_worker = None

    # ── Instructions custom ──

    def _add_custom_instruction(self):
        import uuid

        instr_id = f"custom_{uuid.uuid4().hex[:8]}"
        instr = Instruction(
            id=instr_id,
            label="Nouvelle instruction",
            content="",
            enabled=True,
            builtin=False,
        )

        cb = QCheckBox(instr.label)
        cb.setChecked(True)
        cb.setToolTip("(double-cliquez pour éditer)")

        for group in self.findChildren(QGroupBox):
            if group.title() == "Instructions":
                instr_layout = group.layout()
                insert_idx = 1 + len(self._instruction_checkboxes)
                instr_layout.insertWidget(insert_idx, cb)
                break

        self._instruction_checkboxes.append((instr, cb))

    # ── Application des changements ──

    def apply(self, config: JarvisConfig):
        # Identité
        config.persona.name = self._name.text().strip() or "Jarvis"
        config.persona.language = self._language.currentData() or "fr"
        config.persona.wake_enabled = self._wake_enabled.isChecked()
        config.persona.wake_mode = self._wake_mode.currentData() or "openwakeword"
        if config.persona.wake_mode == "whisper":
            config.persona.wake_phrase = (
                self._whisper_phrase.text().strip() or "salut jarvis"
            )
        else:
            config.persona.wake_phrase = self._wake_phrase.currentText().strip()
        config.persona.wake_threshold = self._wake_threshold.value()

        # Voix — backend
        if self._radio_chatterbox.isChecked():
            config.persona.tts_backend = "chatterbox"
            config.tts.backend = "chatterbox"
        else:
            config.persona.tts_backend = "kokoro"
            config.tts.backend = "kokoro"

        # Voix — Kokoro
        lang, voice_id = self._get_selected_voice()
        config.persona.voice_id = voice_id
        config.tts.kokoro_voice = voice_id
        config.tts.kokoro_lang = lang

        # Voix — Chatterbox (bibliotheque de voix)
        config.persona.active_voice_id = self._selected_voice_id
        if self._selected_voice_id:
            voice_path = self._voice_library.get_voice_path(self._selected_voice_id)
            config.persona.reference_audio = voice_path or ""
        else:
            config.persona.reference_audio = ""
        config.tts.chatterbox_exaggeration = self._cb_exaggeration.value()
        config.tts.chatterbox_cfg_weight = self._cb_cfg_weight.value()
        config.tts.chatterbox_temperature = self._cb_temperature.value()
        config.tts.chatterbox_repetition_penalty = self._cb_rep_penalty.value()
        config.tts.chatterbox_top_p = self._cb_top_p.value()
        config.tts.chatterbox_min_p = self._cb_min_p.value()
        config.tts.chatterbox_seed = self._cb_seed.value()

        # Voix — commun
        config.persona.voice_speed = self._speed.value()
        config.tts.speed = self._speed.value()

        # Instructions
        for instr, cb in self._instruction_checkboxes:
            instr.enabled = cb.isChecked()
        config.persona.instructions = [instr for instr, _ in self._instruction_checkboxes]

        # Override du system prompt
        config.llm.system_prompt_override = self._prompt_override.toPlainText().strip()
