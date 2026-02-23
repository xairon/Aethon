"""Outils — Interface abstraite pour les tools Aethon."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    """Interface commune pour tous les outils.

    Chaque outil expose un nom unique, une description pour le LLM,
    un JSON Schema de ses paramètres, et une méthode d'exécution.
    """

    @property
    def name(self) -> str:
        """Nom unique de l'outil (snake_case)."""
        ...

    @property
    def description(self) -> str:
        """Description pour le LLM (quand utiliser cet outil)."""
        ...

    @property
    def parameters(self) -> dict:
        """JSON Schema des paramètres attendus."""
        ...

    def execute(self, **kwargs) -> str:
        """Exécute l'outil et retourne le résultat en texte."""
        ...
