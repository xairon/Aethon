"""Routes REST pour la detection des peripheriques audio."""

import logging

from fastapi import APIRouter, HTTPException

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/devices")
async def list_devices():
    """Liste les peripheriques audio d'entree et de sortie disponibles.

    Retourne un objet avec deux listes :
        inputs  — microphones (max_input_channels > 0)
        outputs — haut-parleurs (max_output_channels > 0)
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
    except Exception as e:
        log.error("Erreur enumeration peripheriques audio: %s", e)
        raise HTTPException(status_code=500, detail=f"Erreur sounddevice: {e}")

    inputs = []
    outputs = []

    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            inputs.append({
                "id": i,
                "name": d["name"],
                "channels": d["max_input_channels"],
            })
        if d["max_output_channels"] > 0:
            outputs.append({
                "id": i,
                "name": d["name"],
                "channels": d["max_output_channels"],
            })

    return {"inputs": inputs, "outputs": outputs}
