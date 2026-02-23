# Aethon — Assistant Vocal Hybride (Local + Cloud)

## Présentation

Aethon est un assistant vocal hybride, temps réel, tournant sur GPU NVIDIA. Il écoute via le micro, transcrit la parole, génère une réponse via LLM (local Ollama ou cloud Gemini), et la synthétise en voix naturelle.

Deux interfaces : **CLI** (`main.py`) et **Web** (`server/` + `web/`) avec orb animé + chat + settings.

---

## Stack technique

| Brique | Technologie | Détail |
|--------|-------------|--------|
| **STT** | faster-whisper | CTranslate2 GPU CUDA, `large-v3-turbo` par défaut |
| **LLM** | Gemini (défaut) / Ollama | Gemini 2.5 Flash via `google-genai` ou Ollama local (Qwen3) |
| **TTS** | Kokoro (CPU) / Chatterbox (GPU) | Kokoro 82M 10 voix + Chatterbox multilingue 23 langues, clonage zero-shot |
| **VAD** | Silero VAD v6 | torch.hub, chunks 512 samples (32ms @ 16kHz) |
| **Wake word** | OpenWakeWord | ONNX, 4 modèles (`hey_jarvis`, `alexa`, `hey_mycroft`, `ok_google`) |
| **Audio** | sounddevice | PortAudio, capture 16kHz mono, lecture 24kHz, AGC intégré |
| **Mémoire** | SQLite | Tables `memories` + `conversations`, threading.Lock |
| **Tools** | Function calling Gemini | DateTimeTool, SystemInfoTool, extensible via Protocol |
| **Backend** | FastAPI + WebSocket | Serveur Python, bridge pipeline ↔ web |
| **Frontend** | React + Vite + TypeScript | Orb WebGL, chat, settings drawer |
| **Runtime** | Python 3.11 + PyTorch cu124 | CUDA 12.4, venv Windows |

### Dépendances externes (hors pip)
- **Ollama** : `ollama serve` (seulement si backend LLM = ollama)
- **espeak-ng** : requis par Kokoro TTS (MSI, `C:\Program Files\eSpeak NG`)
- **CUDA 12.4** : drivers NVIDIA compatibles
- **Chatterbox** : `pip install chatterbox-tts` (si backend TTS = chatterbox)
- **Node.js** : requis pour le frontend web (npm install dans `web/`)

---

## Architecture

```
E:\TTS\
├── main.py                  # Point d'entrée CLI
├── start_aethon_web.bat     # Lance backend + frontend web
├── setup.bat                # Installation automatique
├── requirements.txt         # Dépendances pip
├── aethon_config.json       # Config persistante JSON
├── aethon_memory.db         # Mémoire SQLite
│
├── aethon/                  # Package Python principal
│   ├── config.py            # Dataclasses : PersonaConfig, LLMConfig, TTSConfig, etc.
│   ├── pipeline.py          # Orchestrateur STT → LLM → TTS + barge-in + wake word
│   ├── audio/
│   │   └── manager.py       # Capture micro + lecture HP + AGC + interruption
│   ├── stt/
│   │   └── transcriber.py   # faster-whisper, lazy loading GPU
│   ├── tts/
│   │   ├── base.py          # Interface TTS abstraite
│   │   ├── kokoro.py        # Kokoro TTS (CPU, 10 voix FR/EN)
│   │   ├── chatterbox.py    # Chatterbox Multilingual (GPU, 23 langues, clonage zero-shot)
│   │   └── cosyvoice.py     # [legacy] CosyVoice2/3 (non utilisé)
│   ├── llm/
│   │   ├── base.py          # Interface LLM abstraite
│   │   ├── ollama.py        # Client Ollama streaming, filtre <think>
│   │   └── gemini.py        # Client Gemini streaming, function calling, Google Search
│   ├── memory/
│   │   └── store.py         # SQLite, extraction de faits, threading.Lock
│   ├── wakeword/
│   │   └── detector.py      # OpenWakeWord ONNX, normalisation conditionnelle
│   ├── tools/
│   │   ├── base.py          # Protocol Tool (name, description, parameters, execute)
│   │   ├── registry.py      # ToolRegistry : register, dispatch, to_gemini_declarations
│   │   ├── datetime_tool.py # Date/heure locale (mapping FR thread-safe)
│   │   └── system_tool.py   # Info système (RAM, VRAM, disk, uptime)
│   ├── voices/
│   │   ├── library.py       # VoiceLibrary : gestion des voix locales
│   │   └── __init__.py
│   └── api/
│       └── server.py        # Serveur HTTP aiohttp (port 8741, legacy CLI)
│
├── server/                  # Backend FastAPI + WebSocket
│   ├── main.py              # Point d'entrée uvicorn
│   ├── dependencies.py      # Injection de dépendances
│   ├── core/
│   │   ├── pipeline_bridge.py  # Bridge pipeline ↔ WebSocket
│   │   └── connection_manager.py  # Gestion connexions WS
│   ├── models/
│   │   └── messages.py      # Schémas Pydantic
│   └── routes/
│       ├── ws.py            # WebSocket streaming
│       ├── config.py        # CRUD config REST
│       ├── voices.py        # Gestion voix REST
│       └── devices.py       # Audio devices REST
│
├── web/                     # Frontend React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/      # Orb, Chat, Controls, Settings
│   │   ├── stores/          # Zustand (config, connection, pipeline)
│   │   ├── types/           # TypeScript interfaces
│   │   └── lib/             # Theme, constants
│   └── package.json
│
├── voices/                  # Échantillons voix pour clonage
└── third_party/
    └── CosyVoice/           # [legacy] Repo CosyVoice2
```

---

## Pipeline — Machine d'état

```
STOPPED → LOADING → IDLE ⇄ LISTENING → THINKING → SPEAKING → IDLE
                                                       ↓ (barge-in)
                                                     IDLE
```

| État | Description |
|------|-------------|
| `STOPPED` | Pipeline arrêté |
| `LOADING` | Chargement modèles (~30s premier lancement) |
| `IDLE` | Attend parole ou wake word |
| `LISTENING` | Capture parole en cours |
| `THINKING` | STT + génération LLM |
| `SPEAKING` | Synthèse TTS + lecture audio |

---

## Contraintes techniques critiques

> **Silero VAD** : chunks de **exactement 512 samples** à 16 kHz (32 ms). Ni plus, ni moins — sinon `ValueError`.

> **Kokoro TTS** : doit être chargé sur **CPU** (`device="cpu"` + `torch.device("cpu")`). Sur GPU → crash `cudnnGetLibConfig` (exit 127).

> **Chatterbox TTS** : `ChatterboxMultilingualTTS.from_pretrained(device="cuda")` — 23 langues natives (français via `language_id="fr"`). Clonage zero-shot via `audio_prompt_path`. Sample rate = 22050 Hz (vs 24000 pour Kokoro) → le pipeline utilise `self.tts.SAMPLE_RATE` dynamique.

> **Gemini** : Google Search et function calling sont **mutuellement exclusifs** dans l'API `generateContent`. Quand les deux sont activés, Google Search est priorisé.

> **AGC** : les chunks silencieux (RMS < 0.002) sont **ignorés** dans le calcul du gain pour éviter l'explosion du gain (55x → saturation). Max gain = 20x.

> **PyTorch** : utiliser l'index **cu124** (pas cu121) pour éviter les incompatibilités cuDNN.

> **espeak-ng** : doit être dans le PATH. Auto-ajouté par `main.py` depuis `C:\Program Files\eSpeak NG`.

> **Windows UTF-8** : `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` requis.

> **SQLite + threads** : `check_same_thread=False` + `threading.Lock` dans `memory/store.py`.

---

## Configuration (dataclasses)

```python
AethonConfig
├── persona: PersonaConfig    # Nom, langue, wake word, voix, instructions, backend TTS
├── llm: LLMConfig           # Backend (gemini/ollama), modèle, température, API key
├── tts: TTSConfig           # Backend (kokoro/chatterbox), voix, vitesse, émotion
├── stt: STTConfig           # Modèle Whisper, device, compute_type
├── audio: AudioConfig       # Sample rate, chunk_duration, silence_timeout, AGC
├── memory: MemoryConfig     # Enabled, db_path, limites contexte
└── tools: ToolsConfig       # DateTime, SystemInfo, API server, port
```

Sauvegarde en `aethon_config.json`. Config modifiable via l'interface web (settings drawer).

---

## Lancement

```bash
venv\Scripts\activate

# Web GUI (recommandé)
start_aethon_web.bat          # Lance backend + frontend

# Ou manuellement
python server/main.py         # Backend (port 8765)
cd web && npm run dev          # Frontend (port 5173)

# Mode CLI
python main.py --no-wake-word           # Écoute permanente
python main.py --model qwen3:8b        # Modèle plus léger
python main.py --language en            # Anglais
python main.py -v                      # Debug
```

---

## Conventions de code

- **Langue du code** : docstrings et commentaires en **français**, noms de variables/fonctions en **anglais**
- **Config** : dataclasses dans `aethon/config.py`, jamais de valeurs hardcodées ailleurs
- **Logs** : `logging` standard, un logger par module (`log = logging.getLogger(__name__)`)
- **Threading** : pipeline dans un thread dédié, communication via WebSocket (server ↔ client)
- **Imports lourds** : lazy loading dans les méthodes `load()` (torch, kokoro, faster_whisper, google.genai)
- **Nettoyage** : chaque composant a une méthode `cleanup()` / `unload()` appelée à l'arrêt
- **Backends switchables** : LLM et TTS utilisent des factories dans `pipeline.py` (`_create_llm`, `_create_tts`)
- **Tools extensibles** : implémenter le `Protocol Tool` dans `tools/base.py`, enregistrer dans `ToolRegistry`

---

## Threading

```
Main Thread (uvicorn)          Pipeline Thread (threading.Thread)
    │                                        │
    │  WebSocket connect ──────────►  PipelineBridge.start()
    │                                        │
    │  ◄──── state_changed (WS msg)          │
    │  ◄──── transcript (WS msg)             │
    │  ◄──── response (WS msg)               │
    │  ◄──── audio_level (WS msg)            │
    │                                        │
    │  WebSocket disconnect ────────►  pipeline.stop()
    │                                        │
    └── WebSocket (async ↔ sync bridge) ─────┘
```

---

## Barge-in

Thread dédié `_monitor_barge_in` surveille le micro pendant que l'assistant parle :
- 3 chunks consécutifs de parole (≈96 ms) déclenchent le barge-in
- Audio coupé (`sd.stop()`), génération LLM annulée (`llm.cancel()`)
- Chunks audio du barge-in conservés comme début de la prochaine collecte de parole
- Pipeline revient en état `IDLE`

---

## Mémoire longue (SQLite)

Tables `memories` (faits extraits) et `conversations` (historique complet).
Extraction déclenchée par marqueurs : `je m'appelle`, `j'habite`, `je travaille`, `j'aime`, `rappelle-toi`, etc.
Faits injectés dans le system prompt au début de chaque session.

---

## Filtrage `<think>` (Qwen3/Ollama)

`ollama.py` filtre en streaming les blocs `<think>...</think>` de Qwen3 :
détection `<think>` → buffer ignoré → détection `</think>` → reprise.
Nettoyage final par regex `re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)`.
