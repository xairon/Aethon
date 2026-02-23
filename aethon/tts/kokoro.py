"""TTS — Synthèse vocale via Kokoro."""

import logging
import numpy as np

from aethon.config import TTSConfig

log = logging.getLogger(__name__)


class KokoroSynthesizer:
    """Synthétise du texte en audio avec Kokoro TTS."""

    SAMPLE_RATE = 24000

    def __init__(self, config: TTSConfig):
        self.config = config
        self._pipeline = None

    def load(self):
        """Charge le pipeline Kokoro (lazy loading)."""
        if self._pipeline is not None:
            return
        import torch
        from kokoro import KPipeline

        log.info("Chargement de Kokoro TTS (lang=%s, voix=%s)...", self.config.kokoro_lang, self.config.kokoro_voice)
        # Kokoro est léger (82M params) — le charger sur CPU évite les problèmes cuDNN
        # et libère de la VRAM pour le STT et le LLM.
        with torch.device("cpu"):
            self._pipeline = KPipeline(lang_code=self.config.kokoro_lang, device="cpu")
        log.info("Kokoro TTS chargé (CPU).")

    @staticmethod
    def _to_numpy(audio) -> np.ndarray:
        """Convertit un tensor PyTorch ou numpy array en float32 numpy."""
        if hasattr(audio, "numpy"):
            return audio.cpu().numpy().astype(np.float32)
        return np.asarray(audio, dtype=np.float32)

    def synthesize(self, text: str) -> np.ndarray:
        """Synthétise du texte en audio complet.

        Args:
            text: Texte à synthétiser.

        Returns:
            Audio float32, 24kHz.
        """
        self.load()
        chunks = []
        for _gs, _ps, audio in self._pipeline(
            text, voice=self.config.kokoro_voice, speed=self.config.speed
        ):
            if audio is not None:
                chunks.append(self._to_numpy(audio))

        if not chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(chunks)

    def synthesize_stream(self, text: str, emotion_params=None):
        """Synthetise du texte chunk par chunk (streaming).

        Args:
            text: Texte a synthetiser.
            emotion_params: Ignore par Kokoro (compatibilite pipeline emotion).

        Yields:
            np.ndarray — chunks audio float32, 24kHz.
        """
        text = (text or "").strip()
        if not text:
            return

        self.load()
        for _gs, _ps, audio in self._pipeline(
            text, voice=self.config.kokoro_voice, speed=self.config.speed
        ):
            if audio is not None:
                yield self._to_numpy(audio)

    def unload(self):
        """Libere les ressources."""
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            log.info("Kokoro TTS decharge.")
