"""Registre centralisé des outils disponibles."""

import logging

from jarvis.tools.base import Tool

log = logging.getLogger(__name__)


class ToolRegistry:
    """Découvre, enregistre et dispatch les appels d'outils."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Enregistre un outil."""
        self._tools[tool.name] = tool
        log.info("Outil enregistré : %s", tool.name)

    def unregister(self, name: str):
        """Retire un outil."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Récupère un outil par nom."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Liste tous les outils enregistrés."""
        return list(self._tools.values())

    def execute(self, name: str, args: dict) -> str:
        """Exécute un outil par nom avec les arguments fournis."""
        tool = self._tools.get(name)
        if not tool:
            return f"Outil '{name}' non trouvé."
        try:
            return tool.execute(**args)
        except Exception as e:
            log.error("Erreur outil %s: %s", name, e, exc_info=True)
            return f"Erreur lors de l'exécution de {name}: {e}"

    def to_gemini_declarations(self) -> list:
        """Convertit les outils en FunctionDeclaration pour le SDK Gemini."""
        from google.genai import types

        declarations = []
        for t in self._tools.values():
            declarations.append(
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=t.parameters,
                )
            )
        return declarations
