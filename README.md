# Aethon

**Real-time hybrid voice assistant** — local + cloud, GPU-accelerated, with barge-in support.

Aethon listens through your microphone, transcribes speech in real-time, generates intelligent responses via LLM (local or cloud), and speaks back with natural-sounding voice synthesis. It features wake word detection, long-term memory, function calling, and a full desktop GUI with an animated orb.

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
- **REST API** — HTTP server for external clients (Samsung Watch, home automation)
- **Desktop GUI** — PyQt6 with animated orb, chat bubbles, toast notifications, system tray
- **Web GUI** — Vite + React + TypeScript frontend with WebSocket streaming

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
| **GUI** | PyQt6 (desktop) / React + Vite (web) |
| **API** | aiohttp REST + WebSocket |
| **Runtime** | Python 3.11, PyTorch cu124, CUDA 12.4 |

---

## Quick Start

### Prerequisites

- **NVIDIA GPU** with CUDA 12.4+ drivers
- **Python 3.11**
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
```

### Running

```bash
# Desktop GUI (recommended)
python gui_main.py

# CLI mode
python main.py                    # with wake word
python main.py --no-wake-word     # always listening
python main.py --language en      # English
python main.py -v                 # verbose logging
```

On first launch, models are downloaded automatically (~30s).

---

## Configuration

All settings are saved to `aethon_config.json` and editable via the GUI settings dialog.

| Section | Options |
|---------|---------|
| **Persona** | Name, language, wake word, voice, system instructions |
| **Intelligence** | LLM backend, model, temperature, max tokens |
| **TTS** | Backend (Kokoro/Chatterbox), voice, speed, emotion |
| **Tools** | Function calling, Google Search, API server |
| **Advanced** | STT model, audio devices, memory, AGC |

---

## Project Structure

```
├── main.py              # CLI entry point
├── gui_main.py          # GUI entry point
├── aethon/
│   ├── pipeline.py      # Main orchestrator (STT → LLM → TTS + barge-in)
│   ├── config.py        # Dataclass configuration
│   ├── audio/           # Microphone capture, playback, AGC
│   ├── stt/             # faster-whisper transcription
│   ├── tts/             # Kokoro, Chatterbox, emotion processing
│   ├── llm/             # Gemini, Ollama clients
│   ├── memory/          # SQLite long-term memory
│   ├── wakeword/        # OpenWakeWord detection
│   ├── tools/           # Function calling (datetime, sysinfo, extensible)
│   ├── api/             # HTTP/WebSocket server
│   └── gui/             # PyQt6 desktop interface
├── server/              # FastAPI backend for web GUI
├── web/                 # React + Vite web frontend
└── voices/              # Custom voice samples for cloning
```

---

## License

MIT

---

*Named after Aethon, one of the horses that pulled the chariot of the Sun in Greek mythology.*
