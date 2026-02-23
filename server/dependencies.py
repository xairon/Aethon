"""Injection de dependances — singletons partages entre les routes et le main."""

from server.core.connection_manager import ConnectionManager
from server.core.pipeline_bridge import PipelineBridge

# Singletons crees une seule fois au demarrage du module
manager = ConnectionManager()
bridge = PipelineBridge(manager)


def get_manager() -> ConnectionManager:
    """Retourne le gestionnaire de connexions WebSocket (singleton)."""
    return manager


def get_bridge() -> PipelineBridge:
    """Retourne le bridge pipeline (singleton)."""
    return bridge
