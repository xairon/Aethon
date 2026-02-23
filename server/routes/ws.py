"""Route WebSocket — communication bidirectionnelle temps reel avec le frontend."""

import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from server.core.connection_manager import ConnectionManager
from server.core.pipeline_bridge import PipelineBridge, STATE_LABELS
from server.dependencies import get_bridge, get_manager

log = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    bridge: PipelineBridge = Depends(get_bridge),
    manager: ConnectionManager = Depends(get_manager),
):
    """Endpoint WebSocket principal.

    Messages entrants (client → serveur) :
        {"type": "command", "action": "start"|"stop"}
        {"type": "text_input", "text": "..."}
        {"type": "config_update", "config": {...}}

    Messages sortants (serveur → client) :
        {"type": "state", "state": "...", "label": "..."}
        {"type": "transcript", "text": "...", "timestamp": ...}
        {"type": "response", "text": "...", "timestamp": ...}
        {"type": "audio_level", "level": 0.0-1.0}
        {"type": "error", "message": "..."}
        {"type": "toast", "message": "...", "level": "info"}
    """
    await manager.connect(ws)
    try:
        # Envoyer l'etat actuel a la connexion
        current = bridge.current_state
        log.info("Nouveau client WS — etat actuel: %s", current)
        await ws.send_json({
            "type": "state",
            "state": current,
            "label": STATE_LABELS.get(current, current),
        })

        while True:
            try:
                data = await ws.receive_json()
            except ValueError:
                log.warning("Message non-JSON recu sur WS.")
                await ws.send_json({
                    "type": "error",
                    "message": "Message non-JSON recu. Seul le JSON est accepte.",
                })
                continue

            # Log TOUT message recu pour le debug
            log.info("WS message recu: %s", data)

            if not isinstance(data, dict):
                await ws.send_json({
                    "type": "error",
                    "message": "Format invalide: un objet JSON est attendu.",
                })
                continue

            msg_type = data.get("type")

            if msg_type == "command":
                action = data.get("action")
                await _handle_command(action, bridge, ws)

            elif msg_type == "text_input":
                text = data.get("text", "").strip()
                await _handle_text_input(text, bridge, ws)

            elif msg_type == "config_update":
                config_data = data.get("config", {})
                await _handle_config_update(config_data, bridge, ws)

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"Type de message inconnu: {msg_type}",
                })

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        log.error("Erreur WebSocket: %s", e, exc_info=True)
        manager.disconnect(ws)


async def _handle_command(action: str, bridge: PipelineBridge, ws: WebSocket):
    """Traite une commande start/stop depuis le client."""
    if action == "start":
        if bridge.is_running:
            await ws.send_json({
                "type": "toast",
                "message": "Le pipeline tourne deja.",
                "level": "warning",
            })
            return
        try:
            log.info("Commande 'start' recue, lancement du pipeline...")
            await bridge.start()
            # Confirmation — le bridge a deja broadcast "loading" via await
            log.info("Pipeline lance avec succes.")
            await ws.send_json({
                "type": "toast",
                "message": "Pipeline demarre — chargement des modeles...",
                "level": "info",
            })
        except Exception as e:
            log.error("Echec demarrage pipeline: %s", e, exc_info=True)
            await ws.send_json({
                "type": "error",
                "message": f"Erreur demarrage: {e}",
            })

    elif action == "stop":
        if not bridge.is_running:
            await ws.send_json({
                "type": "toast",
                "message": "Le pipeline est deja arrete.",
                "level": "warning",
            })
            return
        try:
            log.info("Commande 'stop' recue, arret du pipeline...")
            await bridge.stop()
            log.info("Pipeline arrete avec succes.")
            await ws.send_json({
                "type": "toast",
                "message": "Pipeline arrete.",
                "level": "success",
            })
        except Exception as e:
            log.error("Echec arret pipeline: %s", e, exc_info=True)
            await ws.send_json({
                "type": "error",
                "message": f"Erreur arret: {e}",
            })

    else:
        await ws.send_json({
            "type": "error",
            "message": f"Action inconnue: {action}",
        })


async def _handle_text_input(text: str, bridge: PipelineBridge, ws: WebSocket):
    """Injecte du texte dans le pipeline (bypass STT)."""
    if not text:
        await ws.send_json({
            "type": "error",
            "message": "Texte vide.",
        })
        return
    if not bridge.is_running:
        await ws.send_json({
            "type": "toast",
            "message": "Le pipeline n'est pas demarre.",
            "level": "warning",
        })
        return
    bridge.send_text(text)
    log.info("Texte injecte dans le pipeline: %s", text[:80])


async def _handle_config_update(config_data: dict, bridge: PipelineBridge, ws: WebSocket):
    """Met a jour la configuration depuis le client WebSocket."""
    try:
        bridge.update_config(config_data)
        await ws.send_json({
            "type": "toast",
            "message": "Configuration sauvegardee.",
            "level": "success",
        })
    except Exception as e:
        log.error("Erreur mise a jour config: %s", e)
        await ws.send_json({
            "type": "error",
            "message": f"Erreur configuration: {e}",
        })
