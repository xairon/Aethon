"""Navigateur de voix HuggingFace — telechargement depuis Kyutai TTS Voices."""

import logging
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QProgressBar, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from aethon.gui.theme import (
    ACCENT, BG_BASE, BG_RAISED, BG_SURFACE,
    BORDER_DEFAULT, GREEN, TEXT, TEXT_INVERSE, TEXT_SECONDARY,
)
from aethon.voices.library import HFVoiceInfo, VoiceLibrary

log = logging.getLogger(__name__)

# Categories disponibles sur le dataset Kyutai
_CATEGORIES = [
    ("donations", "Donations"),
    ("french", "Francais"),
    ("vctk", "VCTK"),
]


class _HFListWorker(QThread):
    """Charge la liste des voix HF pour une categorie dans un thread."""

    loaded = pyqtSignal(str, list)
    error = pyqtSignal(str, str)

    def __init__(self, library: VoiceLibrary, category: str, parent=None):
        super().__init__(parent)
        self._library = library
        self._category = category

    def run(self):
        """Appelle list_hf_voices (I/O reseau) hors du thread GUI."""
        try:
            voices = self._library.list_hf_voices(self._category)
            self.loaded.emit(self._category, voices)
        except Exception as e:
            log.error("Erreur chargement HF %s: %s", self._category, e)
            self.error.emit(self._category, str(e))


class _HFDownloadWorker(QThread):
    """Telecharge une liste de voix HF sequentiellement."""

    progress = pyqtSignal(int, int, str)  # current, total, name
    finished = pyqtSignal(list)

    def __init__(self, library: VoiceLibrary, items: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self._library = library
        self._items = items

    def run(self):
        """Telecharge via download_hf_voices_batch avec callback de progression."""
        results = self._library.download_hf_voices_batch(
            self._items,
            progress_cb=lambda cur, total, name: self.progress.emit(cur, total, name),
        )
        self.finished.emit(results)


class _VoiceItemWidget(QWidget):
    """Widget personnalise pour un item de la liste de voix HF."""

    checked_changed = pyqtSignal()

    def __init__(self, info: HFVoiceInfo, parent=None):
        super().__init__(parent)
        self.info = info
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Checkbox de selection (pour batch)
        self.checkbox = QCheckBox()
        self.checkbox.setEnabled(not info.is_installed)
        self.checkbox.toggled.connect(lambda: self.checked_changed.emit())
        layout.addWidget(self.checkbox)

        # Nom de la voix (gras)
        name_lbl = QLabel(info.display_name)
        name_lbl.setStyleSheet(f"font-weight: bold; color: {TEXT};")
        layout.addWidget(name_lbl)

        # Taille en MB
        size_lbl = QLabel(f"{info.size_mb:.1f} MB")
        size_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(size_lbl)

        layout.addStretch()

        # Badge "Installe"
        self.badge = QLabel("Installe")
        self.badge.setStyleSheet(
            f"background-color: {GREEN}; color: {TEXT_INVERSE}; "
            f"border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
        )
        self.badge.setVisible(info.is_installed)
        layout.addWidget(self.badge)

        # Bouton telecharger
        self.dl_btn = QPushButton("Telecharger")
        self.dl_btn.setStyleSheet(
            f"background-color: {ACCENT}; color: {TEXT_INVERSE}; border: none; "
            f"border-radius: 6px; padding: 4px 14px; font-weight: 500; font-size: 12px;"
        )
        self.dl_btn.setVisible(not info.is_installed)
        layout.addWidget(self.dl_btn)

    def mark_installed(self):
        """Met a jour l'affichage apres telechargement reussi."""
        self.info.is_installed = True
        self.badge.setVisible(True)
        self.dl_btn.setVisible(False)
        self.checkbox.setChecked(False)
        self.checkbox.setEnabled(False)


class VoiceBrowserDialog(QDialog):
    """Dialogue modal pour naviguer et telecharger des voix depuis HuggingFace."""

    voices_changed = pyqtSignal()

    def __init__(self, library: VoiceLibrary, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._library = library
        self._workers: list[QThread] = []
        self._dl_worker: Optional[_HFDownloadWorker] = None
        self._tab_loaded: dict[str, bool] = {}
        self._item_widgets: dict[str, list[_VoiceItemWidget]] = {}

        self.setWindowTitle("Telecharger des voix")
        self.resize(700, 550)
        self.setMinimumSize(600, 450)
        self._build_ui()
        self._load_tab(0)

    def _build_ui(self):
        """Construit le layout du dialogue."""
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        # Titre + sous-titre
        title = QLabel("Telecharger des voix — Kyutai TTS Voices")
        title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {TEXT};")
        root.addWidget(title)

        subtitle = QLabel("Dataset HuggingFace avec 370+ voix gratuites")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        root.addWidget(subtitle)
        root.addSpacing(6)

        # Onglets par categorie
        self._tabs = QTabWidget()
        self._lists: dict[str, QListWidget] = {}
        self._loading_labels: dict[str, QLabel] = {}

        for cat_id, cat_label in _CATEGORIES:
            page = QWidget()
            page_lay = QVBoxLayout(page)
            page_lay.setContentsMargins(0, 0, 0, 0)

            loading = QLabel("Chargement...")
            loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading.setStyleSheet(f"color: {TEXT_SECONDARY}; padding: 40px;")
            page_lay.addWidget(loading)
            self._loading_labels[cat_id] = loading

            list_w = QListWidget()
            list_w.setStyleSheet(
                f"QListWidget {{ background-color: {BG_BASE}; "
                f"border: 1px solid {BORDER_DEFAULT}; border-radius: 6px; }} "
                f"QListWidget::item {{ border-bottom: 1px solid {BG_SURFACE}; padding: 2px; }} "
                f"QListWidget::item:selected {{ background-color: {BG_RAISED}; }}"
            )
            list_w.setVisible(False)
            page_lay.addWidget(list_w)
            self._lists[cat_id] = list_w
            self._tabs.addTab(page, cat_label)

        self._tabs.currentChanged.connect(self._load_tab)
        root.addWidget(self._tabs, 1)

        # Barre du bas : compteur + progress + bouton batch
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self._count_label = QLabel("0 selectionne(s)")
        self._count_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        bottom.addWidget(self._count_label)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar {{ background-color: {BG_RAISED}; border: none; border-radius: 3px; }} "
            f"QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}"
        )
        self._progress.setVisible(False)
        bottom.addWidget(self._progress, 1)
        bottom.addStretch()

        self._batch_btn = QPushButton("Telecharger la selection (0)")
        self._batch_btn.setStyleSheet(
            f"background-color: {GREEN}; color: {TEXT_INVERSE}; font-weight: bold; "
            f"border: none; border-radius: 8px; padding: 8px 20px; font-size: 13px;"
        )
        self._batch_btn.setEnabled(False)
        self._batch_btn.clicked.connect(self._start_batch_download)
        bottom.addWidget(self._batch_btn)
        root.addLayout(bottom)

    # ── Chargement des voix ──────────────────────────────────────────

    def _load_tab(self, index: int):
        """Charge les voix d'un onglet si pas encore fait."""
        cat_id = _CATEGORIES[index][0]
        if cat_id in self._tab_loaded:
            return
        self._tab_loaded[cat_id] = True
        worker = _HFListWorker(self._library, cat_id, self)
        worker.loaded.connect(self._on_voices_loaded)
        worker.error.connect(self._on_load_error)
        self._workers.append(worker)
        worker.start()

    def _on_voices_loaded(self, category: str, voices: list[HFVoiceInfo]):
        """Remplit la QListWidget avec les voix chargees."""
        self._loading_labels[category].setVisible(False)
        list_w = self._lists[category]
        list_w.setVisible(True)

        widgets: list[_VoiceItemWidget] = []
        for voice in voices:
            item_widget = _VoiceItemWidget(voice)
            item_widget.checked_changed.connect(self._update_selection_count)
            item_widget.dl_btn.clicked.connect(
                lambda _=False, v=voice: self._download_single(v)
            )
            item = QListWidgetItem(list_w)
            item.setSizeHint(item_widget.sizeHint())
            list_w.addItem(item)
            list_w.setItemWidget(item, item_widget)
            widgets.append(item_widget)

        self._item_widgets[category] = widgets
        log.info("Onglet %s: %d voix affichees.", category, len(voices))

    def _on_load_error(self, category: str, message: str):
        """Affiche un message d'erreur si le chargement echoue."""
        label = self._loading_labels[category]
        label.setText(f"Erreur : {message}")
        label.setStyleSheet("color: #f87171; padding: 40px;")

    # ── Selection / compteur ─────────────────────────────────────────

    def _get_selected(self) -> list[tuple[_VoiceItemWidget, str]]:
        """Retourne les items coches (non installes) avec leur categorie."""
        selected = []
        for cat_id, widgets in self._item_widgets.items():
            for w in widgets:
                if w.checkbox.isChecked() and not w.info.is_installed:
                    selected.append((w, cat_id))
        return selected

    def _update_selection_count(self):
        """Met a jour le label et le bouton batch."""
        count = len(self._get_selected())
        self._count_label.setText(f"{count} selectionne(s)")
        self._batch_btn.setText(f"Telecharger la selection ({count})")
        self._batch_btn.setEnabled(count > 0 and self._dl_worker is None)

    # ── Telechargement ───────────────────────────────────────────────

    def _download_single(self, voice: HFVoiceInfo):
        """Telecharge une seule voix via le worker."""
        if self._dl_worker is not None:
            return
        self._start_download([(voice.hf_id, voice.category)])

    def _start_batch_download(self):
        """Lance le telechargement de toutes les voix cochees."""
        selected = self._get_selected()
        if not selected or self._dl_worker is not None:
            return
        items = [(w.info.hf_id, cat) for w, cat in selected]
        self._start_download(items)

    def _start_download(self, items: list[tuple[str, str]]):
        """Demarre le worker de telechargement avec la barre de progression."""
        self._set_downloading(True)
        self._progress.setMaximum(len(items))
        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._dl_worker = _HFDownloadWorker(self._library, items, self)
        self._dl_worker.progress.connect(self._on_dl_progress)
        self._dl_worker.finished.connect(self._on_dl_finished)
        self._dl_worker.start()

    def _on_dl_progress(self, current: int, total: int, name: str):
        """Met a jour la barre de progression pendant le telechargement."""
        self._progress.setValue(current)
        self._count_label.setText(f"Telechargement {current + 1}/{total} : {name}")

    def _on_dl_finished(self, results: list):
        """Appele quand tous les telechargements sont termines."""
        self._dl_worker = None
        self._progress.setVisible(False)
        self._set_downloading(False)

        # Marquer les items telecharges comme installes
        downloaded_ids = {r.id for r in results}
        for widgets in self._item_widgets.values():
            for w in widgets:
                local_id = self._library._hf_to_local_id(w.info.hf_id, w.info.category)
                if local_id in downloaded_ids:
                    w.mark_installed()

        self._update_selection_count()
        if results:
            log.info("%d voix telechargee(s) avec succes.", len(results))
            self.voices_changed.emit()

    def _set_downloading(self, active: bool):
        """Active/desactive les controles pendant un telechargement."""
        self._batch_btn.setEnabled(not active)
        for widgets in self._item_widgets.values():
            for w in widgets:
                w.dl_btn.setEnabled(not active)
