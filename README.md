# Aethon

**Real-time hybrid voice assistant** — local + cloud, GPU-accelerated, with barge-in support.

Aethon listens through your microphone, transcribes speech in real-time, generates intelligent responses via LLM (local or cloud), and speaks back with natural-sounding voice synthesis. It features wake word detection, long-term memory, function calling, and a web interface with an animated orb.

---

## Features

- **Hybrid LLM** — Gemini 2.5 Flash (cloud) or Ollama/Qwen3 (local), switchable at runtime
- **Multi-TTS** — Chatterbox Multilingual (GPU, 23 languages, zero-shot voice cloning) or Kokoro 82M (CPU fallback)
- **Real-time STT** — faster-whisper with CTranslate2 CUDA acceleration
- **Barge-in** — interrupt the assistant mid-sentence, it stops and listens
- **Wake word** — OpenWakeWord with multiple hotwords
- **Emotion-aware TTS** — LLM emits emotion tags, TTS adjusts expressiveness per segment
- **Voice cloning** — zero-shot cloning from a short audio sample via Chatterbox
- **Long-term memory** — SQLite-backed fact extraction and recall across sessions
- **Function calling** — extensible tool system (date/time, system info, custom tools)
- **Google Search** — grounded responses with live web search via Gemini
- **Web GUI** — React + Vite + TypeScript with WebGL orb, chat, and settings
- **CLI mode** — lightweight terminal interface for headless use

---

## Architecture

```
Microphone → VAD (Silero) → STT (faster-whisper) → LLM (Gemini/Ollama) → TTS (Chatterbox/Kokoro) → Speaker
                                                         ↑                        ↓
                                                    Memory (SQLite)          Barge-in detection
                                                    Tools (function calling)
```

### Pipeline States

```
STOPPED → LOADING → IDLE ⇄ LISTENING → THINKING → SPEAKING → IDLE
                                                      ↓ (barge-in)
                                                    IDLE
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **STT** | faster-whisper (CTranslate2 CUDA, large-v3-turbo) |
| **LLM** | Gemini 2.5 Flash / Ollama (Qwen3) |
| **TTS** | Chatterbox Multilingual (GPU) / Kokoro 82M (CPU) |
| **VAD** | Silero VAD v6 (torch.hub) |
| **Wake Word** | OpenWakeWord (ONNX) |
| **Audio** | sounddevice (PortAudio) with AGC |
| **Memory** | SQLite with fact extraction |
| **Backend** | FastAPI + WebSocket |
| **Frontend** | React + Vite + TypeScript |
| **Runtime** | Python 3.11, PyTorch cu124, CUDA 12.4 |

---

## Quick Start

### Prerequisites

- **NVIDIA GPU** with CUDA 12.4+ drivers
- **Python 3.11**
- **Node.js** (for the web frontend)
- **espeak-ng** — [download MSI](https://github.com/espeak-ng/espeak-ng/releases) (required for Kokoro TTS)
- **Ollama** (optional) — only if using local LLM backend

### Installation

```bash
git clone https://github.com/xairon/Aethon.git
cd Aethon

# Automated setup (Windows)
setup.bat

# Or manual
python -m venv venv
venv\Scripts\activate
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
pip install chatterbox-tts  # GPU TTS (optional, requires numpy<1.26)

# Frontend
cd web && npm install && cd ..
```

### Running

```bash
# Web GUI (recommended)
start_aethon_web.bat

# Or manually
python server/main.py         # Backend (port 8765)
cd web && npm run dev          # Frontend (port 5173)

# CLI mode
python main.py                    # with wake word
python main.py --no-wake-word     # always listening
python main.py --language en      # English
python main.py -v                 # verbose logging
```

On first launch, models are downloaded automatically (~30s).

---

## Configuration

All settings are saved to `aethon_config.json` and editable via the web settings drawer.

| Section | Options |
|---------|---------|
| **Persona** | Name, language, wake word, voice, system instructions |
| **Intelligence** | LLM backend, model, temperature, max tokens |
| **Voice** | Backend (Kokoro/Chatterbox), voice, speed, emotion |
| **Tools** | Function calling, Google Search |
| **Advanced** | STT model, audio devices, memory, AGC |

---

## Project Structure

```
├── main.py              # CLI entry point
├── aethon/              # Core Python package
│   ├── pipeline.py      # Main orchestrator (STT → LLM → TTS + barge-in)
│   ├── config.py        # Dataclass configuration
│   ├── audio/           # Microphone capture, playback, AGC
│   ├── stt/             # faster-whisper transcription
│   ├── tts/             # Kokoro, Chatterbox, emotion processing
│   ├── llm/             # Gemini, Ollama clients
│   ├── memory/          # SQLite long-term memory
│   ├── wakeword/        # OpenWakeWord detection
│   ├── tools/           # Function calling (datetime, sysinfo, extensible)
│   ├── voices/          # Voice library management
│   └── api/             # Legacy aiohttp server (CLI mode)
├── server/              # FastAPI backend + WebSocket bridge
├── web/                 # React + Vite + TypeScript frontend
└── voices/              # Custom voice samples for cloning
```

---

## License

MIT

---

*Named after Aethon, one of the horses that pulled the chariot of the Sun in Greek mythology.*
