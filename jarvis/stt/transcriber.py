"""STT — Transcription vocale via faster-whisper."""

import logging
import numpy as np

from jarvis.config import STTConfig

log = logging.getLogger(__name__)


class Transcriber:
    """Transcrit de l'audio en texte avec faster-whisper."""

    def __init__(self, config: STTConfig):
        self.config = config
        self._model = None

    def load(self):
        """Charge le modèle faster-whisper (lazy loading)."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        log.info("Chargement de faster-whisper %s sur %s...", self.config.model, self.config.device)
        self._model = WhisperModel(
            self.config.model,
            device=self.config.device,
            compute_type=self.config.compute_type,
        )
        log.info("faster-whisper chargé.")

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcrit un segment audio en texte.

        Args:
            audio: Audio int16 ou float32, mono.
            sample_rate: Taux d'échantillonnage.

        Returns:
            Texte transcrit.
        """
        self.load()

        # Convertir en float32 normalisé si nécessaire
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0

        # Normalisation par pic — essentielle pour les micros à faible niveau.
        # Amène le pic audio à TARGET_PEAK pour que Whisper reçoive un signal
        # de bonne amplitude, indépendamment du gain du micro.
        audio = self._normalize(audio)

        segments, info = self._model.transcribe(
            audio,
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad_filter,
            vad_parameters={"threshold": self.config.vad_threshold},
        )

        text = " ".join(seg.text.strip() for seg in segments).strip()
        if text:
            log.debug("Transcription [%s, %.1fs]: %s", info.language, info.duration, text)
        return text

    @staticmethod
    def _normalize(audio: np.ndarray, target_peak: float = 0.5) -> np.ndarray:
        """Normalise l'audio float32 à une amplitude pic cible.

        Amplifie les signaux faibles sans réduire les signaux forts.
        Protège contre les divisions par zéro et limite le gain max à 100x.
        """
        peak = float(np.max(np.abs(audio)))
        if peak < 1e-6:  # Silence complet
            return audio
        gain = target_peak / peak
        gain = min(gain, 100.0)  # Sécurité : pas plus de 100x
        if gain > 1.05:  # Ne pas amplifier si déjà au bon niveau
            log.debug("STT normalisation: peak=%.5f, gain=%.1fx", peak, gain)
            audio = audio * gain
        return audio

    def unload(self):
        """Ne libère PAS le modèle GPU — crash Windows connu (CTranslate2#1782)."""
        # Setting _model = None triggers GC of the CTranslate2 CUDA model,
        # which segfaults on Windows. Keep it alive for process lifetime.
        pass
