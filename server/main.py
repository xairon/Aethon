"""Serveur Web Jarvis — FastAPI + WebSocket.

Point d'entree du backend web. Lance un serveur FastAPI sur le port 8765
avec des routes REST (config, voix, peripheriques) et un endpoint WebSocket
pour la communication temps reel avec le frontend React.

Usage:
    python -m server.main
    # ou depuis la racine du projet :
    python server/main.py
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ajouter la racine du projet au path pour les imports jarvis.*
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.dependencies import bridge, manager
from server.routes import config, devices, voices, ws

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle du serveur : initialise le bridge au demarrage, cleanup a l'arret."""
    bridge.set_loop(asyncio.get_running_loop())
    log.info("Serveur Jarvis demarre sur http://127.0.0.1:8765")
    yield
    # Arret propre du pipeline si actif
    await bridge.stop()
    log.info("Serveur Jarvis arrete.")


app = FastAPI(title="Jarvis", lifespan=lifespan)

# CORS — necessaire en dev (Vite sur localhost:5173), inoffensif en prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrer les routes
app.include_router(ws.router)
app.include_router(config.router)
app.include_router(voices.router)
app.include_router(devices.router)

# Servir le frontend React builde en production
dist_dir = Path(__file__).resolve().parent.parent / "web" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")


if __name__ == "__main__":
    # Configuration des logs — console + fichier pour capturer les crashes
    _log_file = Path(__file__).resolve().parent.parent / "jarvis_server.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(str(_log_file), encoding="utf-8"),
        ],
    )

    # Windows UTF-8
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Ajouter espeak-ng au PATH (requis par Kokoro TTS)
    espeak = r"C:\Program Files\eSpeak NG"
    if os.path.isdir(espeak) and espeak not in os.environ.get("PATH", ""):
        os.environ["PATH"] = espeak + os.pathsep + os.environ.get("PATH", "")

    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info",
    )
