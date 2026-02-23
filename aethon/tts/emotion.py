"""Presets d'emotion et parser de tags pour TTS expressif.

Le LLM genere des tags [emotion] inline dans ses reponses.
Ce module les parse et retourne des segments avec les parametres
Chatterbox optimises pour chaque emotion.

Exemple d'entree LLM :
    "[joyeux] Ah, super nouvelle ! [neutre] La meteo sera nuageuse."

Resultat parse :
    [EmotionSegment("Ah, super nouvelle !", "joyeux", preset_joyeux),
     EmotionSegment("La meteo sera nuageuse.", "neutre", preset_neutre)]
"""

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmotionPreset:
    """Parametres Chatterbox pour une emotion donnee."""

    exaggeration: float
    cfg_weight: float
    temperature: float


# ── Table des presets ─────────────────────────────────────────────
#
# Logique :
#   exaggeration haute + cfg basse = expressif, rythme libre
#   exaggeration basse + cfg haute = pose, structure
#
# temperature controle la variabilite prosodique :
#   basse = consistant, haute = plus varie/naturel

EMOTION_PRESETS: dict[str, EmotionPreset] = {
    "neutre":  EmotionPreset(exaggeration=0.45, cfg_weight=0.50, temperature=0.80),
    "joyeux":  EmotionPreset(exaggeration=0.85, cfg_weight=0.30, temperature=0.90),
    "triste":  EmotionPreset(exaggeration=0.35, cfg_weight=0.60, temperature=0.70),
    "surpris": EmotionPreset(exaggeration=0.90, cfg_weight=0.25, temperature=0.95),
    "taquin":  EmotionPreset(exaggeration=0.75, cfg_weight=0.35, temperature=0.90),
    "serieux": EmotionPreset(exaggeration=0.30, cfg_weight=0.65, temperature=0.70),
    "doux":    EmotionPreset(exaggeration=0.40, cfg_weight=0.45, temperature=0.75),
    "excite":  EmotionPreset(exaggeration=0.95, cfg_weight=0.20, temperature=1.00),
}

DEFAULT_EMOTION = "neutre"

# Regex : matche [emotion] pour toutes les cles connues
_KNOWN_EMOTIONS = "|".join(EMOTION_PRESETS.keys())
_TAG_RE = re.compile(
    r"\[(" + _KNOWN_EMOTIONS + r")\]",
    re.IGNORECASE,
)


@dataclass
class EmotionSegment:
    """Segment de texte avec son emotion associee."""

    text: str
    emotion: str
    preset: EmotionPreset


def parse_emotion_tags(text: str) -> list[EmotionSegment]:
    """Parse les tags [emotion] dans le texte LLM.

    Retourne une liste de segments avec leur emotion.
    Si aucun tag n'est trouve, applique une heuristique basee
    sur la ponctuation.
    """
    matches = list(_TAG_RE.finditer(text))

    if not matches:
        # Fallback : heuristique ponctuation
        emotion = _detect_punctuation_emotion(text)
        preset = EMOTION_PRESETS[emotion]
        cleaned = text.strip()
        if cleaned:
            return [EmotionSegment(text=cleaned, emotion=emotion, preset=preset)]
        return []

    segments: list[EmotionSegment] = []

    # Texte avant le premier tag (rare mais possible)
    if matches[0].start() > 0:
        prefix = text[: matches[0].start()].strip()
        if prefix:
            emotion = _detect_punctuation_emotion(prefix)
            segments.append(EmotionSegment(
                text=prefix, emotion=emotion, preset=EMOTION_PRESETS[emotion],
            ))

    # Chaque tag delimite un segment
    for i, match in enumerate(matches):
        emotion_key = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        segment_text = text[start:end].strip()

        if segment_text:
            preset = EMOTION_PRESETS.get(emotion_key, EMOTION_PRESETS[DEFAULT_EMOTION])
            segments.append(EmotionSegment(
                text=segment_text, emotion=emotion_key, preset=preset,
            ))

    return segments


def _detect_punctuation_emotion(text: str) -> str:
    """Heuristique de detection d'emotion basee sur la ponctuation.

    Utilise en fallback quand le LLM n'emet pas de tags.
    """
    text = text.strip()
    excl = text.count("!")
    quest = text.count("?")

    if excl >= 2:
        return "excite"
    if excl >= 1 and quest >= 1:
        return "surpris"
    if excl == 1:
        return "joyeux"
    # Les questions restent neutres — le ? donne deja une intonation montante
    return DEFAULT_EMOTION


def strip_emotion_tags(text: str) -> str:
    """Retire tous les tags [emotion] du texte (pour affichage/memoire)."""
    import re as _re
    text = _TAG_RE.sub("", text)
    return _re.sub(r"\s{2,}", " ", text).strip()
