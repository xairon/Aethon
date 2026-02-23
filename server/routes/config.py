"""Routes REST pour la configuration Aethon."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from server.core.pipeline_bridge import PipelineBridge
from server.dependencies import get_bridge

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/config")
async def get_config(bridge: PipelineBridge = Depends(get_bridge)):
    """Retourne la configuration actuelle en JSON."""
    return bridge.config.to_dict()


@router.put("/config")
async def update_config(request: Request, bridge: PipelineBridge = Depends(get_bridge)):
    """Met a jour la configuration et sauvegarde sur disque.

    Accepte un dictionnaire partiel ou complet.
    Le pipeline doit etre redemarre pour appliquer les changements.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON invalide")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Le body doit etre un objet JSON")

    try:
        bridge.update_config(data)
        return {"success": True}
    except Exception as e:
        log.error("Erreur mise a jour config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status(bridge: PipelineBridge = Depends(get_bridge)):
    """Retourne l'etat actuel du pipeline."""
    return {
        "state": bridge.current_state,
        "running": bridge.is_running,
    }
