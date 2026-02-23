"""Gestionnaire de connexions WebSocket — broadcast vers tous les clients."""

import asyncio
import logging

from fastapi import WebSocket
from pydantic import BaseModel

log = logging.getLogger(__name__)


class ConnectionManager:
    """Hub WebSocket gerant les connexions actives et le broadcast."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        """Accepte et enregistre une nouvelle connexion WebSocket."""
        await ws.accept()
        self._connections.append(ws)
        log.info("WebSocket connecte (%d clients actifs)", len(self._connections))

    def disconnect(self, ws: WebSocket):
        """Retire une connexion fermee."""
        if ws in self._connections:
            self._connections.remove(ws)
        log.info("WebSocket deconnecte (%d clients actifs)", len(self._connections))

    async def broadcast(self, message: dict):
        """Envoie un message JSON a tous les clients connectes.

        Les clients deconnectes sont retires silencieusement.
        """
        if not self._connections:
            return

        # Snapshot pour eviter les modifications concurrentes pendant l'iteration
        disconnected: list[WebSocket] = []
        tasks = []
        for ws in list(self._connections):
            tasks.append(self._safe_send(ws, message, disconnected))
        await asyncio.gather(*tasks)

        # Nettoyer les clients deconnectes
        for ws in disconnected:
            if ws in self._connections:
                self._connections.remove(ws)

    async def broadcast_model(self, msg: BaseModel):
        """Envoie un modele Pydantic serialise a tous les clients."""
        await self.broadcast(msg.model_dump())

    async def _safe_send(self, ws: WebSocket, message: dict, disconnected: list):
        """Envoie un message a un client, le marque deconnecte en cas d'erreur."""
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)

    @property
    def client_count(self) -> int:
        """Nombre de clients connectes."""
        return len(self._connections)
