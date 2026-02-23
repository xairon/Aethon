"""LLM — Interface abstraite pour les backends LLM."""

from __future__ import annotations

import logging
from typing import Protocol, Generator, runtime_checkable

log = logging.getLogger(__name__)


@runtime_checkable
class LLMBackend(Protocol):
    """Interface commune pour tous les backends LLM (Ollama, Gemini, etc.)."""

    def set_context(self, system_prompt: str, memories: list[str] | None = None) -> None:
        """Initialise le contexte de conversation."""
        ...

    def add_user_message(self, text: str) -> None:
        """Ajoute un message utilisateur à l'historique."""
        ...

    def generate_stream(self) -> Generator[str, None, None]:
        """Génère une réponse en streaming, yield par phrase complète."""
        ...

    def cancel(self) -> None:
        """Annule la génération en cours (barge-in)."""
        ...

    def get_partial_response(self) -> str:
        """Retourne la réponse partielle générée jusqu'ici."""
        ...

    def check_connection(self) -> bool:
        """Vérifie que le backend est accessible."""
        ...

    def cleanup(self) -> None:
        """Libère les ressources."""
        ...
