"""Modeles Pydantic pour les messages WebSocket Jarvis."""

from pydantic import BaseModel


class WSMessage(BaseModel):
    """Message WebSocket generique."""
    type: str


class StateMessage(WSMessage):
    """Changement d'etat du pipeline."""
    type: str = "state"
    state: str
    label: str


class TranscriptMessage(WSMessage):
    """Transcription de la parole utilisateur."""
    type: str = "transcript"
    text: str
    timestamp: float


class ResponseMessage(WSMessage):
    """Reponse generee par le LLM."""
    type: str = "response"
    text: str
    timestamp: float


class AudioLevelMessage(WSMessage):
    """Niveau audio du micro (0.0-1.0)."""
    type: str = "audio_level"
    level: float


class ErrorMessage(WSMessage):
    """Message d'erreur."""
    type: str = "error"
    message: str


class ToastMessage(WSMessage):
    """Notification toast pour le frontend."""
    type: str = "toast"
    message: str
    level: str = "info"  # success, warning, error, info


class HFProgressMessage(WSMessage):
    """Progression de telechargement HuggingFace."""
    type: str = "hf_progress"
    current: int
    total: int
    name: str
