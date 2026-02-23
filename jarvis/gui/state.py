"""Pipeline state enum with display data."""

from enum import Enum


class PipelineState(Enum):
    STOPPED = "stopped"
    LOADING = "loading"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


# Obsidian palette — state colors
STATE_COLORS: dict[PipelineState, str] = {
    PipelineState.STOPPED: "#4a5568",   # Muted grey
    PipelineState.LOADING: "#fbbf24",   # Warm amber
    PipelineState.IDLE: "#34d399",      # Mint green
    PipelineState.LISTENING: "#4f8fff", # Electric blue
    PipelineState.THINKING: "#917cf7",  # Violet
    PipelineState.SPEAKING: "#22d3ee",  # Cyan
}

STATE_LABELS: dict[PipelineState, str] = {
    PipelineState.STOPPED: "Arrêté",
    PipelineState.LOADING: "Chargement...",
    PipelineState.IDLE: "Prêt",
    PipelineState.LISTENING: "Écoute...",
    PipelineState.THINKING: "Réflexion...",
    PipelineState.SPEAKING: "Parle...",
}
