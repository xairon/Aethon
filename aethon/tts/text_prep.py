"""Preprocesseur de texte pour un rendu TTS naturel.

Optimise le texte avant envoi a Chatterbox/Kokoro :
- Nettoyage des artefacts LLM (markdown, URLs, etc.)
- Conversion des ellipses en pauses reelles (virgules)
  AVANT que punc_norm() de Chatterbox ne les ecrase
- Ajout de micro-pauses (virgules) aux points de respiration naturels
- Protection de la ponctuation expressive

Remplace l'ancien ``_clean_for_tts()`` de pipeline.py.

NOTE sur punc_norm() de Chatterbox (mtl_tts.py) :
- ``...`` et ``\u2026`` → ``, `` (virgule)
- ``:`` → ``,``
- ``;`` → ``, ``
- Smart quotes normalises
- Point auto-ajoute si pas de ponctuation finale
On pre-traite les ellipses nous-memes pour les convertir en pauses
plus naturelles (virgule + espace) au lieu de laisser Chatterbox
le faire brutalement.
"""

import logging
import re

log = logging.getLogger(__name__)

# Connecteurs logiques devant lesquels une micro-pause est naturelle
_BREATH_BEFORE = re.compile(
    r"(?<=[a-z\u00e0\u00e2\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00fb\u00f9\u00fc\u00e7])\s+"
    r"(?=(?:mais|cependant|toutefois|n\u00e9anmoins|pourtant|"
    r"donc|alors|ensuite|puis|sinon|d'ailleurs|en fait|"
    r"parce que|puisque|car|afin que|pour que)\b)",
    re.IGNORECASE,
)

# Interjections naturelles qui beneficient d'une pause apres elles
_INTERJECTION_RE = re.compile(
    r"\b(ah|oh|eh|hmm|bon|ben|bref|enfin|tiens|bah|euh|hein|allons|voyons|"
    r"dis donc|quand m\u00eame|du coup)\b(?!\s*[,!?.])",
    re.IGNORECASE,
)


def prepare_for_tts(text: str) -> str:
    """Prepare le texte pour un rendu TTS optimal.

    Enchaine : nettoyage artefacts \u2192 ponctuation expressive \u2192
    micro-pauses \u2192 normalisation.
    """
    if not text or not text.strip():
        return ""

    text = _clean_llm_artifacts(text)
    text = _normalize_punctuation_for_prosody(text)
    text = _add_breath_pauses(text)
    text = _normalize_whitespace(text)

    return text.strip()


def _clean_llm_artifacts(text: str) -> str:
    """Retire les artefacts courants des LLMs."""
    # Liens markdown [texte](url) \u2192 texte
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # URLs brutes
    text = re.sub(r"https?://\S+", "", text)
    # Markdown bold/italic
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    # Backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Tirets de liste en debut de ligne
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    # Dashes longs isoles \u2192 virgule (pause naturelle)
    text = re.sub(r"\s*[\u2014\u2013]\s*", ", ", text)
    return text


def _normalize_punctuation_for_prosody(text: str) -> str:
    """Convertit la ponctuation en formes optimales pour le TTS.

    Chatterbox punc_norm() va convertir ``...`` en ``, `` de toute facon.
    On le fait nous-memes de facon plus intelligente :
    - Ellipses en fin de phrase \u2192 point (sentence-ending pause)
    - Ellipses mid-phrase \u2192 virgule (breath pause)
    - Points-virgules \u2192 virgules
    - Deux-points \u2192 virgules
    """
    # Ellipses unicode
    text = text.replace("\u2026", "...")
    # Ellipses en fin de texte \u2192 point (pause finale naturelle)
    text = re.sub(r"\.\.\.\s*$", ".", text)
    # Ellipses mid-texte \u2192 virgule (micro-pause)
    text = text.replace("...", ",")
    # Point-virgule \u2192 virgule
    text = text.replace(";", ",")
    return text


def _add_breath_pauses(text: str) -> str:
    """Ajoute des virgules aux points de respiration naturels."""
    # Virgule avant les connecteurs logiques
    text = _BREATH_BEFORE.sub(", ", text)
    # Virgule apres les interjections non suivies de ponctuation
    text = _INTERJECTION_RE.sub(r"\1,", text)
    return text


def _normalize_whitespace(text: str) -> str:
    """Normalise les espaces et evite les doubles virgules."""
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text
