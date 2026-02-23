"""Wake Word — Détection par transcription Whisper + matching flou.

Utilise Silero VAD pour détecter le début/fin de parole, accumule
les chunks audio, transcrit via faster-whisper, puis compare le texte
au wake phrase configuré via matching flou.

Avantages par rapport à OpenWakeWord :
- N'importe quelle phrase dans n'importe quelle langue
- Zéro entraînement, zéro dépendance supplémentaire
- Réutilise les modèles STT + VAD déjà chargés
"""

import logging
import re
import unicodedata
from difflib import SequenceMatcher
from enum import Enum, auto

import numpy as np

from jarvis.config import JarvisConfig

log = logging.getLogger(__name__)


class _State(Enum):
    IDLE = auto()
    COLLECTING = auto()


class WhisperWakeDetector:
    """Détecte un wake word en transcrivant la parole via faster-whisper.

    Machine d'état interne :
        IDLE → (VAD speech) → COLLECTING → (silence ≥ 500ms) → transcribe+match → IDLE
    """

    # Paramètres internes (pas exposés dans la config pour simplifier)
    SILENCE_TIMEOUT_MS = 500   # Fin de parole après 500ms de silence
    MIN_SPEECH_MS = 200        # Minimum 200ms de parole
    MAX_SPEECH_MS = 4000       # Maximum 4s (sécurité)
    MATCH_THRESHOLD = 0.6      # Seuil de similarité SequenceMatcher
    CHUNK_MS = 32              # Durée d'un chunk (512 samples @ 16kHz)

    def __init__(self, config: JarvisConfig):
        self._persona = config.persona
        self._audio_config = config.audio
        self._transcriber = None   # Référence vers le Transcriber partagé
        self._vad_model = None     # Référence vers le Silero VAD partagé
        self._sample_rate: int = 16000

        # État interne
        self._state = _State.IDLE
        self._speech_chunks: list[np.ndarray] = []
        self._speech_ms: int = 0
        self._silence_ms: int = 0

        # Cache du wake phrase normalisé
        self._wake_phrase_normalized: str = ""

        # Stats pour le debug
        self._transcribe_count: int = 0

    def load(self):
        """Pré-calcule le wake phrase normalisé."""
        raw = self._persona.wake_phrase
        self._wake_phrase_normalized = self._normalize_text(raw)
        log.info(
            "WhisperWakeDetector chargé : phrase='%s' → normalisé='%s'",
            raw, self._wake_phrase_normalized,
        )

    def set_shared_models(self, transcriber, vad_model):
        """Injecte les modèles partagés (appelé par le pipeline après load_all).

        Args:
            transcriber: Instance de jarvis.stt.transcriber.Transcriber (déjà chargé).
            vad_model: Modèle Silero VAD (déjà chargé).
        """
        self._transcriber = transcriber
        self._vad_model = vad_model

    def detect(self, audio_chunk: np.ndarray) -> bool:
        """Traite un chunk audio (512 samples, int16, 16kHz).

        Returns:
            True si le wake word est détecté dans la transcription.
        """
        if not self._persona.wake_enabled:
            return False
        if self._transcriber is None or self._vad_model is None:
            return False

        is_speech = self._check_vad(audio_chunk)

        if self._state == _State.IDLE:
            if is_speech:
                self._state = _State.COLLECTING
                self._speech_chunks = [audio_chunk]
                self._speech_ms = self.CHUNK_MS
                self._silence_ms = 0
            return False

        # État COLLECTING
        self._speech_chunks.append(audio_chunk)

        if is_speech:
            self._speech_ms += self.CHUNK_MS
            self._silence_ms = 0
        else:
            self._silence_ms += self.CHUNK_MS

        # Conditions de fin de collecte
        total_ms = len(self._speech_chunks) * self.CHUNK_MS
        should_transcribe = (
            self._silence_ms >= self.SILENCE_TIMEOUT_MS
            or total_ms >= self.MAX_SPEECH_MS
        )

        if should_transcribe:
            if self._speech_ms >= self.MIN_SPEECH_MS:
                result = self._transcribe_and_match()
                self._reset_collection()
                return result
            # Pas assez de parole (bruit, claquement)
            self._reset_collection()

        return False

    def _check_vad(self, chunk: np.ndarray) -> bool:
        """Passe un chunk dans Silero VAD."""
        import torch

        try:
            if chunk.dtype == np.int16:
                audio_f32 = chunk.astype(np.float32) / 32768.0
            else:
                audio_f32 = chunk.astype(np.float32)

            tensor = torch.from_numpy(audio_f32)
            confidence = self._vad_model(tensor, self._sample_rate).item()
            return confidence > 0.5
        except Exception as e:
            log.warning("WhisperWake VAD erreur : %s", e)
            return False

    def _transcribe_and_match(self) -> bool:
        """Transcrit l'audio collecté et compare au wake phrase."""
        audio = np.concatenate(self._speech_chunks)
        duration_s = len(audio) / self._sample_rate
        self._transcribe_count += 1

        log.debug(
            "WhisperWake: transcription #%d (%.1fs, %d chunks)...",
            self._transcribe_count, duration_s, len(self._speech_chunks),
        )

        try:
            text = self._transcriber.transcribe(audio, self._sample_rate)
        except Exception as e:
            log.warning("WhisperWake: erreur transcription : %s", e)
            return False

        if not text or len(text.strip()) < 2:
            log.debug("WhisperWake: transcription vide, ignoré.")
            return False

        text_norm = self._normalize_text(text)
        match = self._fuzzy_match(text_norm, self._wake_phrase_normalized)

        if match:
            log.info(
                "Wake word détecté! '%s' → '%s' (phrase='%s')",
                text, text_norm, self._wake_phrase_normalized,
            )
        else:
            log.debug(
                "WhisperWake: pas de match '%s' → '%s' (phrase='%s')",
                text, text_norm, self._wake_phrase_normalized,
            )

        return match

    def _reset_collection(self):
        """Remet l'état interne à IDLE."""
        self._state = _State.IDLE
        self._speech_chunks.clear()
        self._speech_ms = 0
        self._silence_ms = 0

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalise du texte pour le matching flou.

        - Minuscules
        - Suppression des accents (é → e, ü → u, etc.)
        - Suppression de la ponctuation
        - Underscores → espaces (pour convertir "hey_jarvis" → "hey jarvis")
        - Espaces normalisés
        """
        text = text.lower().strip()
        # Underscores → espaces (noms de modèles OWW)
        text = text.replace("_", " ")
        # Supprimer les accents
        nfkd = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in nfkd if not unicodedata.combining(c))
        # Supprimer la ponctuation
        text = re.sub(r"[^\w\s]", "", text)
        # Normaliser les espaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _fuzzy_match(transcription: str, wake_phrase: str) -> bool:
        """Compare la transcription au wake phrase (4 stratégies en cascade).

        1. Substring exact (après normalisation)
        2. Tous les mots du wake phrase présents dans la transcription
        3. SequenceMatcher ratio >= seuil
        4. Pour phrases courtes : ratio par mot individuel
        """
        if not transcription or not wake_phrase:
            return False

        # 1. Substring direct
        if wake_phrase in transcription:
            return True

        # 2. Tous les mots du wake phrase présents dans la transcription
        wake_words = wake_phrase.split()
        trans_words = transcription.split()
        if len(wake_words) >= 2 and all(w in trans_words for w in wake_words):
            return True

        # 3. SequenceMatcher global
        ratio = SequenceMatcher(None, transcription, wake_phrase).ratio()
        if ratio >= WhisperWakeDetector.MATCH_THRESHOLD:
            return True

        # 4. Pour les phrases courtes (1-2 mots), vérifier mot par mot
        if len(wake_words) <= 2:
            phrase_joined = wake_phrase.replace(" ", "")
            for word in trans_words:
                word_ratio = SequenceMatcher(None, word, phrase_joined).ratio()
                if word_ratio >= 0.7:
                    return True

        return False

    def reset(self):
        """Réinitialise l'état du détecteur (appelé après activation)."""
        self._reset_collection()
        # Reset l'état du VAD (il est stateful)
        if self._vad_model is not None:
            try:
                self._vad_model.reset_states()
            except Exception:
                pass

    def unload(self):
        """Libère les références (les modèles sont gérés par le pipeline)."""
        self._transcriber = None
        self._vad_model = None
        self._speech_chunks.clear()
