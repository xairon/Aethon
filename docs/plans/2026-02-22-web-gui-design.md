# Jarvis Web GUI — Design Document

**Date** : 2026-02-22
**Objectif** : Remplacement total de l'interface PyQt6 par une application web moderne
**Statut** : Approuve

---

## 1. Decisions architecturales

| Aspect | Choix | Justification |
|--------|-------|---------------|
| Frontend | React 19 + Vite + TypeScript | Ecosysteme le plus large, Tailwind CSS, composants riches |
| Backend | FastAPI + uvicorn | Async natif, WebSocket integre, Pydantic, documentation auto |
| Communication | WebSocket unique + REST | Temps reel pour etat/audio, REST pour config/CRUD |
| Audio | Hybride (serveur par defaut + navigateur optionnel) | Zero latence en local, accessible a distance |
| Orb | Redesign complet — raymarching WebGL2 | Full-screen, shaders proceduraux, fluid dynamics |
| Layout | Full-screen orb + chat overlay glassmorphism | Experience immersive, l'animation est l'interface |
| Settings | Drawer lateral glisse depuis la droite | Scrollable, sections collapsables, glassmorphism |
| Lancement | Deux process separes (backend + frontend) | Dev-friendly, hot reload |
| Theme | Obsidian dark (porte depuis PyQt6) | Continuite visuelle |

---

## 2. Architecture globale

```
Navigateur (React + Vite)
     |
     | WebSocket ws://localhost:8765
     | + REST http://localhost:8765/api
     |
FastAPI Server (Python)
     |
     |-- ConnectionManager (WebSocket hub, broadcast)
     |-- PipelineBridge (thread → async bridge)
     |-- AudioBridge (streaming audio optionnel)
     |
     |-- JarvisPipeline (inchange)
         |-- AudioManager (sounddevice, micro + HP)
         |-- STT (faster-whisper, CUDA)
         |-- LLM (Gemini / Ollama)
         |-- TTS (Kokoro / Chatterbox)
         |-- WakeWord (OpenWakeWord)
         |-- Memory (SQLite)
         |-- VoiceLibrary (local + HuggingFace)
```

**Point cle** : Le package `jarvis/` (pipeline, STT, TTS, LLM, memory, voices, etc.) reste 100% inchange. Seul le layer GUI est remplace.

---

## 3. Protocole WebSocket

### Serveur → Client

```json
{"type": "state", "state": "listening", "color": "#4f8fff", "label": "Ecoute..."}
{"type": "transcript", "text": "Bonjour Jarvis", "timestamp": 1708617600}
{"type": "response", "text": "Salut ! Comment vas-tu ?", "timestamp": 1708617601}
{"type": "audio_level", "level": 0.42}
{"type": "config", "config": {...}}
{"type": "voices", "voices": [{...}]}
{"type": "hf_voices", "category": "donations", "voices": [{...}]}
{"type": "hf_progress", "current": 2, "total": 5, "name": "Donation 0A67"}
{"type": "error", "message": "..."}
{"type": "toast", "message": "...", "level": "success|warning|error|info"}
```

Audio binaire optionnel (mode navigateur) :
```json
{"type": "audio_chunk", "data": "<base64 PCM int16>", "sample_rate": 24000}
```

### Client → Serveur

```json
{"type": "command", "action": "start|stop"}
{"type": "config_update", "config": {...}}
{"type": "voice_preview", "voice_id": "ff_siwis", "backend": "kokoro"}
{"type": "hf_browse", "category": "donations"}
{"type": "hf_download", "items": [{"hf_id": "...", "category": "..."}]}
{"type": "voice_import", "name": "...", "lang": "fr", "gender": "unknown"}
{"type": "audio_mode", "mode": "server|browser"}
```

### Throttling

- `audio_level` : max 20 messages/seconde (50ms minimum entre deux envois)
- `audio_chunk` : envoye par blocs de 4096 samples (pas par chunk de 512)
- Reconnexion automatique cote client avec backoff exponentiel (1s, 2s, 4s, max 30s)

---

## 4. REST API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/status` | Etat pipeline + info serveur |
| GET | `/api/config` | Config complete (JarvisConfig) |
| PUT | `/api/config` | Sauvegarde config |
| GET | `/api/voices` | Liste voix locales |
| POST | `/api/voices/import` | Upload WAV (multipart/form-data) |
| DELETE | `/api/voices/{id}` | Supprime une voix |
| GET | `/api/voices/{id}/audio` | Stream WAV d'une voix (pour preview) |
| GET | `/api/hf/voices/{category}` | Liste voix HuggingFace |
| POST | `/api/hf/download` | Telecharge voix HF (async, progression via WS) |
| GET | `/api/devices` | Liste peripheriques audio (in + out) |
| POST | `/api/speak` | TTS texte → WAV (clients externes) |

---

## 5. Frontend — Structure

```
web/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
│
└── src/
    ├── main.tsx
    ├── App.tsx
    │
    ├── stores/                    (Zustand)
    │   ├── useConnection.ts       WebSocket lifecycle + reconnect
    │   ├── usePipeline.ts         State, transcript, response, audio level
    │   ├── useConfig.ts           Config CRUD
    │   └── useAudio.ts            Remote audio playback
    │
    ├── hooks/
    │   ├── useWebSocket.ts        WebSocket with auto-reconnect
    │   └── useAnimationFrame.ts   rAF hook for orb renderer
    │
    ├── components/
    │   ├── layout/
    │   │   └── AppShell.tsx       Root layout (full-screen orb + overlays)
    │   │
    │   ├── orb/
    │   │   ├── Orb.tsx            Canvas container + WebGL context
    │   │   ├── OrbRenderer.ts     Raymarching engine (class)
    │   │   ├── shaders/
    │   │   │   ├── raymarcher.frag   Main fragment shader
    │   │   │   ├── fluid.frag        Fluid simulation pass
    │   │   │   ├── bloom.frag        Bloom post-processing
    │   │   │   └── compose.frag      Final composition
    │   │   └── OrbFallback.tsx    Canvas 2D fallback (pas de WebGL)
    │   │
    │   ├── chat/
    │   │   ├── ChatOverlay.tsx    Glass container + auto-scroll
    │   │   └── ChatBubble.tsx     Message bubble (user/assistant)
    │   │
    │   ├── controls/
    │   │   ├── ControlBar.tsx     Bottom bar (state + buttons)
    │   │   ├── StartStopButton.tsx
    │   │   └── AudioMeter.tsx     Horizontal level indicator
    │   │
    │   └── settings/
    │       ├── SettingsDrawer.tsx  Slide-in panel (glassmorphism)
    │       ├── sections/
    │       │   ├── PersonaSection.tsx
    │       │   ├── VoiceSection.tsx
    │       │   ├── IntelligenceSection.tsx
    │       │   ├── ToolsSection.tsx
    │       │   └── AdvancedSection.tsx
    │       └── VoiceBrowserModal.tsx   HF voice browser
    │
    ├── lib/
    │   ├── theme.ts              Couleurs Obsidian (constantes)
    │   ├── api.ts                Fetch wrappers REST
    │   └── audio.ts              Web Audio API helpers
    │
    └── types/
        ├── config.ts             Miroir TypeScript des dataclasses Python
        ├── pipeline.ts           PipelineState enum
        ├── voice.ts              VoiceMeta, HFVoiceInfo
        └── messages.ts           Types messages WebSocket
```

---

## 6. Layout — Full-screen Orb + Overlay

### Desktop (>1024px)

```
┌──────────────────────────────────────────────────────────┐
│                                                           │
│                  ORB PLEIN ECRAN                          │
│                  (Canvas WebGL2)                          │
│                  100vh × 100vw                            │
│                  Raymarching + fluid                      │
│                  + particules                             │
│                                                           │
│  ┌─ Chat Overlay ────────────────────────────────────┐   │
│  │  backdrop-filter: blur(16px)                       │   │
│  │  background: rgba(13,16,23,0.7)                    │   │
│  │  max-height: 40vh, scrollable                      │   │
│  │                                                    │   │
│  │  Toi: Bonjour Jarvis                              │   │
│  │  Jarvis: Salut ! Comment ca va ?                  │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌─ Control Bar ─────────────────────────────────────┐   │
│  │  ● Pret    ═══════════    [⚙ Settings] [▶ Start] │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Mobile (<768px)

```
┌──────────────────────┐
│                      │
│   ORB (50vh)         │
│                      │
│                      │
├──────────────────────┤
│  Chat (scrollable)   │
│  max-height: 40vh    │
│                      │
│  Toi: ...            │
│  Jarvis: ...         │
│                      │
├──────────────────────┤
│ ● Pret  [⚙] [▶]    │
└──────────────────────┘
```

### Settings Drawer

- Slide depuis la droite, largeur 420px (desktop) / 100vw (mobile)
- Glassmorphism (blur 20px, bg rgba(13,16,23,0.85))
- Sections collapsables (accordeon)
- Animation d'ouverture : 300ms ease-out + overlay sombre sur l'orb
- Fermeture : clic sur l'overlay OU bouton ✕ OU Escape

---

## 7. Orb — Raymarching WebGL2

### Architecture de rendu

Multi-pass rendering pipeline :

```
Pass 1: Fluid Simulation (ping-pong FBO)
  - 256×256 resolution
  - Advection + diffusion + external forces (audio)
  - Output: velocity + density texture

Pass 2: Raymarching (main render)
  - Full resolution
  - SDF sphere + 4 octaves simplex noise 3D
  - Fluid texture mapped on sphere surface
  - Fresnel + subsurface scattering + iridescence
  - Volumetric light scattering (god rays)

Pass 3: Bloom (gaussian blur)
  - 1/4 resolution horizontal + vertical
  - Threshold: luminance > 0.8
  - Radius proportionnel a audio level

Pass 4: Composition finale
  - Combine raymarching + bloom
  - Chromatic aberration (subtle, 0.5-2px)
  - Vignette
  - Output → canvas
```

### Uniforms CPU → GPU

```glsl
uniform float u_time;           // Temps en secondes
uniform float u_audioLevel;     // 0.0 - 1.0 (RMS normalise)
uniform float u_deform;         // 0.0 - 1.0 (amplitude noise)
uniform float u_glow;           // 0.0 - 1.0 (intensite bloom)
uniform vec3  u_colorPrimary;   // Couleur dominante (depend de l'etat)
uniform vec3  u_colorSecondary; // Couleur secondaire
uniform float u_fluidForce;     // Force injection dans le fluide
uniform float u_particleSpeed;  // Vitesse des particules
uniform int   u_state;          // 0-5 (PipelineState)
uniform vec2  u_resolution;     // Taille canvas
uniform vec2  u_mouse;          // Position souris (normalise 0-1)
```

### Comportement par etat

| Etat | Noise | Fluid | God rays | Particules | Bloom | Couleur |
|------|-------|-------|----------|------------|-------|---------|
| STOPPED | freq=0.5, amp=0.02 | Off | Off | Rares, lentes | 0.1 | #4a5568 gris |
| IDLE | freq=1.0, amp=0.05 | Lent, pastel | Glow doux | Orbitantes | 0.3 | #34d399 vert |
| LOADING | freq=2.0, amp=0.08 | Rotation | Arc tournant | Accelerent | 0.5 | #fbbf24 amber |
| LISTENING | freq=3+audio×5, amp=0.15+audio×0.3 | Reactif audio | Pulsent | Attirees centre | 0.4+audio | #4f8fff bleu |
| THINKING | freq=4.0, amp=0.12 | Vortex | Spirale | Spiralent | 0.6 | #917cf7 violet |
| SPEAKING | freq=2+audio×8, amp=0.10+audio×0.4 | Explosif | Rayons intenses | Explosent | 0.5+audio×0.5 | #22d3ee cyan |

### Transitions

- Toutes les transitions : interpolation cubique 800ms
- Couleurs : interpolation HSL (evite les gris intermediaires)
- Le fluide conserve son momentum entre les etats
- Les particules morphent entre les patterns (pas de teleportation)

### Fallback Canvas 2D

Si `WebGL2` non disponible :
- Cercles concentriques animes (gradient radial)
- CSS `filter: blur()` pour le glow
- `requestAnimationFrame` pour la respiration
- Couleurs reactives a l'etat (memes couleurs)

---

## 8. Backend FastAPI — Structure

```
server/
├── main.py                        uvicorn entry + CORS + lifespan
├── requirements.txt               fastapi, uvicorn[standard], websockets
│
├── core/
│   ├── connection_manager.py      WebSocket hub (multi-client broadcast)
│   ├── pipeline_bridge.py         Thread pipeline ↔ async FastAPI bridge
│   └── audio_bridge.py            Optional: audio streaming via WebSocket
│
├── routes/
│   ├── ws.py                      WebSocket endpoint principal
│   ├── config.py                  GET/PUT /api/config
│   ├── voices.py                  CRUD /api/voices + HF browser
│   ├── pipeline.py                start/stop/status
│   ├── devices.py                 Audio devices listing
│   └── speak.py                   POST /api/speak (TTS externe)
│
└── models/
    └── messages.py                Pydantic models (WS message types)
```

### ConnectionManager

```python
class ConnectionManager:
    """Gere les connexions WebSocket multiples avec broadcast."""

    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    async def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, message: dict):
        """Envoie un message JSON a tous les clients connectes."""
        data = json.dumps(message)
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                pass  # cleanup au prochain disconnect

    async def broadcast_binary(self, data: bytes):
        """Envoie des donnees binaires (audio) a tous les clients."""
        for ws in self._connections:
            try:
                await ws.send_bytes(data)
            except Exception:
                pass
```

### PipelineBridge

```python
class PipelineBridge:
    """Execute JarvisPipeline dans un thread, bridge vers async WebSocket."""

    def __init__(self, config: JarvisConfig, manager: ConnectionManager):
        self._config = config
        self._manager = manager
        self._pipeline: JarvisPipeline | None = None
        self._thread: Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self):
        """Lance le pipeline dans un thread dedie avec callbacks bridges."""
        self._loop = asyncio.get_running_loop()
        self._thread = Thread(target=self._run_pipeline, daemon=True)
        self._thread.start()

    def _run_pipeline(self):
        """Thread principal du pipeline (bloquant)."""
        self._pipeline = JarvisPipeline(self._config)
        self._pipeline.on_state_change = self._bridge_state
        self._pipeline.on_transcript = self._bridge_transcript
        self._pipeline.on_response = self._bridge_response
        self._pipeline.on_audio_level = self._bridge_audio_level
        self._pipeline.run()

    def _bridge_state(self, state: str):
        """Bridge thread → async : etat pipeline."""
        asyncio.run_coroutine_threadsafe(
            self._manager.broadcast({"type": "state", "state": state}),
            self._loop,
        )
    # ... idem pour transcript, response, audio_level
```

---

## 9. Theme Obsidian (Tailwind)

```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        bg: {
          void: '#08090f',
          base: '#0d1017',
          surface: '#131720',
          raised: '#1a1f2e',
          elevated: '#232a3c',
        },
        text: {
          DEFAULT: '#e2e8f0',
          secondary: '#7e8ca2',
          muted: '#4a5568',
          inverse: '#08090f',
        },
        accent: {
          DEFAULT: '#4f8fff',
          hover: '#6aa0ff',
          violet: '#917cf7',
        },
        green: '#34d399',
        amber: '#fbbf24',
        red: '#f87171',
        cyan: '#22d3ee',
        border: {
          DEFAULT: '#1e2536',
          focus: '#4f8fff',
        },
      },
      fontFamily: {
        sans: ['"Segoe UI Variable"', '"Inter"', 'system-ui', 'sans-serif'],
      },
      backdropBlur: {
        glass: '16px',
      },
    },
  },
}
```

---

## 10. Settings Drawer — Sections

Reprend exactement les memes options que les 4 onglets PyQt6, en layout vertical scrollable avec accordeons collapsables.

### Persona
- Nom (text input)
- Langue (select dropdown)
- Wake Word : enabled toggle, phrase select, seuil slider, mode radio

### Voix
- Backend TTS : radio Kokoro / Chatterbox
- Voix Kokoro : select + preview button
- Voix Chatterbox : voice library browser
  - Liste scrollable des voix locales (avec play/delete)
  - Bouton "Importer un WAV" → upload dialog
  - Bouton "Telecharger depuis HF" → modal browser
- Vitesse : slider 0.5x - 2.0x
- Parametres Chatterbox (si actif) : exaggeration, cfg_weight, temperature, etc.

### Intelligence
- Backend : radio Gemini / Ollama
- Config Gemini : modele select, API key, thinking budget slider
- Config Ollama : base URL, modele select + refresh
- Temperature : slider 0.0 - 2.0
- Max tokens : slider 10 - 2000

### Outils
- Google Search toggle
- Date & Heure toggle
- Infos Systeme toggle
- API Server : enabled toggle + port input

### Avance
- Audio : input/output device selects, gain slider, AGC toggle + target
- STT : modele select, device radio, compute type, langue, VAD
- Memoire : enabled toggle, limites sliders

### Instructions (sous-section de Persona)
- Liste toggleable d'instructions
- Chaque instruction : label + toggle switch
- Ajout d'instructions custom

---

## 11. Dependances

### Backend (Python)

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
websockets>=13.0
python-multipart>=0.0.18    # pour upload fichiers
```

Les dependances existantes (torch, faster-whisper, google-genai, etc.) sont deja installees.

### Frontend (Node.js)

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zustand": "^5.0.0",
    "framer-motion": "^12.0.0",
    "three": "^0.172.0",
    "@types/three": "^0.172.0"
  },
  "devDependencies": {
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.0"
  }
}
```

---

## 12. Lancement

### Developpement

```bash
# Terminal 1 — Backend
cd E:\TTS
python server/main.py
# → uvicorn sur http://localhost:8765

# Terminal 2 — Frontend
cd E:\TTS\web
npm run dev
# → Vite sur http://localhost:5173
# → Proxy /api et /ws vers localhost:8765
```

### Production

```bash
# Build frontend
cd web && npm run build  # → web/dist/

# Lancer le serveur (sert aussi le build statique optionnellement)
python server/main.py
```

---

## 13. Migration — Ce qui change / Ce qui reste

### Inchange (zero modification)

- `jarvis/pipeline.py` — Orchestrateur STT→LLM→TTS
- `jarvis/audio/manager.py` — Capture micro + lecture HP
- `jarvis/stt/transcriber.py` — faster-whisper
- `jarvis/tts/kokoro.py`, `chatterbox.py` — Backends TTS
- `jarvis/llm/gemini.py`, `ollama.py` — Backends LLM
- `jarvis/memory/store.py` — SQLite
- `jarvis/wakeword/detector.py` — OpenWakeWord
- `jarvis/tools/` — Function calling
- `jarvis/voices/library.py` — Voice library backend
- `jarvis/config.py` — Dataclasses config

### Remplace (PyQt6 → Web)

- `jarvis/gui/` (tout le dossier) → `server/` + `web/`
- `jarvis/api/server.py` (aiohttp) → `server/routes/` (FastAPI)
- `gui_main.py` → `server/main.py`

### Nouveau

- `server/` — Backend FastAPI complet
- `web/` — Frontend React complet
- Shaders GLSL pour l'orb
- TypeScript types miroir des dataclasses Python
