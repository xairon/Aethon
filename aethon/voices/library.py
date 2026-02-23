"""Bibliotheque de voix — gestion locale + telechargement HuggingFace.

Gere un dossier `voices/` contenant des sous-dossiers par voix,
chacun avec `voice.wav` + `meta.json`. Permet aussi de naviguer
et telecharger des voix depuis le dataset Kyutai TTS Voices sur HF.
"""

import json
import logging
import re
import shutil
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Dataset HuggingFace Kyutai TTS Voices
HF_REPO_ID = "kyutai/tts-voices"

# Mapping categorie → chemin dans le repo HF
HF_CATEGORY_PATHS = {
    "donations": "voice-donations",
    "french": "cml-tts/fr",
    "vctk": "vctk",
}


@dataclass
class VoiceMeta:
    """Metadonnees d'une voix dans la bibliotheque locale."""

    id: str  # Nom du dossier (ex: "kyutai_donation_0a67")
    name: str  # Nom affiche (ex: "Donation 0A67")
    lang: str  # "fr", "en", "unknown"
    gender: str  # "male", "female", "unknown"
    source: str  # "local" ou "kyutai"
    duration_s: float  # Duree en secondes
    path: str  # Chemin absolu vers voice.wav


@dataclass
class HFVoiceInfo:
    """Voix disponible sur HuggingFace (pas encore telechargee)."""

    hf_id: str  # Nom du fichier sur HF (ex: "0a67_enhanced.wav")
    display_name: str  # Nom affiche (ex: "Donation 0A67")
    category: str  # "donations", "french", "vctk"
    size_mb: float  # Taille en MB
    is_installed: bool  # Deja telechargee localement


def _slugify(text: str) -> str:
    """Genere un identifiant propre a partir d'un texte."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "voice"


def _get_wav_duration(path: str) -> float:
    """Retourne la duree d'un fichier WAV en secondes (stdlib wave)."""
    try:
        with wave.open(path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate > 0:
                return frames / rate
    except Exception as e:
        log.debug("Impossible de lire la duree WAV de %s: %s", path, e)
    return 0.0


class VoiceLibrary:
    """Gestionnaire de la bibliotheque de voix locale + HuggingFace."""

    def __init__(self, voices_dir: str):
        self._dir = Path(voices_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._hf_cache: dict[str, list[HFVoiceInfo]] = {}

    @property
    def voices_dir(self) -> Path:
        """Chemin du dossier voices/."""
        return self._dir

    # ── Gestion locale ──────────────────────────────────────────────

    def scan_local(self) -> list[VoiceMeta]:
        """Scanne voices/*/meta.json et retourne la liste triee par nom."""
        voices: list[VoiceMeta] = []
        if not self._dir.exists():
            return voices

        for sub in sorted(self._dir.iterdir()):
            if not sub.is_dir():
                continue
            meta_file = sub / "meta.json"
            wav_file = sub / "voice.wav"
            if not meta_file.exists() or not wav_file.exists():
                continue
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                voices.append(
                    VoiceMeta(
                        id=sub.name,
                        name=data.get("name", sub.name),
                        lang=data.get("lang", "unknown"),
                        gender=data.get("gender", "unknown"),
                        source=data.get("source", "local"),
                        duration_s=data.get("duration_s", 0.0),
                        path=str(wav_file.resolve()),
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                log.warning("Meta invalide dans %s: %s", meta_file, e)

        voices.sort(key=lambda v: v.name.lower())
        return voices

    def import_wav(
        self, src_path: str, name: str, lang: str = "fr", gender: str = "unknown"
    ) -> VoiceMeta:
        """Importe un fichier WAV dans la bibliotheque.

        Copie le fichier (ne le deplace pas) et cree le meta.json.
        """
        slug = _slugify(name)
        voice_id = f"custom_{slug}"

        # Eviter les collisions
        dest_dir = self._dir / voice_id
        counter = 2
        while dest_dir.exists():
            voice_id = f"custom_{slug}_{counter}"
            dest_dir = self._dir / voice_id
            counter += 1

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_wav = dest_dir / "voice.wav"

        # Copier le fichier audio
        shutil.copy2(src_path, dest_wav)

        # Mesurer la duree
        duration_s = _get_wav_duration(str(dest_wav))

        # Ecrire meta.json
        meta = {
            "name": name,
            "lang": lang,
            "gender": gender,
            "source": "local",
            "duration_s": round(duration_s, 1),
        }
        (dest_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        log.info("Voix importee: %s → %s (%.1fs)", name, voice_id, duration_s)

        return VoiceMeta(
            id=voice_id,
            name=name,
            lang=lang,
            gender=gender,
            source="local",
            duration_s=duration_s,
            path=str(dest_wav.resolve()),
        )

    def delete_voice(self, voice_id: str) -> bool:
        """Supprime une voix de la bibliotheque. Retourne True si supprimee."""
        voice_dir = self._dir / voice_id
        if not voice_dir.exists():
            log.warning("Voix introuvable: %s", voice_id)
            return False

        try:
            shutil.rmtree(voice_dir)
            log.info("Voix supprimee: %s", voice_id)
            return True
        except Exception as e:
            log.error("Erreur suppression voix %s: %s", voice_id, e)
            return False

    def get_voice_path(self, voice_id: str) -> str | None:
        """Retourne le chemin absolu vers voice.wav, ou None si absent."""
        wav = self._dir / voice_id / "voice.wav"
        if wav.exists():
            return str(wav.resolve())
        return None

    def is_installed(self, hf_id: str, category: str) -> bool:
        """Verifie si une voix HF est deja installee localement."""
        local_id = self._hf_to_local_id(hf_id, category)
        return (self._dir / local_id / "voice.wav").exists()

    # ── HuggingFace ─────────────────────────────────────────────────

    def list_hf_voices(self, category: str = "donations") -> list[HFVoiceInfo]:
        """Liste les voix disponibles sur HuggingFace pour une categorie.

        Resultat cache en memoire pour eviter les appels API repetes.
        """
        if category in self._hf_cache:
            # Mettre a jour is_installed
            for v in self._hf_cache[category]:
                v.is_installed = self.is_installed(v.hf_id, v.category)
            return self._hf_cache[category]

        from huggingface_hub import list_repo_tree

        path_prefix = HF_CATEGORY_PATHS.get(category, "voice-donations")

        voices: list[HFVoiceInfo] = []
        try:
            for entry in list_repo_tree(
                HF_REPO_ID, path_in_repo=path_prefix, repo_type="dataset"
            ):
                name = entry.path.split("/")[-1]
                if not name.endswith("_enhanced.wav"):
                    continue

                # Extraire un nom affichable
                clean = name.replace("_enhanced.wav", "")
                display = self._make_display_name(clean, category)

                size_mb = entry.size / (1024 * 1024) if hasattr(entry, "size") and entry.size else 0.0

                voices.append(
                    HFVoiceInfo(
                        hf_id=name,
                        display_name=display,
                        category=category,
                        size_mb=round(size_mb, 1),
                        is_installed=self.is_installed(name, category),
                    )
                )

            voices.sort(key=lambda v: v.display_name.lower())
            log.info("HF %s: %d voix trouvees.", category, len(voices))

        except Exception as e:
            log.error("Erreur listing HF %s: %s", category, e)

        self._hf_cache[category] = voices
        return voices

    def invalidate_hf_cache(self, category: str | None = None):
        """Invalide le cache HF (une categorie ou toutes)."""
        if category:
            self._hf_cache.pop(category, None)
        else:
            self._hf_cache.clear()

    def download_hf_voice(
        self, hf_id: str, category: str, progress_cb=None
    ) -> VoiceMeta:
        """Telecharge une voix depuis HuggingFace et l'installe localement."""
        from huggingface_hub import hf_hub_download

        path_prefix = HF_CATEGORY_PATHS.get(category, "voice-donations")
        hf_path = f"{path_prefix}/{hf_id}"

        # ID local
        local_id = self._hf_to_local_id(hf_id, category)
        dest_dir = self._dir / local_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_wav = dest_dir / "voice.wav"

        # Telecharger via huggingface_hub
        log.info("Telechargement HF: %s → %s", hf_path, local_id)
        downloaded_path = hf_hub_download(
            HF_REPO_ID,
            filename=hf_path,
            repo_type="dataset",
            local_dir=str(dest_dir / "_hf_tmp"),
        )

        # Copier vers voice.wav (hf_hub_download met dans un sous-arbre)
        shutil.copy2(downloaded_path, dest_wav)

        # Nettoyer le dossier temporaire HF
        hf_tmp = dest_dir / "_hf_tmp"
        if hf_tmp.exists():
            shutil.rmtree(hf_tmp)

        # Mesurer la duree
        duration_s = _get_wav_duration(str(dest_wav))

        # Determiner la langue depuis la categorie
        lang = "fr" if category == "french" else "en" if category == "vctk" else "unknown"

        # Nom affichable
        clean = hf_id.replace("_enhanced.wav", "")
        display = self._make_display_name(clean, category)

        # Ecrire meta.json
        meta = {
            "name": display,
            "lang": lang,
            "gender": "unknown",
            "source": "kyutai",
            "duration_s": round(duration_s, 1),
        }
        (dest_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        log.info("Voix HF installee: %s (%.1fs)", local_id, duration_s)

        return VoiceMeta(
            id=local_id,
            name=display,
            lang=lang,
            gender="unknown",
            source="kyutai",
            duration_s=duration_s,
            path=str(dest_wav.resolve()),
        )

    def download_hf_voices_batch(
        self, items: list[tuple[str, str]], progress_cb=None
    ) -> list[VoiceMeta]:
        """Telecharge une liste de voix HF sequentiellement.

        Args:
            items: Liste de (hf_id, category) tuples.
            progress_cb: Callable(current_index, total_count, voice_name).
        """
        results: list[VoiceMeta] = []
        total = len(items)

        for i, (hf_id, category) in enumerate(items):
            clean = hf_id.replace("_enhanced.wav", "")
            display = self._make_display_name(clean, category)

            if progress_cb:
                progress_cb(i, total, display)

            try:
                meta = self.download_hf_voice(hf_id, category)
                results.append(meta)
            except Exception as e:
                log.error("Echec telechargement %s: %s", hf_id, e)

        if progress_cb:
            progress_cb(total, total, "Termine")

        return results

    # ── Helpers privees ──────────────────────────────────────────────

    def _hf_to_local_id(self, hf_id: str, category: str) -> str:
        """Convertit un identifiant HF en identifiant local."""
        clean = hf_id.replace("_enhanced.wav", "").replace(".wav", "")
        clean = _slugify(clean)
        prefix_map = {
            "donations": "kyutai_donation",
            "french": "kyutai_fr",
            "vctk": "kyutai_vctk",
        }
        prefix = prefix_map.get(category, "kyutai")
        return f"{prefix}_{clean}"

    @staticmethod
    def _make_display_name(clean_id: str, category: str) -> str:
        """Genere un nom affichable a partir d'un ID et d'une categorie."""
        if category == "donations":
            return f"Donation {clean_id.upper()}"
        elif category == "french":
            # IDs comme "cml_tts_fr_1234" → "FR 1234"
            parts = clean_id.replace("cml_tts_fr_", "").replace("cml_tts_", "")
            return f"FR {parts.upper()}"
        elif category == "vctk":
            # IDs comme "p225" → "VCTK P225"
            return f"VCTK {clean_id.upper()}"
        return clean_id.title()
