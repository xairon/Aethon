"""TTS — Backend Chatterbox Multilingual (GPU) avec clonage de voix.

Exploite TOUS les parametres de ChatterboxMultilingualTTS :
- exaggeration, cfg_weight (emotion/prosodie)
- temperature, repetition_penalty (sampling)
- top_p, min_p (nucleus/min-p sampling)
- audio_prompt_path (clonage zero-shot)
- prepare_conditionals (cache voix pre-calculee)
- seed (reproductibilite)
"""

import logging
import os
import threading
import time
from collections.abc import Generator

import numpy as np

from aethon.config import AethonConfig

log = logging.getLogger(__name__)

# Langues supportées par ChatterboxMultilingualTTS (ISO 639-1)
_SUPPORTED_LANGS = {
    "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi",
    "it", "ja", "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv",
    "sw", "tr", "zh",
}


class ChatterboxSynthesizer:
    """Backend TTS Chatterbox — multilingue natif (23 langues), clonage zero-shot.

    Resemble AI, #1 TTS Arena. Utilise ``ChatterboxMultilingualTTS``.
    Francais natif via ``language_id="fr"``.
    Clonage de voix via ``audio_prompt_path`` (quelques secondes suffisent).

    Parametres exposes :
    - **exaggeration** : expressivite/emotion (0.25=neutre, 0.5=defaut, 2.0=max)
    - **cfg_weight** : adherence au texte / pacing (0.0=libre, 0.5=defaut, 1.0=strict)
      Mettre a 0 pour le transfert cross-langue (evite accent bleed).
    - **temperature** : variabilite du sampling (0.8=defaut)
    - **repetition_penalty** : penalise les repetitions (2.0=defaut multilingual)
    - **top_p** : nucleus sampling (1.0=desactive=recommande)
    - **min_p** : min-p sampling (0.05=defaut, 0.02-0.1 recommande)
    - **seed** : reproductibilite (-1=aleatoire)

    L'audio est genere en une passe (pas de streaming interne) — le pipeline
    parallele dans ``pipeline.py`` masque la latence en synthetisant la
    phrase N+1 pendant la lecture de la phrase N.
    """

    def __init__(self, config: AethonConfig):
        self._config = config
        self._model = None
        self._sample_rate: int = 0  # Mis a jour au load() depuis model.sr
        self._cached_ref_audio: str | None = None  # Path du dernier ref audio pre-calcule
        self._synthesis_lock = threading.Lock()
        self._load_lock = threading.Lock()

    @property
    def SAMPLE_RATE(self) -> int:
        """Sample rate de sortie (mis a jour apres chargement du modele)."""
        if self._sample_rate == 0:
            raise RuntimeError("ChatterboxSynthesizer.load() doit etre appele avant d'acceder a SAMPLE_RATE")
        return self._sample_rate

    def load(self):
        """Charge le modele Chatterbox Multilingual sur GPU."""
        with self._load_lock:
            if self._model is not None:
                return

            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            log.info("Chargement de Chatterbox Multilingual TTS sur GPU...")
            t0 = time.monotonic()
            try:
                self._model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
            except Exception as e:
                log.error(
                    "Echec chargement Chatterbox: %s — cache corrompu? "
                    "Supprimer %%USERPROFILE%%\\.cache\\huggingface\\hub\\models--ResembleAI--chatterbox "
                    "et relancer.", e, exc_info=True,
                )
                raise RuntimeError(f"Chatterbox from_pretrained a echoue: {e}") from e
            self._sample_rate = self._model.sr
            elapsed = time.monotonic() - t0
            log.info(
                "Chatterbox charge en %.1fs (sample_rate=%d).",
                elapsed, self._sample_rate,
            )

            # Pre-calculer les conditionals si un audio de reference est configure
            self._maybe_prepare_conditionals()

    def _maybe_prepare_conditionals(self):
        """Pre-calcule les conditionals voix si un audio de reference est dispo.

        Appeler prepare_conditionals() une seule fois au lieu de passer
        audio_prompt_path a chaque generate() evite de re-extraire les
        embeddings speaker a chaque phrase (~200ms economises/phrase).

        NOTE : on ne cache QUE sur le chemin audio. L'exaggeration n'est
        pas un critere d'invalidation car generate() met a jour le tensor
        emotion_adv en interne de facon quasi-gratuite (pas de re-extraction
        des embeddings speaker). Cf. mtl_tts.py lignes 258-265.
        """
        ref_audio = self._config.persona.reference_audio
        if not ref_audio or not os.path.exists(ref_audio):
            return
        if ref_audio == self._cached_ref_audio:
            return  # Speaker embeddings deja pre-calcules

        try:
            log.info(
                "Pre-calcul conditionals voix: %s",
                os.path.basename(ref_audio),
            )
            t0 = time.monotonic()
            self._model.prepare_conditionals(ref_audio, exaggeration=0.5)
            self._cached_ref_audio = ref_audio
            elapsed = time.monotonic() - t0
            log.info("Conditionals pre-calcules en %.2fs.", elapsed)
        except Exception as e:
            log.warning("Echec prepare_conditionals: %s", e)
            self._cached_ref_audio = None

    def synthesize_stream(self, text: str, emotion_params=None) -> Generator[np.ndarray, None, None]:
        """Synthetise du texte, yield un chunk audio float32.

        Args:
            text: Texte a synthetiser (sans tags d'emotion).
            emotion_params: EmotionPreset optionnel (exaggeration, cfg_weight,
                temperature) qui override les valeurs de config pour ce segment.
                Permet un rendu expressif dynamique par segment.
        """
        self.load()

        # Valider le texte
        text = (text or "").strip()
        if not text:
            return

        with self._synthesis_lock:
            lang = self._config.persona.language
            if lang not in _SUPPORTED_LANGS:
                log.warning(
                    "Langue '%s' non supportee par Chatterbox, fallback vers 'fr'.",
                    lang,
                )
                lang = "fr"

            # Gerer la disparition du fichier de reference
            ref_audio = self._config.persona.reference_audio
            if ref_audio and not os.path.exists(ref_audio) and self._cached_ref_audio == ref_audio:
                log.warning("Fichier reference disparu, invalidation cache conditionals.")
                self._cached_ref_audio = None

            # Verifier si le ref audio ou l'exaggeration a change → re-preparer les conditionals
            if ref_audio and os.path.exists(ref_audio) and ref_audio != self._cached_ref_audio:
                self._maybe_prepare_conditionals()

            # Construire les kwargs de generation
            tts_cfg = self._config.tts
            kwargs = {"language_id": lang}

            # Si pas de conditionals pre-calcules, passer le path directement
            if not self._cached_ref_audio and ref_audio and os.path.exists(ref_audio):
                kwargs["audio_prompt_path"] = ref_audio

            # Parametres de generation : emotion_params override si present
            if emotion_params is not None:
                kwargs["exaggeration"] = emotion_params.exaggeration
                kwargs["cfg_weight"] = emotion_params.cfg_weight
                kwargs["temperature"] = emotion_params.temperature
            else:
                kwargs["exaggeration"] = tts_cfg.chatterbox_exaggeration
                kwargs["cfg_weight"] = tts_cfg.chatterbox_cfg_weight
                kwargs["temperature"] = tts_cfg.chatterbox_temperature

            # Parametres de sampling (toujours depuis la config)
            kwargs["repetition_penalty"] = tts_cfg.chatterbox_repetition_penalty
            kwargs["top_p"] = tts_cfg.chatterbox_top_p
            kwargs["min_p"] = tts_cfg.chatterbox_min_p

            # Seed pour reproductibilite
            seed = tts_cfg.chatterbox_seed
            if seed >= 0:
                import torch
                torch.manual_seed(seed)

            try:
                t0 = time.monotonic()
                wav = self._model.generate(text, **kwargs)
                elapsed = time.monotonic() - t0
                emo_tag = f" [{emotion_params.exaggeration:.2f}/{emotion_params.cfg_weight:.2f}]" if emotion_params else ""
                log.debug(
                    "Chatterbox%s: '%s' → %.2fs audio en %.2fs (RTF=%.2f)",
                    emo_tag,
                    text[:40],
                    wav.shape[-1] / self._sample_rate if wav is not None else 0,
                    elapsed,
                    (wav.shape[-1] / self._sample_rate / elapsed) if wav is not None and elapsed > 0 else 0,
                )
            except Exception as e:
                log.error("Erreur synthese Chatterbox: %s", e, exc_info=True)
                return

            if wav is None:
                log.warning("Chatterbox: generation vide pour '%s'", text[:50])
                return

            # Tensor [1, samples] ou [samples] → numpy float32 1D
            audio = wav.squeeze().cpu().numpy().astype(np.float32)

            if audio.size == 0:
                log.warning("Chatterbox: audio vide apres conversion")
                return

            # Normaliser si l'audio depasse [-1, 1] (securite)
            peak = np.max(np.abs(audio))
            if peak > 1.0:
                audio = audio / peak

            yield audio

    def set_reference_voice(self, audio_path: str):
        """Change la voix de reference et re-prepare les conditionals."""
        if audio_path and os.path.exists(audio_path):
            self._config.persona.reference_audio = audio_path
            log.info("Voix de reference mise a jour: %s", audio_path)
            # Re-preparer les conditionals si le modele est charge
            if self._model is not None:
                self._cached_ref_audio = None  # Force re-calcul
                self._maybe_prepare_conditionals()
        else:
            log.warning("Fichier audio introuvable: %s", audio_path)

    def unload(self):
        """Libere le modele GPU."""
        if self._model is not None:
            del self._model
            self._model = None
            self._cached_ref_audio = None

            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            log.info("Chatterbox decharge.")
