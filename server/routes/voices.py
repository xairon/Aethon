"""Routes REST pour la bibliotheque de voix (locale + HuggingFace)."""

import asyncio
import logging
import re
import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from server.core.connection_manager import ConnectionManager
from server.core.pipeline_bridge import PipelineBridge
from server.dependencies import get_bridge, get_manager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Taille maximale d'upload (50 Mo)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024

# Pattern strict pour les identifiants de voix (previent le path traversal)
_VOICE_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")

# Pattern pour les identifiants HuggingFace (noms de fichiers WAV sur le repo)
_HF_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

# Categories HuggingFace valides
_VALID_HF_CATEGORIES = ("donations", "french", "vctk")


def _validate_voice_id(voice_id: str) -> None:
    """Valide qu'un identifiant de voix ne contient que des caracteres surs.

    Leve HTTPException 400 si le format est invalide.
    """
    if not _VOICE_ID_PATTERN.match(voice_id):
        raise HTTPException(
            status_code=400,
            detail=f"Identifiant de voix invalide: {voice_id!r}. "
                   "Seuls les caracteres a-z, 0-9 et _ sont acceptes.",
        )


def _get_library(bridge: PipelineBridge):
    """Cree une instance VoiceLibrary depuis la config du bridge."""
    from aethon.voices.library import VoiceLibrary
    return VoiceLibrary(bridge.config.persona.voices_path)


@router.get("/voices")
async def list_voices(bridge: PipelineBridge = Depends(get_bridge)):
    """Liste toutes les voix installees localement."""
    lib = _get_library(bridge)
    voices = lib.scan_local()
    return [asdict(v) for v in voices]


@router.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str, bridge: PipelineBridge = Depends(get_bridge)):
    """Supprime une voix de la bibliotheque locale."""
    _validate_voice_id(voice_id)
    lib = _get_library(bridge)
    ok = lib.delete_voice(voice_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Voix introuvable: {voice_id}")
    return {"success": True}


@router.post("/voices/import")
async def import_voice(
    file: UploadFile,
    name: str = Form(...),
    lang: str = Form("fr"),
    gender: str = Form("unknown"),
    bridge: PipelineBridge = Depends(get_bridge),
):
    """Importe un fichier WAV comme nouvelle voix dans la bibliotheque.

    Le fichier est sauvegarde temporairement puis copie dans voices/.
    """
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .wav sont acceptes")

    lib = _get_library(bridge)

    # Sauvegarder dans un fichier temporaire
    tmp_path = None
    try:
        # Lecture par chunks avec verification de taille
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            total_read = 0
            while True:
                chunk = await file.read(64 * 1024)
                if not chunk:
                    break
                total_read += len(chunk)
                if total_read > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Fichier trop volumineux (max {MAX_UPLOAD_SIZE // (1024 * 1024)} Mo)",
                    )
                tmp.write(chunk)

        # Importer dans la bibliotheque (copie + meta.json)
        voice = await asyncio.get_running_loop().run_in_executor(
            None, lib.import_wav, tmp_path, name, lang, gender
        )
        return asdict(voice)

    except HTTPException:
        raise
    except Exception as e:
        log.error("Erreur import voix: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Nettoyer le fichier temporaire
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass


@router.get("/voices/{voice_id}/audio")
async def get_voice_audio(voice_id: str, bridge: PipelineBridge = Depends(get_bridge)):
    """Retourne le fichier WAV d'une voix pour ecoute/previsualisation."""
    _validate_voice_id(voice_id)
    lib = _get_library(bridge)
    path = lib.get_voice_path(voice_id)
    if not path:
        raise HTTPException(status_code=404, detail=f"Voix introuvable: {voice_id}")
    return FileResponse(path, media_type="audio/wav", filename=f"{voice_id}.wav")


@router.get("/hf/voices/{category}")
async def list_hf_voices(category: str, bridge: PipelineBridge = Depends(get_bridge)):
    """Liste les voix disponibles sur HuggingFace pour une categorie.

    Categories disponibles: donations, french, vctk.
    """
    if category not in _VALID_HF_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Categorie invalide. Valeurs acceptees: {', '.join(_VALID_HF_CATEGORIES)}",
        )

    lib = _get_library(bridge)
    voices = await asyncio.get_running_loop().run_in_executor(
        None, lib.list_hf_voices, category
    )
    return [asdict(v) for v in voices]


@router.post("/hf/download")
async def download_hf_voice(
    data: dict,
    bridge: PipelineBridge = Depends(get_bridge),
    manager: ConnectionManager = Depends(get_manager),
):
    """Telecharge une voix depuis HuggingFace en arriere-plan.

    Body: {"hf_id": "xxx_enhanced.wav", "category": "donations"}

    La progression est emise via WebSocket (type: hf_progress).
    """
    hf_id = data.get("hf_id")
    category = data.get("category", "donations")

    if not hf_id:
        raise HTTPException(status_code=400, detail="Champ 'hf_id' requis")

    # Valider hf_id pour prevenir le path traversal
    if not _HF_ID_PATTERN.match(hf_id):
        raise HTTPException(
            status_code=400,
            detail=f"Identifiant HF invalide: {hf_id!r}. "
                   "Seuls les caracteres alphanumeriques, _, . et - sont acceptes.",
        )

    if category not in _VALID_HF_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Categorie invalide. Valeurs acceptees: {', '.join(_VALID_HF_CATEGORIES)}",
        )

    lib = _get_library(bridge)
    loop = asyncio.get_running_loop()

    def _progress_cb(current: int, total: int, name: str):
        """Callback de progression — bridge vers WebSocket."""
        asyncio.run_coroutine_threadsafe(
            manager.broadcast({
                "type": "hf_progress",
                "current": current,
                "total": total,
                "name": name,
            }),
            loop,
        )

    try:
        voice = await loop.run_in_executor(
            None, lib.download_hf_voice, hf_id, category, _progress_cb
        )
        return asdict(voice)
    except Exception as e:
        log.error("Erreur telechargement HF: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
