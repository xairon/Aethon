# Jarvis V2 — Hybrid Agent Architecture

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transformer Jarvis en assistant vocal hybride (local STT + Gemini cloud LLM + CosyVoice3 TTS local) avec architecture agent extensible, GUI intuitive par Personas, et function calling.

**Architecture:** Mode B Hybrid — Whisper (local GPU) pour le STT, Gemini 2.5 Flash (SDK natif google-genai) pour le LLM avec function calling + search grounding, CosyVoice3 (local GPU) pour le TTS avec clonage de voix. Ollama + Kokoro gardés en fallback. Système de Personas (profils d'identité switchables) avec instructions modulaires. Architecture Tools extensible pour futur agent (domotique, montre, etc.).

**Tech Stack:** Python 3.11, PyQt6, google-genai SDK, faster-whisper, CosyVoice3/Kokoro, SQLite, sounddevice, aiohttp (Phase 3)

---

## Phase 1 : Gemini LLM + Bugs + Fondation

### Task 1: Créer l'abstraction LLM (Protocol)

**Files:**
- Create: `jarvis/llm/base.py`

**Step 1:** Créer le Protocol LLM qui définit l'interface commune Gemini/Ollama.

```python
"""LLM — Interface abstraite pour les backends LLM."""

from __future__ import annotations

import logging
from typing import Protocol, Generator, runtime_checkable

log = logging.getLogger(__name__)


@runtime_checkable
class LLMBackend(Protocol):
    """Interface commune pour tous les backends LLM (Ollama, Gemini, etc.)."""

    def set_context(self, system_prompt: str, memories: list[str] | None = None) -> None:
        """Initialise le contexte de conversation."""
        ...

    def add_user_message(self, text: str) -> None:
        """Ajoute un message utilisateur à l'historique."""
        ...

    def generate_stream(self) -> Generator[str, None, None]:
        """Génère une réponse en streaming, yield par phrase complète."""
        ...

    def cancel(self) -> None:
        """Annule la génération en cours (barge-in)."""
        ...

    def get_partial_response(self) -> str:
        """Retourne la réponse partielle générée jusqu'ici."""
        ...

    def check_connection(self) -> bool:
        """Vérifie que le backend est accessible."""
        ...

    def cleanup(self) -> None:
        """Libère les ressources."""
        ...
```

**Step 2:** Commit.

```bash
git add jarvis/llm/base.py
git commit -m "feat(llm): add LLMBackend protocol for backend abstraction"
```

---

### Task 2: Adapter Ollama au Protocol (renommer chat.py → ollama.py)

**Files:**
- Rename: `jarvis/llm/chat.py` → `jarvis/llm/ollama.py`
- Modify: `jarvis/llm/ollama.py` (adapter à LLMBackend)

**Step 1:** Renommer et adapter. Changements clés :
- `set_context()` prend `system_prompt: str` + `memories` au lieu de juste `memories`
- Ajouter `cancel()` qui ferme la connexion httpx
- Ajouter `get_partial_response()` qui retourne le texte généré jusqu'ici
- Tracker `_current_response` pendant le streaming
- Ajouter `_cancel_event = threading.Event()`

```python
"""LLM — Backend Ollama (local) via HTTP streaming."""

import json
import logging
import re
import threading
from collections.abc import Generator

import httpx

from jarvis.config import LLMConfig

log = logging.getLogger(__name__)


class OllamaLLM:
    """Backend LLM local via Ollama HTTP API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.conversation: list[dict] = []
        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self._cancel_event = threading.Event()
        self._current_response = ""
        self._response: httpx.Response | None = None

    def set_context(self, system_prompt: str, memories: list[str] | None = None) -> None:
        """Réinitialise le contexte de conversation avec les mémoires."""
        full_prompt = system_prompt
        if memories:
            memory_text = "\n".join(f"- {m}" for m in memories)
            full_prompt += (
                f"\n\nVoici ce que tu sais sur l'utilisateur (mémoire) :\n{memory_text}"
            )
        self.conversation = [{"role": "system", "content": full_prompt}]

    def add_user_message(self, text: str) -> None:
        """Ajoute un message utilisateur à l'historique."""
        self.conversation.append({"role": "user", "content": text})

    def generate_stream(self) -> Generator[str, None, None]:
        """Génère une réponse en streaming, yield par phrase."""
        self._cancel_event.clear()
        self._current_response = ""

        try:
            self._response = self._client.send(
                self._client.build_request(
                    "POST",
                    "/api/chat",
                    json={
                        "model": self.config.model,
                        "messages": self.conversation,
                        "stream": True,
                        "think": False,
                        "options": {
                            "temperature": self.config.temperature,
                            "num_predict": self.config.max_tokens,
                        },
                    },
                ),
                stream=True,
            )
            self._response.raise_for_status()
        except httpx.HTTPError as e:
            log.error("Erreur Ollama: %s", e)
            yield "Désolé, je n'ai pas pu générer de réponse."
            return

        full_response = ""
        buffer = ""
        in_think_block = False
        sentence_endings = {".", "!", "?", "…", "\n"}

        try:
            for line in self._response.iter_lines():
                if self._cancel_event.is_set():
                    break
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if data.get("done"):
                    break

                token = data.get("message", {}).get("content", "")
                if not token:
                    continue

                full_response += token

                # Filtrer les blocs <think>...</think> de Qwen3
                if "<think>" in token:
                    in_think_block = True
                if in_think_block:
                    if "</think>" in token:
                        in_think_block = False
                        after = token.split("</think>", 1)[-1]
                        if after:
                            buffer += after
                    continue

                buffer += token

                # Yield dès qu'on a une phrase complète
                for ending in sentence_endings:
                    if ending in buffer:
                        idx = buffer.rindex(ending) + len(ending)
                        sentence = buffer[:idx].strip()
                        buffer = buffer[idx:]
                        if sentence:
                            self._current_response += sentence + " "
                            yield sentence
                        break
        finally:
            # Fermer le stream proprement
            if self._response:
                self._response.close()
                self._response = None

        # Flush le reste du buffer
        remaining = buffer.strip()
        if remaining:
            remaining = re.sub(r"<think>.*?</think>", "", remaining, flags=re.DOTALL).strip()
            if remaining:
                self._current_response += remaining + " "
                yield remaining

        # Sauvegarder la réponse complète dans l'historique
        clean_response = re.sub(
            r"<think>.*?</think>", "", full_response, flags=re.DOTALL
        ).strip()
        if clean_response:
            self.conversation.append(
                {"role": "assistant", "content": clean_response}
            )
        self._trim_history()

    def cancel(self) -> None:
        """Annule la génération en cours."""
        self._cancel_event.set()
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass
            self._response = None

    def get_partial_response(self) -> str:
        """Retourne la réponse partielle générée jusqu'ici."""
        return self._current_response.strip()

    def check_connection(self) -> bool:
        """Vérifie que Ollama est accessible."""
        try:
            r = self._client.get("/api/tags")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def _trim_history(self, max_turns: int = 20):
        """Garde seulement les N derniers tours + le system prompt."""
        if len(self.conversation) <= 1 + max_turns * 2:
            return
        system = self.conversation[0]
        recent = self.conversation[-(max_turns * 2):]
        self.conversation = [system] + recent

    def cleanup(self) -> None:
        """Ferme le client HTTP."""
        self.cancel()
        self._client.close()

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass
```

**Step 2:** Mettre à jour les imports dans `jarvis/llm/__init__.py`.

**Step 3:** Commit.

```bash
git add jarvis/llm/
git commit -m "refactor(llm): rename chat.py to ollama.py, implement LLMBackend protocol with cancel support"
```

---

### Task 3: Créer le backend Gemini (SDK natif google-genai)

**Files:**
- Create: `jarvis/llm/gemini.py`

**Step 1:** Implémenter GeminiLLM avec le SDK google-genai. Fonctionnalités :
- Streaming via `generate_content_stream()`
- Function calling (architecture prête, tools injectés plus tard)
- Google Search grounding (configurable)
- Cancel via Event
- Sentence splitting identique à OllamaLLM

```python
"""LLM — Backend Gemini (cloud) via SDK google-genai."""

import logging
import threading
from collections.abc import Generator

from jarvis.config import LLMConfig

log = logging.getLogger(__name__)


class GeminiLLM:
    """Backend LLM cloud via Google Gemini API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._messages: list[dict] = []
        self._system_prompt = ""
        self._cancel_event = threading.Event()
        self._current_response = ""
        self._tool_declarations: list = []
        self._tool_executor = None  # Callable[[str, dict], str] — set by pipeline
        self._init_client()

    def _init_client(self):
        """Initialise le client Gemini."""
        from google import genai

        api_key = self.config.api_key
        if not api_key:
            import os
            api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            log.error("Clé API Gemini manquante. Configure-la dans les settings.")
            return
        self._client = genai.Client(api_key=api_key)
        log.info("Client Gemini initialisé (modèle: %s)", self.config.model)

    def set_context(self, system_prompt: str, memories: list[str] | None = None) -> None:
        """Réinitialise le contexte de conversation."""
        full_prompt = system_prompt
        if memories:
            memory_text = "\n".join(f"- {m}" for m in memories)
            full_prompt += (
                f"\n\nVoici ce que tu sais sur l'utilisateur (mémoire) :\n{memory_text}"
            )
        self._system_prompt = full_prompt
        self._messages = []

    def set_tools(self, declarations: list, executor=None):
        """Configure les tools (function calling).

        Args:
            declarations: Liste de types.FunctionDeclaration.
            executor: Callable(name, args) -> str pour exécuter les tools.
        """
        self._tool_declarations = declarations
        self._tool_executor = executor

    def add_user_message(self, text: str) -> None:
        """Ajoute un message utilisateur."""
        self._messages.append({"role": "user", "parts": [{"text": text}]})

    def generate_stream(self) -> Generator[str, None, None]:
        """Génère une réponse en streaming, yield par phrase complète."""
        from google.genai import types

        self._cancel_event.clear()
        self._current_response = ""

        if not self._client:
            yield "Erreur : client Gemini non initialisé."
            return

        # Construire la config
        tools = []
        if self.config.enable_search:
            tools.append(types.Tool(google_search=types.GoogleSearch()))
        if self._tool_declarations:
            tools.append(types.Tool(function_declarations=self._tool_declarations))

        config = types.GenerateContentConfig(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            system_instruction=self._system_prompt,
            tools=tools if tools else None,
        )

        buffer = ""
        sentence_endings = {".", "!", "?", "…", "\n"}
        full_text = ""

        try:
            for chunk in self._client.models.generate_content_stream(
                model=self.config.model,
                contents=self._messages,
                config=config,
            ):
                if self._cancel_event.is_set():
                    break

                # Gérer les function calls
                if hasattr(chunk, "function_calls") and chunk.function_calls:
                    yield from self._handle_function_calls(chunk.function_calls)
                    continue

                # Texte normal
                text = ""
                if hasattr(chunk, "text") and chunk.text:
                    text = chunk.text
                elif hasattr(chunk, "candidates") and chunk.candidates:
                    for candidate in chunk.candidates:
                        if hasattr(candidate, "content") and candidate.content:
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    text += part.text

                if not text:
                    continue

                full_text += text
                buffer += text

                # Yield dès qu'on a une phrase complète
                for ending in sentence_endings:
                    if ending in buffer:
                        idx = buffer.rindex(ending) + len(ending)
                        sentence = buffer[:idx].strip()
                        buffer = buffer[idx:]
                        if sentence:
                            self._current_response += sentence + " "
                            yield sentence
                        break

        except Exception as e:
            log.error("Erreur Gemini streaming: %s", e)
            yield f"Désolé, erreur de communication avec Gemini."
            return

        # Flush le reste du buffer
        remaining = buffer.strip()
        if remaining:
            self._current_response += remaining + " "
            yield remaining

        # Sauvegarder dans l'historique
        if full_text.strip():
            self._messages.append(
                {"role": "model", "parts": [{"text": full_text.strip()}]}
            )
        self._trim_history()

    def _handle_function_calls(self, function_calls) -> Generator[str, None, None]:
        """Exécute les function calls et retourne les résultats au modèle."""
        if not self._tool_executor:
            log.warning("Function call reçu mais pas d'executor configuré.")
            return

        for fc in function_calls:
            name = fc.name
            args = dict(fc.args) if fc.args else {}
            log.info("Function call: %s(%s)", name, args)

            try:
                result = self._tool_executor(name, args)
                log.info("Function result: %s", result[:200] if result else "")
            except Exception as e:
                log.error("Erreur exécution tool %s: %s", name, e)
                result = f"Erreur: {e}"

            # TODO: Renvoyer le résultat au modèle pour qu'il génère la réponse finale
            # Pour l'instant, on yield directement le résultat
            if result:
                yield result

    def cancel(self) -> None:
        """Annule la génération en cours."""
        self._cancel_event.set()

    def get_partial_response(self) -> str:
        """Retourne la réponse partielle."""
        return self._current_response.strip()

    def check_connection(self) -> bool:
        """Vérifie que l'API Gemini est accessible."""
        if not self._client:
            return False
        try:
            # Test simple : lister les modèles
            models = list(self._client.models.list())
            return len(models) > 0
        except Exception as e:
            log.error("Connexion Gemini échouée: %s", e)
            return False

    def _trim_history(self, max_turns: int = 20):
        """Garde seulement les N derniers tours."""
        if len(self._messages) <= max_turns * 2:
            return
        self._messages = self._messages[-(max_turns * 2):]

    def cleanup(self) -> None:
        """Libère les ressources."""
        self.cancel()
        self._client = None

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
```

**Step 2:** Commit.

```bash
git add jarvis/llm/gemini.py
git commit -m "feat(llm): add GeminiLLM backend with streaming, function calling, and search grounding"
```

---

### Task 4: Refondre la configuration (Persona + Instructions + LLM étendu)

**Files:**
- Modify: `jarvis/config.py` (refonte majeure)

**Step 1:** Réécrire config.py avec les nouveaux concepts. Changements :
- Ajout `Instruction` dataclass
- Ajout `PersonaConfig` dataclass (nom, langue, wake phrase, voix, instructions)
- Extension `LLMConfig` (backend, api_key, enable_search, enable_tools)
- Extension `TTSConfig` (backend, cosyvoice_model, reference_audio/text)
- Ajout `ToolsConfig` dataclass
- `JarvisConfig` utilise `PersonaConfig` au lieu de `name` + champs dispersés
- Garder `to_dict()`, `from_dict()`, `save()`, `load()` rétrocompatibles

```python
"""Jarvis — Configuration centralisée avec système de Personas."""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "jarvis_config.json"
PERSONAS_DIR = Path(__file__).parent.parent / "personas"


@dataclass
class Instruction:
    """Une instruction individuelle activable/désactivable."""
    id: str
    label: str
    content: str
    enabled: bool = True
    builtin: bool = True


DEFAULT_INSTRUCTIONS = [
    Instruction("concise", "Réponses concises (1-3 phrases)",
                "Réponds en 1 à 3 phrases courtes, comme dans une vraie conversation orale."),
    Instruction("no_emoji", "Pas d'emojis ni de markdown",
                "N'utilise JAMAIS d'emojis, d'émoticônes, d'astérisques, de tirets, de listes à puces, de markdown ou de mise en forme."),
    Instruction("no_code", "Pas de code ni de tableaux",
                "N'écris JAMAIS de code, de tableaux ou de blocs formatés."),
    Instruction("spell_numbers", "Nombres en toutes lettres",
                "Écris les nombres en toutes lettres."),
    Instruction("no_abbrev", "Pas d'abréviations",
                "Évite les abréviations, les sigles et les URLs."),
    Instruction("humor", "Humour et personnalité",
                "Parle naturellement, avec de l'humour et de la personnalité, comme un humain décontracté."),
    Instruction("tutoiement", "Tutoiement",
                "Tutoie l'utilisateur.", enabled=False),
    Instruction("vouvoiement", "Vouvoiement",
                "Vouvoie l'utilisateur.", enabled=False),
]


@dataclass
class PersonaConfig:
    """Identité complète de l'assistant — sauvegardable et switchable."""
    name: str = "Jarvis"
    language: str = "fr"
    wake_phrase: str = "hey_jarvis"
    wake_enabled: bool = True
    wake_threshold: float = 0.5

    # Voix
    tts_backend: str = "kokoro"  # "kokoro" | "cosyvoice" (Phase 2)
    voice_id: str = "ff_siwis"
    reference_audio: str = ""
    reference_text: str = ""
    voice_speed: float = 1.0

    # Instructions (liste ordonnée, toggleables)
    instructions: list[Instruction] = field(
        default_factory=lambda: [Instruction(i.id, i.label, i.content, i.enabled, i.builtin)
                                  for i in DEFAULT_INSTRUCTIONS]
    )

    def build_system_prompt(self) -> str:
        """Génère le system prompt à partir des instructions actives."""
        base = (
            f"Tu es {self.name}, un assistant vocal. "
            "Tes réponses seront lues à voix haute par un synthétiseur vocal."
        )
        active = [i.content for i in self.instructions if i.enabled]
        if active:
            base += " Règles strictes : " + " ".join(active)
        return base


@dataclass
class STTConfig:
    model: str = "large-v3-turbo"
    device: str = "cuda"
    compute_type: str = "float16"
    language: str = "fr"
    beam_size: int = 1
    vad_filter: bool = True
    vad_threshold: float = 0.5


@dataclass
class LLMConfig:
    # Backend
    backend: str = "gemini"  # "gemini" | "ollama"

    # Gemini
    model: str = "gemini-2.5-flash"
    api_key: str = ""

    # Ollama
    ollama_model: str = "qwen3:14b"
    base_url: str = "http://localhost:11434"

    # Commun
    temperature: float = 0.7
    max_tokens: int = 300

    # Features (Gemini seulement)
    enable_search: bool = True
    enable_tools: bool = True

    # System prompt — auto-généré par PersonaConfig.build_system_prompt()
    # mais peut être overridé manuellement
    system_prompt_override: str = ""


@dataclass
class TTSConfig:
    # Backend
    backend: str = "kokoro"  # "kokoro" | "cosyvoice"

    # Kokoro
    kokoro_lang: str = "f"
    kokoro_voice: str = "ff_siwis"

    # CosyVoice (Phase 2)
    cosyvoice_model: str = "FunAudioLLM/CosyVoice2-0.5B"

    # Commun
    speed: float = 1.0


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 32
    silence_timeout_ms: int = 700
    min_speech_ms: int = 300
    playback_sample_rate: int = 24000
    input_device: int | None = None
    output_device: int | None = None


@dataclass
class MemoryConfig:
    enabled: bool = True
    db_path: str = "jarvis_memory.db"
    max_context_memories: int = 5
    max_conversation_turns: int = 10


@dataclass
class ToolsConfig:
    """Configuration des outils et de l'API externe."""
    enable_api_server: bool = False
    api_port: int = 8741


@dataclass
class JarvisConfig:
    persona: PersonaConfig = field(default_factory=PersonaConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)

    @property
    def name(self) -> str:
        """Raccourci vers le nom du persona actif."""
        return self.persona.name

    def to_dict(self) -> dict:
        """Sérialise en dictionnaire (gère les Instruction dataclass)."""
        d = {}
        for key, val in asdict(self).items():
            d[key] = val
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "JarvisConfig":
        """Désérialise depuis un dictionnaire."""
        config = cls()

        # Persona (avec gestion spéciale des instructions)
        if "persona" in data and isinstance(data["persona"], dict):
            persona_data = data["persona"]
            for k, v in persona_data.items():
                if k == "instructions" and isinstance(v, list):
                    config.persona.instructions = [
                        Instruction(**instr) if isinstance(instr, dict) else instr
                        for instr in v
                    ]
                elif hasattr(config.persona, k):
                    setattr(config.persona, k, v)

        # Sous-configs simples
        simple_subs = {
            "llm": config.llm,
            "tts": config.tts,
            "stt": config.stt,
            "audio": config.audio,
            "memory": config.memory,
            "tools": config.tools,
        }
        for key, sub_obj in simple_subs.items():
            if key in data and isinstance(data[key], dict):
                for k, v in data[key].items():
                    if hasattr(sub_obj, k):
                        setattr(sub_obj, k, v)

        # Rétrocompatibilité : ancien format avec "name" au top level
        if "name" in data and "persona" not in data:
            config.persona.name = data["name"]

        return config

    def save(self, path: Path | str | None = None):
        """Sauvegarde la config en JSON."""
        p = Path(path) if path else DEFAULT_CONFIG_PATH
        p.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path | str | None = None) -> "JarvisConfig":
        """Charge la config depuis JSON (fallback vers défauts)."""
        p = Path(path) if path else DEFAULT_CONFIG_PATH
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("Config corrompue, utilisation des défauts: %s", e)
            return cls()


def save_persona(persona: PersonaConfig, name: str | None = None):
    """Sauvegarde un persona dans le dossier personas/."""
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
    filename = (name or persona.name).lower().replace(" ", "_") + ".json"
    path = PERSONAS_DIR / filename
    path.write_text(
        json.dumps(asdict(persona), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_persona(name: str) -> PersonaConfig | None:
    """Charge un persona depuis le dossier personas/."""
    filename = name.lower().replace(" ", "_") + ".json"
    path = PERSONAS_DIR / filename
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    persona = PersonaConfig()
    for k, v in data.items():
        if k == "instructions" and isinstance(v, list):
            persona.instructions = [
                Instruction(**i) if isinstance(i, dict) else i for i in v
            ]
        elif hasattr(persona, k):
            setattr(persona, k, v)
    return persona


def list_personas() -> list[str]:
    """Liste les noms de personas disponibles."""
    if not PERSONAS_DIR.exists():
        return []
    return [p.stem for p in PERSONAS_DIR.glob("*.json")]
```

**Step 2:** Supprimer l'ancien `jarvis_config.json` (sera recréé au prochain save).

**Step 3:** Commit.

```bash
git add jarvis/config.py
git commit -m "refactor(config): add Persona system, Instructions, extended LLM/TTS config with backend switching"
```

---

### Task 5: Créer l'abstraction TTS (Protocol) et renommer synthesizer.py

**Files:**
- Create: `jarvis/tts/base.py`
- Rename: `jarvis/tts/synthesizer.py` → `jarvis/tts/kokoro.py`
- Modify: `jarvis/tts/kokoro.py` (adapter au Protocol)

**Step 1:** Créer le Protocol TTS.

```python
"""TTS — Interface abstraite pour les backends TTS."""

from __future__ import annotations

from typing import Protocol, Generator, runtime_checkable

import numpy as np


@runtime_checkable
class TTSBackend(Protocol):
    """Interface commune pour tous les backends TTS."""

    SAMPLE_RATE: int

    def load(self) -> None:
        """Charge le modèle TTS."""
        ...

    def synthesize_stream(self, text: str) -> Generator[np.ndarray, None, None]:
        """Synthétise du texte en streaming, yield des chunks float32."""
        ...

    def unload(self) -> None:
        """Libère les ressources."""
        ...
```

**Step 2:** Renommer `synthesizer.py` → `kokoro.py`. Le code reste identique, juste le nom de fichier change. Classe renommée en `KokoroSynthesizer`.

**Step 3:** Commit.

```bash
git add jarvis/tts/
git commit -m "refactor(tts): add TTSBackend protocol, rename synthesizer.py to kokoro.py"
```

---

### Task 6: Factory pattern dans pipeline.py + utiliser les abstractions

**Files:**
- Modify: `jarvis/pipeline.py`

**Step 1:** Ajouter des factory methods pour créer le bon backend LLM/TTS selon la config. Changements clés :
- `_create_llm()` retourne `GeminiLLM` ou `OllamaLLM` selon `config.llm.backend`
- `_create_tts()` retourne `KokoroSynthesizer` (ou CosyVoice en Phase 2) selon `config.persona.tts_backend`
- `set_context()` utilise `persona.build_system_prompt()` (ou `system_prompt_override`)
- Utiliser le wake_phrase du persona au lieu du WakeWordConfig séparé
- Supprimer l'import direct de `ChatLLM`, `Synthesizer`

```python
"""Pipeline Jarvis — Orchestre STT → LLM → TTS avec barge-in et wake word."""

import logging
import threading
import uuid
from collections.abc import Callable

import numpy as np

from jarvis.config import JarvisConfig

log = logging.getLogger(__name__)


def _create_llm(config: JarvisConfig):
    """Factory : crée le backend LLM selon la config."""
    if config.llm.backend == "gemini":
        from jarvis.llm.gemini import GeminiLLM
        return GeminiLLM(config.llm)
    else:
        from jarvis.llm.ollama import OllamaLLM
        return OllamaLLM(config.llm)


def _create_tts(config: JarvisConfig):
    """Factory : crée le backend TTS selon la config."""
    if config.persona.tts_backend == "cosyvoice":
        from jarvis.tts.cosyvoice import CosyVoiceSynthesizer
        return CosyVoiceSynthesizer(config)
    else:
        from jarvis.tts.kokoro import KokoroSynthesizer
        return KokoroSynthesizer(config.tts)


class JarvisPipeline:
    """Pipeline vocal complet avec gestion des interruptions."""

    def __init__(self, config: JarvisConfig):
        self.config = config

        # Composants — créés via factory
        from jarvis.audio.manager import AudioManager
        from jarvis.stt.transcriber import Transcriber
        from jarvis.memory.store import MemoryStore
        from jarvis.wakeword.detector import WakeWordDetector

        self.audio = AudioManager(config.audio)
        self.stt = Transcriber(config.stt)
        self.tts = _create_tts(config)
        self.llm = _create_llm(config)
        self.memory = MemoryStore(config.memory)
        self.wake_word = WakeWordDetector(config)

        self._running = False
        self._active = False
        self._session_id = ""
        self._vad_model = None
        self._barge_in_detected = threading.Event()

        # Callbacks GUI
        self.on_state_change: Callable[[str], None] | None = None
        self.on_transcript: Callable[[str], None] | None = None
        self.on_response: Callable[[str], None] | None = None
        self.on_audio_level: Callable[[float], None] | None = None

    # ... (_emit_state, _emit_audio_level inchangés)

    def load_all(self):
        """Charge tous les modèles."""
        self._emit_state("loading")
        log.info("=== Chargement des modèles ===")

        # Vérifier le backend LLM
        if not self.llm.check_connection():
            backend = self.config.llm.backend
            if backend == "gemini":
                log.error("API Gemini non accessible. Vérifie ta clé API.")
            else:
                log.error("Ollama non accessible sur %s.", self.config.llm.base_url)
            raise ConnectionError(f"Backend LLM ({backend}) non accessible")
        log.info("LLM connecté (%s: %s)", self.config.llm.backend,
                 self.config.llm.model if self.config.llm.backend == "gemini"
                 else self.config.llm.ollama_model)

        # Charger les modèles
        self.stt.load()
        self.tts.load()
        self._load_vad()

        if self.config.persona.wake_enabled:
            self.wake_word.load()

        if self.config.memory.enabled:
            self.memory.load()

        # Initialiser contexte LLM avec le system prompt du persona
        memories = self.memory.get_recent_memories() if self.config.memory.enabled else []
        system_prompt = (
            self.config.llm.system_prompt_override
            or self.config.persona.build_system_prompt()
        )
        self.llm.set_context(system_prompt, memories)

        self._session_id = uuid.uuid4().hex[:8]
        log.info("=== Tous les modèles chargés. Session: %s ===", self._session_id)

    # _load_vad(), _is_speech() : inchangés

    def run(self):
        """Boucle principale du pipeline."""
        self._running = True
        self.audio.start_capture()
        self._emit_state("idle")

        if not self.config.persona.wake_enabled:
            self._active = True
            log.info("Wake word désactivé — %s écoute en permanence.", self.config.name)
        else:
            log.info("Dis '%s' pour activer...", self.config.persona.wake_phrase)

        try:
            while self._running:
                chunk = self.audio.get_audio_chunk(timeout=0.1)
                if chunk is None:
                    continue

                if not self._active:
                    if self.wake_word.detect(chunk):
                        self._active = True
                        self._play_activation_sound()
                        log.info("%s activé! Je t'écoute...", self.config.name)
                    continue

                speech_audio = self._collect_speech(chunk)
                if speech_audio is None:
                    continue

                self._emit_state("thinking")
                text = self.stt.transcribe(speech_audio, self.config.audio.sample_rate)
                if not text or len(text.strip()) < 2:
                    self._emit_state("idle")
                    continue

                log.info("Toi: %s", text)
                if self.on_transcript:
                    self.on_transcript(text)

                if self.config.memory.enabled:
                    self.memory.process_user_message(text, self._session_id)

                self.llm.add_user_message(text)
                self._respond_streaming()
                self._emit_state("idle")

        except KeyboardInterrupt:
            log.info("Arrêt demandé par l'utilisateur.")
        finally:
            self.stop()

    # _collect_speech() : inchangé

    def _respond_streaming(self):
        """Génère la réponse LLM en streaming et joue le TTS chunk par chunk."""
        self._barge_in_detected.clear()
        full_response = ""

        barge_in_thread = threading.Thread(
            target=self._monitor_barge_in, daemon=True
        )
        barge_in_thread.start()

        try:
            for sentence in self.llm.generate_stream():
                if self._barge_in_detected.is_set():
                    log.info("Barge-in! Réponse interrompue.")
                    self.llm.cancel()  # ← FIX Bug 1 : arrêter le LLM
                    break

                full_response += sentence + " "
                log.info("%s: %s", self.config.name, sentence)
                if self.on_response:
                    self.on_response(sentence)

                self._emit_state("speaking")

                def _tts_chunks():
                    for chunk in self.tts.synthesize_stream(sentence):
                        if self._barge_in_detected.is_set():
                            return
                        self._emit_audio_level(chunk)
                        yield chunk

                if not self._barge_in_detected.is_set():
                    self.audio.play_audio_stream(
                        _tts_chunks(), self.tts.SAMPLE_RATE
                    )

        finally:
            # FIX Bug 2 : sauvegarder la réponse partielle
            if not full_response.strip():
                full_response = self.llm.get_partial_response()

            if full_response.strip() and self.config.memory.enabled:
                self.memory.process_assistant_message(
                    full_response.strip(), self._session_id
                )

            self.audio.drain_capture_queue()

    # _monitor_barge_in(), _play_activation_sound() : inchangés

    def stop(self):
        """Arrête proprement le pipeline."""
        log.info("Arrêt de %s...", self.config.name)
        self._running = False
        self._emit_state("stopped")
        self.audio.cleanup()
        self.memory.cleanup()
        self.llm.cleanup()
        log.info("%s arrêté.", self.config.name)
```

**Notes importantes :**
- Les méthodes `_emit_state`, `_emit_audio_level`, `_load_vad`, `_is_speech`, `_collect_speech`, `_monitor_barge_in`, `_play_activation_sound` restent **identiques** au code actuel.
- Seuls `__init__`, `load_all`, `run`, `_respond_streaming` et `stop` changent.

**Step 2:** Adapter `WakeWordDetector` pour accepter `JarvisConfig` au lieu de `WakeWordConfig` (il lit `config.persona.wake_phrase`, `config.persona.wake_threshold`, `config.persona.wake_enabled`).

**Step 3:** Commit.

```bash
git add jarvis/pipeline.py jarvis/wakeword/detector.py
git commit -m "refactor(pipeline): use LLM/TTS factories, Persona system prompt, fix barge-in bugs 1&2"
```

---

### Task 7: Fix barge-in Bug 3 — Écoute immédiate après interruption

**Files:**
- Modify: `jarvis/pipeline.py` (méthode `_respond_streaming` et `run`)

**Step 1:** Quand le barge-in est détecté, les chunks audio qui l'ont déclenché contiennent la parole de l'utilisateur. Au lieu de les jeter, on les conserve et on les injecte comme début de la prochaine collecte.

Ajouter un attribut `self._barge_in_audio: list[np.ndarray] = []` à `__init__`.

Dans `_monitor_barge_in`, au lieu de juste détecter, accumuler les chunks qui ont déclenché le barge-in :

```python
def _monitor_barge_in(self):
    """Surveille le micro pendant que Jarvis parle. Détecte les interruptions."""
    consecutive_speech = 0
    required_chunks = 3
    speech_chunks = []

    while self.audio.is_playing and not self._barge_in_detected.is_set():
        chunk = self.audio.get_audio_chunk(timeout=0.05)
        if chunk is None:
            consecutive_speech = 0
            speech_chunks.clear()
            continue

        if self._is_speech(chunk):
            consecutive_speech += 1
            speech_chunks.append(chunk)
            if consecutive_speech >= required_chunks:
                self._barge_in_audio = speech_chunks.copy()
                self._barge_in_detected.set()
                self.audio.stop_playback()
                return
        else:
            consecutive_speech = 0
            speech_chunks.clear()
```

Dans `run()`, après `_respond_streaming()`, vérifier s'il y a de l'audio de barge-in à traiter :

```python
# Après _respond_streaming()
if self._barge_in_detected.is_set() and self._barge_in_audio:
    # Traiter les chunks de barge-in comme début de nouvelle parole
    initial = self._barge_in_audio
    self._barge_in_audio = []
    self._barge_in_detected.clear()

    # Collecter la suite de la parole
    combined = np.concatenate(initial)
    speech_audio = self._collect_speech_continue(combined)
    if speech_audio is not None:
        self._emit_state("thinking")
        text = self.stt.transcribe(speech_audio, self.config.audio.sample_rate)
        if text and len(text.strip()) >= 2:
            log.info("Toi (après barge-in): %s", text)
            if self.on_transcript:
                self.on_transcript(text)
            if self.config.memory.enabled:
                self.memory.process_user_message(text, self._session_id)
            self.llm.add_user_message(text)
            self._respond_streaming()

self._emit_state("idle")
```

Ajouter `_collect_speech_continue(initial_audio)` — identique à `_collect_speech` mais démarre avec l'audio déjà capturé :

```python
def _collect_speech_continue(self, initial_audio: np.ndarray) -> np.ndarray | None:
    """Continue la collecte de parole après un barge-in."""
    self._emit_state("listening")
    chunks = [initial_audio]
    silence_ms = 0
    speech_ms = len(initial_audio) / self.config.audio.sample_rate * 1000
    timeout_ms = self.config.audio.silence_timeout_ms
    min_speech = self.config.audio.min_speech_ms

    while self._running:
        chunk = self.audio.get_audio_chunk(timeout=0.15)
        if chunk is None:
            silence_ms += 150
            if silence_ms >= timeout_ms:
                break
            continue

        chunks.append(chunk)
        self._emit_audio_level(chunk)

        if self._is_speech(chunk):
            silence_ms = 0
            speech_ms += self.config.audio.chunk_duration_ms
        else:
            silence_ms += self.config.audio.chunk_duration_ms
            if silence_ms >= timeout_ms:
                break

    if speech_ms < min_speech:
        return None

    return np.concatenate(chunks)
```

**Step 2:** Commit.

```bash
git add jarvis/pipeline.py
git commit -m "fix(pipeline): barge-in bug 3 - immediately listen to user speech after interrupting"
```

---

### Task 8: Refonte GUI — Nouveau SettingsDialog + PersonaTab

**Files:**
- Rewrite: `jarvis/gui/settings_dialog.py`
- Create: `jarvis/gui/widgets/persona_tab.py`
- Create: `jarvis/gui/widgets/intelligence_tab.py`
- Create: `jarvis/gui/widgets/tools_tab.py`
- Modify: `jarvis/gui/widgets/audio_tab.py` (intégrer STT + mémoire)

**Step 1: settings_dialog.py** — 4 onglets au lieu de 7 :

```python
"""Dialogue de paramètres — 4 onglets user-friendly."""

import logging
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QDialogButtonBox,
)

from jarvis.config import JarvisConfig
from jarvis.gui.widgets.persona_tab import PersonaTab
from jarvis.gui.widgets.intelligence_tab import IntelligenceTab
from jarvis.gui.widgets.tools_tab import ToolsTab
from jarvis.gui.widgets.advanced_tab import AdvancedTab

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Fenêtre de paramètres avec 4 onglets intuitifs."""

    save_and_restart = pyqtSignal(JarvisConfig)

    def __init__(self, config: JarvisConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Paramètres de {config.persona.name}")
        self.setMinimumSize(650, 550)
        self._config = config

        layout = QVBoxLayout(self)

        # Onglets
        self._tabs = QTabWidget()
        self._persona_tab = PersonaTab(config)
        self._intelligence_tab = IntelligenceTab(config.llm)
        self._tools_tab = ToolsTab(config.tools)
        self._advanced_tab = AdvancedTab(config)

        self._tabs.addTab(self._persona_tab, "👤 Persona")
        self._tabs.addTab(self._intelligence_tab, "🧠 Intelligence")
        self._tabs.addTab(self._tools_tab, "🔧 Outils")
        self._tabs.addTab(self._advanced_tab, "⚙ Avancé")
        layout.addWidget(self._tabs)

        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        """Applique les changements et émet le signal."""
        self._persona_tab.apply(self._config)
        self._intelligence_tab.apply(self._config.llm)
        self._tools_tab.apply(self._config.tools)
        self._advanced_tab.apply(self._config)
        self.save_and_restart.emit(self._config)
        self.accept()
```

**Step 2: persona_tab.py** — L'onglet le plus riche. Contient identité, voix et instructions.

Le widget `PersonaTab` contient :
- Section Profils : boutons radio pour personas sauvés + bouton "Nouveau"
- Section Identité : nom, langue, phrase d'appel
- Section Voix : sélection backend (Kokoro/CosyVoice), grille de voix avec preview, zone de clonage audio, slider vitesse
- Section Instructions : liste de QCheckBox + label éditable par instruction, bouton "Ajouter", textarea avancé pour le system prompt override

Ce fichier est le plus gros (~300 lignes). Il utilise :
- `QScrollArea` pour le contenu scrollable
- `QGroupBox` pour chaque section
- `QGridLayout` pour la grille de voix
- `QFileDialog` pour sélectionner l'audio de référence (clonage)
- Boutons preview TTS pour chaque voix

**Step 3: intelligence_tab.py** — Onglet cerveau.

Le widget `IntelligenceTab` contient :
- Radio buttons Gemini/Ollama
- Champs Gemini : modèle (dropdown), clé API (QLineEdit avec echoMode Password), statut connexion
- Champs Ollama : modèle (QComboBox avec fetch async), URL
- Section commune : température (slider), tokens max (spinbox)
- Le switch backend masque/affiche dynamiquement les champs pertinents

**Step 4: tools_tab.py** — Onglet outils (placeholder Phase 3).

Affiche les outils disponibles avec toggles. Pour Phase 1 : seulement "Google Search" et "Date et heure". Le serveur API est configurable ici.

**Step 5: advanced_tab.py** — Fusionne les anciens tabs Audio + STT + Mémoire.

Renommer/adapter `audio_tab.py` en `advanced_tab.py` qui contient 3 QGroupBox :
- Audio : devices, timeouts
- Transcription (STT) : modèle, device, langue
- Mémoire : enable, limits, reset

**Step 6:** Supprimer les anciens fichiers widget inutilisés :
- `jarvis/gui/widgets/general_tab.py`
- `jarvis/gui/widgets/llm_tab.py`
- `jarvis/gui/widgets/tts_tab.py`
- `jarvis/gui/widgets/wakeword_tab.py`
- `jarvis/gui/widgets/memory_tab.py`

**Step 7:** Commit.

```bash
git add jarvis/gui/
git commit -m "feat(gui): complete settings redesign - 4 intuitive tabs with Persona system"
```

---

### Task 9: Mettre à jour app.py et worker.py pour la nouvelle config

**Files:**
- Modify: `jarvis/gui/app.py`
- Modify: `jarvis/gui/worker.py`
- Modify: `jarvis/gui/main_window.py`

**Step 1:** `app.py` — Adapter les imports et la création du worker. `config.persona.name` au lieu de `config.name` dans les messages. Le worker reçoit la config complète (inchangé).

**Step 2:** `worker.py` — Aucun changement structurel nécessaire. Le pipeline gère la factory en interne.

**Step 3:** `main_window.py` — Passer `config` (pas des sous-configs) au `SettingsDialog`.

**Step 4:** Commit.

```bash
git add jarvis/gui/app.py jarvis/gui/worker.py jarvis/gui/main_window.py
git commit -m "refactor(gui): adapt app/worker/window to new config structure"
```

---

### Task 10: Mettre à jour main.py (CLI) pour la nouvelle config

**Files:**
- Modify: `main.py`

**Step 1:** Adapter les arguments CLI pour la nouvelle structure de config :
- `--backend gemini|ollama` au lieu de juste `--model`
- `--model` s'applique au backend sélectionné
- `--api-key` pour Gemini
- Le reste reste identique

**Step 2:** Commit.

```bash
git add main.py
git commit -m "refactor(cli): adapt main.py to new config structure with backend selection"
```

---

### Task 11: Mettre à jour requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1:** Ajouter `google-genai` :

```
# LLM
httpx
google-genai>=1.0.0
```

**Step 2:** Installer.

```bash
pip install google-genai
```

**Step 3:** Commit.

```bash
git add requirements.txt
git commit -m "deps: add google-genai SDK for Gemini backend"
```

---

### Task 12: Test intégration Phase 1

**Step 1:** Tester le backend Gemini en CLI :

```bash
python main.py --backend gemini --api-key "LA_CLE" --no-wake-word
```

Vérifier :
- Connexion Gemini réussie
- Streaming fonctionne
- Réponses en français
- Barge-in fonctionne (couper pendant la réponse)
- Après barge-in, la nouvelle parole est captée immédiatement

**Step 2:** Tester le fallback Ollama :

```bash
python main.py --backend ollama --no-wake-word
```

**Step 3:** Tester la GUI :

```bash
python gui_main.py
```

Vérifier :
- Les 4 onglets s'affichent
- Switch Gemini/Ollama fonctionne
- Clé API sauvegardée dans la config
- Instructions toggleables
- Persona sauvegardable/chargeable

**Step 4:** Commit final Phase 1.

```bash
git add -A
git commit -m "milestone: Phase 1 complete - Gemini backend, Persona system, barge-in fixes"
```

---

## Phase 2 : CosyVoice3 TTS

### Task 13: Installer CosyVoice3 et créer le backend TTS

**Files:**
- Create: `jarvis/tts/cosyvoice.py`

**Step 1:** Installer CosyVoice3 dans le venv :

```bash
pip install cosyvoice
# Si pynini nécessaire et conda dispo :
# conda install -y -c conda-forge pynini==2.1.5
```

**Step 2:** Implémenter `CosyVoiceSynthesizer` :

```python
"""TTS — Backend CosyVoice3 (GPU) avec clonage de voix."""

import logging
import numpy as np
from collections.abc import Generator

from jarvis.config import JarvisConfig

log = logging.getLogger(__name__)


class CosyVoiceSynthesizer:
    """Backend TTS local sur GPU avec support clonage de voix."""

    SAMPLE_RATE = 22050  # CosyVoice3 sample rate de sortie

    def __init__(self, config: JarvisConfig):
        self._config = config
        self._model = None
        self._reference_audio = None
        self._reference_text = ""

    def load(self):
        """Charge le modèle CosyVoice3 sur GPU."""
        if self._model is not None:
            return

        from cosyvoice.cli.cosyvoice import CosyVoice2

        model_name = self._config.tts.cosyvoice_model
        log.info("Chargement de CosyVoice3 (%s) sur GPU...", model_name)
        self._model = CosyVoice2(
            model_name,
            load_jit=False,
            load_trt=False,
        )
        log.info("CosyVoice3 chargé.")

        # Charger la voix de référence si configurée
        ref_path = self._config.persona.reference_audio
        ref_text = self._config.persona.reference_text
        if ref_path and ref_text:
            self._load_reference(ref_path, ref_text)

    def _load_reference(self, audio_path: str, text: str):
        """Charge l'audio de référence pour le clonage de voix."""
        import torchaudio

        log.info("Chargement de la voix de référence : %s", audio_path)
        waveform, sr = torchaudio.load(audio_path)
        if sr != 16000:
            waveform = torchaudio.functional.resample(waveform, sr, 16000)
        self._reference_audio = waveform
        self._reference_text = text
        log.info("Voix de référence chargée (%.1fs)", waveform.shape[1] / 16000)

    def synthesize_stream(self, text: str) -> Generator[np.ndarray, None, None]:
        """Synthétise du texte en streaming, yield des chunks float32."""
        self.load()

        if self._reference_audio is not None and self._reference_text:
            # Mode clonage (zero-shot)
            gen = self._model.inference_zero_shot(
                text,
                self._reference_text,
                self._reference_audio,
                stream=True,
            )
        else:
            # Mode SFT (voix prédéfinie)
            gen = self._model.inference_sft(
                text,
                speaker_id=self._config.persona.voice_id or "default",
                stream=True,
            )

        for result in gen:
            audio = result.get("tts_speech")
            if audio is None:
                continue
            # Convertir tensor → numpy float32
            if hasattr(audio, "numpy"):
                chunk = audio.squeeze().cpu().numpy().astype(np.float32)
            else:
                chunk = np.asarray(audio, dtype=np.float32)
            yield chunk

    def set_reference_voice(self, audio_path: str, text: str):
        """Change la voix de référence pour le clonage."""
        self._load_reference(audio_path, text)

    def unload(self):
        """Libère le modèle GPU."""
        self._model = None
        self._reference_audio = None
        log.info("CosyVoice3 déchargé.")
```

**Step 3:** Commit.

```bash
git add jarvis/tts/cosyvoice.py
git commit -m "feat(tts): add CosyVoice3 backend with GPU inference and voice cloning"
```

---

### Task 14: Enrichir PersonaTab avec la sélection de voix CosyVoice

**Files:**
- Modify: `jarvis/gui/widgets/persona_tab.py`

**Step 1:** Ajouter dans la section Voix :
- Radio button "CosyVoice (GPU)" / "Kokoro (CPU)"
- Si CosyVoice sélectionné : afficher zone de clonage (file picker + texte de référence)
- Si Kokoro sélectionné : afficher la grille de voix prédéfinies
- Bouton preview qui utilise le bon backend

**Step 2:** Commit.

```bash
git add jarvis/gui/widgets/persona_tab.py
git commit -m "feat(gui): add CosyVoice3 voice selection and cloning UI to PersonaTab"
```

---

### Task 15: Test intégration Phase 2

**Step 1:** Tester CosyVoice3 en CLI :

```bash
python main.py --backend gemini --tts-backend cosyvoice --no-wake-word
```

**Step 2:** Tester le clonage de voix via la GUI : choisir un fichier audio de référence, entrer le texte correspondant, preview.

**Step 3:** Vérifier que le fallback Kokoro fonctionne toujours.

**Step 4:** Commit final Phase 2.

```bash
git add -A
git commit -m "milestone: Phase 2 complete - CosyVoice3 GPU TTS with voice cloning"
```

---

## Phase 3 : Tools & Agent Architecture

### Task 16: Créer le système de Tools (Protocol + Registry)

**Files:**
- Create: `jarvis/tools/__init__.py`
- Create: `jarvis/tools/base.py`
- Create: `jarvis/tools/registry.py`

**Step 1:** Protocol Tool + ToolRegistry :

```python
# jarvis/tools/base.py
"""Outils — Interface abstraite pour les tools Jarvis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class Tool(Protocol):
    """Interface commune pour tous les outils."""

    @property
    def name(self) -> str:
        """Nom unique de l'outil (snake_case)."""
        ...

    @property
    def description(self) -> str:
        """Description pour le LLM (quand utiliser cet outil)."""
        ...

    @property
    def parameters(self) -> dict:
        """JSON Schema des paramètres attendus."""
        ...

    def execute(self, **kwargs) -> str:
        """Exécute l'outil et retourne le résultat en texte."""
        ...
```

```python
# jarvis/tools/registry.py
"""Registre centralisé des outils disponibles."""

import logging
from jarvis.tools.base import Tool

log = logging.getLogger(__name__)


class ToolRegistry:
    """Découvre, enregistre et dispatch les appels d'outils."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Enregistre un outil."""
        self._tools[tool.name] = tool
        log.info("Outil enregistré : %s", tool.name)

    def unregister(self, name: str):
        """Retire un outil."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        """Récupère un outil par nom."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Liste tous les outils enregistrés."""
        return list(self._tools.values())

    def execute(self, name: str, args: dict) -> str:
        """Exécute un outil par nom avec les arguments fournis."""
        tool = self._tools.get(name)
        if not tool:
            return f"Outil '{name}' non trouvé."
        try:
            return tool.execute(**args)
        except Exception as e:
            log.error("Erreur outil %s: %s", name, e)
            return f"Erreur lors de l'exécution de {name}: {e}"

    def to_gemini_declarations(self) -> list:
        """Convertit les outils en FunctionDeclaration pour le SDK Gemini."""
        from google.genai import types

        return [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in self._tools.values()
        ]
```

**Step 2:** Commit.

```bash
git add jarvis/tools/
git commit -m "feat(tools): add Tool protocol and ToolRegistry for extensible agent architecture"
```

---

### Task 17: Créer les premiers outils intégrés

**Files:**
- Create: `jarvis/tools/datetime_tool.py`
- Create: `jarvis/tools/system_tool.py`

**Step 1:** Outils de base :

```python
# jarvis/tools/datetime_tool.py
"""Outil — Date et heure actuelles."""

from datetime import datetime
import locale


class DateTimeTool:
    """Fournit la date et l'heure actuelles."""

    @property
    def name(self) -> str:
        return "get_current_datetime"

    @property
    def description(self) -> str:
        return (
            "Retourne la date et l'heure actuelles. "
            "Utilise cet outil quand l'utilisateur demande l'heure, "
            "la date, le jour de la semaine, ou toute information temporelle."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Fuseau horaire (ex: 'Europe/Paris'). Par défaut: local.",
                }
            },
            "required": [],
        }

    def execute(self, timezone: str = "") -> str:
        now = datetime.now()
        return (
            f"Date: {now.strftime('%A %d %B %Y')}. "
            f"Heure: {now.strftime('%H:%M')}."
        )
```

**Step 2:** Commit.

```bash
git add jarvis/tools/datetime_tool.py jarvis/tools/system_tool.py
git commit -m "feat(tools): add datetime and system info built-in tools"
```

---

### Task 18: Intégrer le ToolRegistry dans le pipeline

**Files:**
- Modify: `jarvis/pipeline.py`
- Modify: `jarvis/llm/gemini.py`

**Step 1:** Dans `pipeline.py`, dans `load_all()` :
- Créer un `ToolRegistry`
- Enregistrer les outils activés selon `config.tools`
- Passer les declarations au `GeminiLLM` via `set_tools()`
- Passer `registry.execute` comme executor

```python
# Dans load_all(), après le chargement des modèles :
if self.config.llm.enable_tools and self.config.llm.backend == "gemini":
    from jarvis.tools.registry import ToolRegistry
    from jarvis.tools.datetime_tool import DateTimeTool

    self._tool_registry = ToolRegistry()
    self._tool_registry.register(DateTimeTool())

    self.llm.set_tools(
        declarations=self._tool_registry.to_gemini_declarations(),
        executor=lambda name, args: self._tool_registry.execute(name, args),
    )
```

**Step 2:** Dans `gemini.py`, améliorer `_handle_function_calls` pour renvoyer le résultat au modèle et obtenir une réponse naturelle (au lieu de yield direct du résultat brut).

**Step 3:** Commit.

```bash
git add jarvis/pipeline.py jarvis/llm/gemini.py
git commit -m "feat(tools): integrate ToolRegistry with GeminiLLM function calling"
```

---

### Task 19: Enrichir ToolsTab dans la GUI

**Files:**
- Modify: `jarvis/gui/widgets/tools_tab.py`

**Step 1:** Ajouter des cartes toggleables pour chaque outil, avec description et bouton config pour les outils qui ont des settings. Ajouter la section API server avec port et statut.

**Step 2:** Commit.

```bash
git add jarvis/gui/widgets/tools_tab.py
git commit -m "feat(gui): enrich ToolsTab with tool cards and API server config"
```

---

### Task 20: Créer le serveur API HTTP (trigger externe)

**Files:**
- Create: `jarvis/api/__init__.py`
- Create: `jarvis/api/server.py`

**Step 1:** Serveur léger aiohttp qui écoute les commandes :

```python
# jarvis/api/server.py
"""API HTTP — Point d'entrée pour triggers externes (montre, webhook, etc.)."""

import asyncio
import logging
import threading

from aiohttp import web

log = logging.getLogger(__name__)


class JarvisAPIServer:
    """Serveur API REST pour contrôler Jarvis à distance."""

    def __init__(self, pipeline, port: int = 8741):
        self._pipeline = pipeline
        self._port = port
        self._runner = None
        self._thread = None

    def start(self):
        """Démarre le serveur dans un thread séparé."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("API Jarvis démarrée sur http://0.0.0.0:%d", self._port)

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._start_server())
        loop.run_forever()

    async def _start_server(self):
        app = web.Application()
        app.router.add_post("/api/command", self._handle_command)
        app.router.add_post("/api/wake", self._handle_wake)
        app.router.add_get("/api/status", self._handle_status)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()

    async def _handle_command(self, request):
        """POST /api/command {"text": "quelle heure est-il"}"""
        data = await request.json()
        text = data.get("text", "")
        if not text:
            return web.json_response({"error": "missing text"}, status=400)
        # Injecter le texte dans le pipeline comme si c'était du STT
        self._pipeline.llm.add_user_message(text)
        response = " ".join(self._pipeline.llm.generate_stream())
        return web.json_response({"response": response})

    async def _handle_wake(self, request):
        """POST /api/wake — Active Jarvis."""
        self._pipeline._active = True
        return web.json_response({"status": "active"})

    async def _handle_status(self, request):
        """GET /api/status — État actuel du pipeline."""
        return web.json_response({
            "running": self._pipeline._running,
            "active": self._pipeline._active,
            "session": self._pipeline._session_id,
        })

    def stop(self):
        """Arrête le serveur."""
        if self._runner:
            asyncio.run(self._runner.cleanup())
```

**Step 2:** Intégrer dans `pipeline.py` : si `config.tools.enable_api_server`, démarrer le serveur dans `load_all()` et l'arrêter dans `stop()`.

**Step 3:** Ajouter `aiohttp` à requirements.txt.

**Step 4:** Commit.

```bash
git add jarvis/api/ requirements.txt
git commit -m "feat(api): add HTTP API server for external triggers (watch, webhooks)"
```

---

### Task 21: Test intégration Phase 3 complète

**Step 1:** Tester le function calling :
- "Quelle heure est-il ?" → doit utiliser l'outil DateTimeTool
- "Cherche les dernières nouvelles sur l'IA" → doit utiliser Google Search grounding

**Step 2:** Tester l'API HTTP :

```bash
curl -X POST http://localhost:8741/api/command -H "Content-Type: application/json" -d '{"text":"bonjour"}'
curl http://localhost:8741/api/status
```

**Step 3:** Tester le switch de persona via la GUI.

**Step 4:** Commit final.

```bash
git add -A
git commit -m "milestone: Phase 3 complete - Tools, function calling, API server, full agent architecture"
```

---

## Résumé des fichiers

### Créés (15 fichiers)
| Fichier | Phase | Rôle |
|---------|-------|------|
| `jarvis/llm/base.py` | 1 | Protocol LLMBackend |
| `jarvis/llm/gemini.py` | 1 | Backend Gemini SDK |
| `jarvis/tts/base.py` | 1 | Protocol TTSBackend |
| `jarvis/tts/cosyvoice.py` | 2 | Backend CosyVoice3 GPU |
| `jarvis/tools/__init__.py` | 3 | Package tools |
| `jarvis/tools/base.py` | 3 | Protocol Tool |
| `jarvis/tools/registry.py` | 3 | ToolRegistry |
| `jarvis/tools/datetime_tool.py` | 3 | Outil date/heure |
| `jarvis/tools/system_tool.py` | 3 | Outil info système |
| `jarvis/api/__init__.py` | 3 | Package API |
| `jarvis/api/server.py` | 3 | Serveur HTTP |
| `jarvis/gui/widgets/persona_tab.py` | 1 | Onglet Persona |
| `jarvis/gui/widgets/intelligence_tab.py` | 1 | Onglet Intelligence |
| `jarvis/gui/widgets/tools_tab.py` | 1 | Onglet Outils |
| `jarvis/gui/widgets/advanced_tab.py` | 1 | Onglet Avancé |

### Modifiés (8 fichiers)
| Fichier | Phase | Changement |
|---------|-------|-----------|
| `jarvis/config.py` | 1 | Refonte totale (Persona, Instructions) |
| `jarvis/pipeline.py` | 1+3 | Factory LLM/TTS, bug fixes, tools |
| `jarvis/gui/settings_dialog.py` | 1 | 4 onglets au lieu de 7 |
| `jarvis/gui/app.py` | 1 | Nouvelle config structure |
| `jarvis/gui/worker.py` | 1 | Adaptations mineures |
| `jarvis/gui/main_window.py` | 1 | Adaptations mineures |
| `main.py` | 1 | Args CLI mis à jour |
| `requirements.txt` | 1+3 | google-genai, aiohttp |

### Renommés (2 fichiers)
| Ancien | Nouveau | Phase |
|--------|---------|-------|
| `jarvis/llm/chat.py` | `jarvis/llm/ollama.py` | 1 |
| `jarvis/tts/synthesizer.py` | `jarvis/tts/kokoro.py` | 1 |

### Supprimés (5 fichiers)
| Fichier | Raison |
|---------|--------|
| `jarvis/gui/widgets/general_tab.py` | Remplacé par PersonaTab |
| `jarvis/gui/widgets/llm_tab.py` | Remplacé par IntelligenceTab |
| `jarvis/gui/widgets/tts_tab.py` | Intégré dans PersonaTab |
| `jarvis/gui/widgets/wakeword_tab.py` | Intégré dans PersonaTab |
| `jarvis/gui/widgets/memory_tab.py` | Intégré dans AdvancedTab |

---

## Dépendances à installer

```bash
# Phase 1
pip install google-genai>=1.0.0

# Phase 2
pip install cosyvoice
# Si nécessaire (conda) : conda install -y -c conda-forge pynini==2.1.5

# Phase 3
pip install aiohttp>=3.9
```

---

## Ordre d'exécution

```
Phase 1 (Tasks 1-12) :  ~3-4h de dev
├── Tasks 1-3 :  Abstractions LLM + backends        (~1h)
├── Tasks 4-5 :  Config refonte + TTS abstraction    (~30min)
├── Task 6 :     Pipeline factory + bug fixes 1&2    (~30min)
├── Task 7 :     Bug fix 3 (barge-in écoute)         (~20min)
├── Tasks 8-10 : GUI refonte complète                (~1h30)
├── Task 11 :    requirements.txt                    (~5min)
└── Task 12 :    Test intégration                    (~30min)

Phase 2 (Tasks 13-15) :  ~1-2h de dev
├── Task 13 :    CosyVoice3 backend                  (~1h)
├── Task 14 :    GUI voix enrichie                   (~30min)
└── Task 15 :    Test intégration                    (~30min)

Phase 3 (Tasks 16-21) :  ~2h de dev
├── Tasks 16-17 : Tools system + outils de base      (~30min)
├── Task 18 :     Intégration pipeline               (~30min)
├── Task 19 :     GUI outils                         (~20min)
├── Task 20 :     Serveur API HTTP                   (~30min)
└── Task 21 :     Test intégration                   (~30min)
```
