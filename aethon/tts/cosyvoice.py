"""TTS — Backend CosyVoice2/CosyVoice3 (GPU) avec clonage de voix."""

import logging
import os
import sys
from collections.abc import Generator
from pathlib import Path

import numpy as np

from aethon.config import AethonConfig

log = logging.getLogger(__name__)

# Chemin par défaut du repo CosyVoice cloné dans third_party/
_COSYVOICE_ROOT = Path(__file__).parent.parent.parent / "third_party" / "CosyVoice"
_MATCHA_TTS_PATH = _COSYVOICE_ROOT / "third_party" / "Matcha-TTS"


def _ensure_cosyvoice_on_path():
    """Ajoute CosyVoice et Matcha-TTS au sys.path si nécessaire."""
    root = str(_COSYVOICE_ROOT)
    matcha = str(_MATCHA_TTS_PATH)
    if root not in sys.path:
        sys.path.insert(0, root)
    if matcha not in sys.path:
        sys.path.insert(0, matcha)


class CosyVoiceSynthesizer:
    """Backend TTS local sur GPU avec support clonage de voix.

    Supporte CosyVoice2 et CosyVoice3 via AutoModel (détection automatique).
    CosyVoice3 est recommandé pour le multilingue (français natif).
    Nécessite un audio de référence (~5-15s) et sa transcription pour cloner
    une voix. Sans référence, utilise la voix par défaut SFT si disponible.
    """

    # Langues nativement supportées par CosyVoice2 pour les tags <|xx|>
    # CosyVoice3 est multilingue natif et n'a pas besoin de tags langue.
    _CV2_SUPPORTED_LANGS = {"zh", "en", "ja", "yue", "ko"}

    def __init__(self, config: AethonConfig):
        self._config = config
        self._model = None
        self._is_v3: bool = False
        self._sample_rate: int = 24000
        self._reference_audio = None  # torch.Tensor [1, samples] ou None
        self._reference_text: str = ""
        self._speaker_registered: bool = False

    @property
    def SAMPLE_RATE(self) -> int:
        """Sample rate de sortie (mis à jour après chargement du modèle)."""
        return self._sample_rate

    @staticmethod
    def _setup_modelscope_cache():
        """Active le mode offline ModelScope si le cache WeText existe.

        WeText (text normalizer de CosyVoice) utilise modelscope snapshot_download
        qui fait une requête réseau à chaque instanciation pour vérifier les mises
        à jour, même quand le modèle est déjà en cache. Le mode offline supprime
        cette vérification et accélère le chargement de ~10-20s.
        """
        if os.environ.get("MODELSCOPE_OFFLINE"):
            return  # Déjà configuré
        cache_candidates = [
            Path.home() / ".cache" / "modelscope" / "hub" / "pengzhendong" / "wetext",
            Path.home() / ".cache" / "modelscope" / "hub" / "models" / "pengzhendong" / "wetext",
        ]
        for cache_dir in cache_candidates:
            if cache_dir.exists() and any(cache_dir.iterdir()):
                os.environ["MODELSCOPE_OFFLINE"] = "1"
                log.info("WeText cache trouvé (%s), mode offline ModelScope activé.", cache_dir)
                return
        log.info("WeText pas encore en cache, premier téléchargement sera effectué.")

    def load(self):
        """Charge le modèle CosyVoice sur GPU (v2 ou v3 via AutoModel)."""
        if self._model is not None:
            return

        _ensure_cosyvoice_on_path()

        # Empêcher WeText de re-télécharger à chaque lancement
        self._setup_modelscope_cache()

        from cosyvoice.cli.cosyvoice import AutoModel

        model_dir = self._config.tts.cosyvoice_model
        # Si c'est un nom HuggingFace, résoudre en chemin local
        if "/" in model_dir and not os.path.exists(model_dir):
            local_dir = _COSYVOICE_ROOT / "pretrained_models" / model_dir.split("/")[-1]
            if local_dir.exists():
                model_dir = str(local_dir)
            else:
                log.info("Téléchargement du modèle %s...", model_dir)

        log.info("Chargement de CosyVoice (%s) sur GPU (fp32)...", model_dir)
        self._model = AutoModel(
            model_dir=model_dir,
            load_trt=False,
            fp16=False,
        )
        self._is_v3 = type(self._model).__name__ == "CosyVoice3"
        self._sample_rate = self._model.sample_rate
        version = "CosyVoice3" if self._is_v3 else "CosyVoice2"
        log.info("%s charg\u00e9 (sample_rate=%d).", version, self.SAMPLE_RATE)

        # Baisser le CFG rate pour plus d'expressivite et de variation prosodique.
        # Default 0.7 = tres colle a la reference → monotone.
        # 0.4 = garde le timbre mais plus de liberte d'intonation.
        self._set_cfg_rate(0.4)

        # Charger la voix de référence si configurée
        ref_path = self._config.persona.reference_audio
        ref_text = self._config.persona.reference_text
        if ref_path and os.path.exists(ref_path):
            self._load_reference(ref_path, ref_text)

    def _set_cfg_rate(self, rate: float):
        """Modifie le inference_cfg_rate du flow matching a runtime.

        Controle l'intensite du classifier-free guidance :
        - 0.7 (defaut) : tres fidele a la reference mais monotone
        - 0.4-0.5 : bon equilibre timbre/expressivite
        - 0.2-0.3 : tres expressif mais peut diverger du timbre
        """
        try:
            flow = self._model.model.flow
            if hasattr(flow, "decoder") and hasattr(flow.decoder, "inference_cfg_rate"):
                old = flow.decoder.inference_cfg_rate
                flow.decoder.inference_cfg_rate = rate
                log.info("CFG rate: %.2f -> %.2f (plus expressif)", old, rate)
            else:
                log.debug("Impossible de modifier le CFG rate (structure modele inconnue)")
        except Exception as e:
            log.debug("CFG rate non modifiable: %s", e)

    def _load_reference(self, audio_path: str, text: str):
        """Charge l'audio de référence pour le clonage de voix."""
        import torchaudio

        log.info("Chargement de la voix de référence : %s", audio_path)
        waveform, sr = torchaudio.load(audio_path)

        # Convertir en mono si stéréo
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # Resampler à 16kHz (requis par le frontend CosyVoice)
        if sr != 16000:
            waveform = torchaudio.functional.resample(waveform, sr, 16000)

        self._reference_audio = waveform
        self._reference_text = text or ""
        duration = waveform.shape[1] / 16000
        log.info("Voix de référence chargée (%.1fs, texte=%d chars)", duration, len(text))

        # Enregistrer le speaker pour réutilisation
        if self._model is not None and text:
            try:
                spk_id = "aethon_cloned"
                prompt_text = self._format_prompt_text(text)
                self._model.add_zero_shot_spk(prompt_text, audio_path, spk_id)
                self._speaker_registered = True
                log.info("Speaker '%s' enregistré pour réutilisation.", spk_id)
            except Exception as e:
                log.warning("Impossible d'enregistrer le speaker: %s", e)
                self._speaker_registered = False

    def _format_prompt_text(self, text: str) -> str:
        """Formate le texte de référence (prompt_text) selon la version du modèle.

        CosyVoice3 requiert ``<|endofprompt|>`` dans le prompt_text :
            ``You are a helpful assistant.<|endofprompt|>{texte}``

        CosyVoice2 utilise des tags langue pour les langues supportées :
            ``<|en|>{texte}`` ou texte brut pour les langues non supportées.
        """
        if self._is_v3:
            if "<|endofprompt|>" not in text:
                return f"You are a helpful assistant.<|endofprompt|>{text}"
            return text
        # CosyVoice2 : tag langue si supportée
        return self._tag_text_v2(text)

    def _format_tts_text(self, text: str) -> str:
        """Formate le texte à synthétiser selon la version du modèle.

        CosyVoice3 : pas de tag langue, le modèle est multilingue natif.
        CosyVoice2 : tag langue pour les langues supportées (zh/en/ja/yue/ko).
        """
        if self._is_v3:
            return text  # CosyVoice3 gère le multilingue nativement
        return self._tag_text_v2(text)

    def _format_crosslingual_text(self, text: str) -> str:
        """Formate le texte pour le mode cross-lingual.

        CosyVoice3 requiert ``<|endofprompt|>`` dans le tts_text en cross-lingual
        (pas de prompt_text dans ce mode).
        """
        if self._is_v3:
            if "<|endofprompt|>" not in text:
                return f"You are a helpful assistant.<|endofprompt|>{text}"
            return text
        return self._tag_text_v2(text)

    def _tag_text_v2(self, text: str) -> str:
        """Préfixe le texte avec le tag de langue CosyVoice2 si supporté.

        Seules zh/en/ja/yue/ko sont supportées. Pour les autres (ex: français),
        pas de tag — il serait tokenisé en subwords parasites.
        """
        lang = self._config.persona.language
        tag_map = {"zh": "<|zh|>", "en": "<|en|>", "ja": "<|ja|>",
                   "yue": "<|yue|>", "ko": "<|ko|>"}
        tag = tag_map.get(lang, "")
        if tag and not text.startswith("<|"):
            return f"{tag}{text}"
        return text

    @property
    def _needs_raw_frontend(self) -> bool:
        """True si text_frontend doit être désactivé.

        CosyVoice3 : toujours False (le frontend gère le multilingue).
        CosyVoice2 : True pour les langues non supportées (évite le
        traitement anglais sur du texte français).
        """
        if self._is_v3:
            return False
        return self._config.persona.language not in self._CV2_SUPPORTED_LANGS

    def synthesize_stream(self, text: str) -> Generator[np.ndarray, None, None]:
        """Synth\u00e9tise du texte, yield des chunks audio float32.

        Utilise le mode **non-streaming** (``stream=False``) pour :
        - Meilleure qualit\u00e9 (pas d'artefacts aux jointures de chunks)
        - Support du param\u00e8tre speed (ignor\u00e9 en mode streaming)
        - Meilleure coh\u00e9rence prosodique sur la phrase enti\u00e8re

        Le pipeline parall\u00e8le dans ``pipeline.py`` masque la latence en
        synth\u00e9tisant la phrase N+1 pendant la lecture de la phrase N.
        """
        self.load()

        speed = self._config.tts.speed
        raw = self._needs_raw_frontend

        try:
            if self._reference_text and (self._reference_audio is not None or self._speaker_registered):
                # Mode clonage zero-shot (avec texte de r\u00e9f\u00e9rence)
                spk_id = "aethon_cloned" if self._speaker_registered else ""
                prompt_wav = "" if self._speaker_registered else self._config.persona.reference_audio
                tts_text = self._format_tts_text(text)
                prompt_text = self._format_prompt_text(self._reference_text)
                gen = self._model.inference_zero_shot(
                    tts_text,
                    prompt_text,
                    prompt_wav,
                    zero_shot_spk_id=spk_id,
                    stream=False,
                    speed=speed,
                    text_frontend=not raw,
                )
            elif self._reference_audio is not None:
                # Mode cross-lingual (audio de r\u00e9f\u00e9rence sans texte)
                tts_text = self._format_crosslingual_text(text)
                gen = self._model.inference_cross_lingual(
                    tts_text,
                    self._config.persona.reference_audio,
                    stream=False,
                    speed=speed,
                    text_frontend=not raw,
                )
            else:
                # Pas de r\u00e9f\u00e9rence : tenter le mode SFT (si speakers disponibles)
                available = self._model.list_available_spks()
                if available:
                    spk = available[0]
                    log.info("Pas de voix de r\u00e9f\u00e9rence. Utilisation du speaker SFT '%s'.", spk)
                    tts_text = self._format_tts_text(text)
                    gen = self._model.inference_sft(
                        tts_text,
                        spk,
                        stream=False,
                        speed=speed,
                        text_frontend=not raw,
                    )
                else:
                    log.error(
                        "CosyVoice: aucune voix de r\u00e9f\u00e9rence et aucun speaker SFT. "
                        "Configurez un audio de r\u00e9f\u00e9rence dans l'onglet Persona."
                    )
                    return

            for result in gen:
                audio = result.get("tts_speech")
                if audio is None:
                    continue
                # Tensor shape [1, num_samples] \u2192 numpy float32 [num_samples]
                if hasattr(audio, "numpy"):
                    chunk = audio.squeeze().cpu().numpy().astype(np.float32)
                else:
                    chunk = np.asarray(audio, dtype=np.float32).squeeze()
                yield chunk

        except Exception as e:
            log.error("Erreur synth\u00e8se CosyVoice: %s", e, exc_info=True)

    def set_reference_voice(self, audio_path: str, text: str):
        """Change la voix de référence pour le clonage."""
        self._load_reference(audio_path, text)

    def unload(self):
        """Libère le modèle GPU."""
        if self._model is not None:
            del self._model
            self._model = None
            self._is_v3 = False
            self._reference_audio = None
            self._speaker_registered = False

            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            log.info("CosyVoice déchargé.")
