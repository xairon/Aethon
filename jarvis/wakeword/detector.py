"""Wake Word — Détection de mot-clé avec OpenWakeWord."""

import logging
import numpy as np

from jarvis.config import JarvisConfig

log = logging.getLogger(__name__)


class WakeWordDetector:
    """Détecte un wake word dans un flux audio continu.

    Inclut une normalisation audio intégrée pour les micros à faible niveau.
    OpenWakeWord attend de l'int16 16kHz mono avec une amplitude raisonnable ;
    un signal trop faible (< 1% du max) empêche toute détection.
    """

    def __init__(self, config: JarvisConfig):
        self._persona = config.persona
        self._audio_config = config.audio
        self._model = None
        self._score_log_counter: int = 0
        self._max_score_seen: float = 0.0
        self._disabled: bool = False  # Désactivé suite à une erreur (sans muter la config)

    def load(self):
        """Charge le modèle OpenWakeWord."""
        if self._model is not None:
            return
        try:
            from openwakeword.model import Model

            log.info(
                "Chargement du wake word '%s' (seuil=%.2f)...",
                self._persona.wake_phrase,
                self._persona.wake_threshold,
            )
            self._model = Model(
                wakeword_models=[self._persona.wake_phrase],
                inference_framework="onnx",
            )
            log.info("Wake word chargé.")
        except ImportError:
            log.warning(
                "openwakeword non installé. Wake word désactivé. "
                "Installer avec: pip install openwakeword"
            )
            self._disabled = True
        except Exception as e:
            log.warning("Erreur chargement wake word: %s. Désactivé.", e)
            self._disabled = True

    @staticmethod
    def _normalize_chunk(chunk: np.ndarray, target_peak: int = 8000) -> np.ndarray:
        """Normalise un chunk int16 à une amplitude pic cible.

        Amplifie les signaux faibles pour que le modèle reçoive un signal
        exploitable, même avec un micro à faible gain.
        """
        peak = int(np.max(np.abs(chunk)))
        if peak < 5:  # Silence complet
            return chunk
        if peak >= target_peak:
            return chunk  # Déjà assez fort
        gain = target_peak / peak
        gain = min(gain, 20.0)  # Aligné sur l'AGC max du pipeline (CLAUDE.md)
        return np.clip(
            chunk.astype(np.float32) * gain, -32768, 32767
        ).astype(np.int16)

    def detect(self, audio_chunk: np.ndarray) -> bool:
        """Vérifie si le wake word est détecté dans un chunk audio.

        Args:
            audio_chunk: Audio int16, 16kHz, mono.

        Returns:
            True si le wake word est détecté.
        """
        if self._disabled or not self._persona.wake_enabled or self._model is None:
            return False

        # Normaliser le chunk seulement si l'AGC n'est pas déjà active
        # (double normalisation = sur-amplification = faux positifs/négatifs)
        if self._audio_config.auto_gain:
            normalized = audio_chunk
        else:
            normalized = self._normalize_chunk(audio_chunk)

        prediction = self._model.predict(normalized)
        score = prediction.get(self._persona.wake_phrase, 0)

        # Suivi du score max pour le debug
        if score > self._max_score_seen:
            self._max_score_seen = score

        # Log périodique du score max vu (toutes les ~5s = ~156 chunks de 32ms)
        self._score_log_counter += 1
        if self._score_log_counter >= 156:
            if self._max_score_seen > 0.01:
                log.info(
                    "Wake score max: %.3f / seuil %.2f",
                    self._max_score_seen,
                    self._persona.wake_threshold,
                )
            self._score_log_counter = 0
            self._max_score_seen = 0.0

        if score > self._persona.wake_threshold:
            log.info("Wake word détecté! (score=%.3f, seuil=%.2f)", score, self._persona.wake_threshold)
            self._model.reset()
            return True
        return False

    def reset(self):
        """Réinitialise l'état du détecteur."""
        if self._model is not None:
            self._model.reset()

    def unload(self):
        """Libère le modèle."""
        self._model = None
