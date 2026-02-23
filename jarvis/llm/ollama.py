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
                        "model": self.config.ollama_model,
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
                    before = token.split("<think>", 1)[0]
                    if before:
                        buffer += before
                    in_think_block = True
                    # Verifier si </think> est aussi dans le meme token
                    if "</think>" in token:
                        in_think_block = False
                        after = token.split("</think>", 1)[-1]
                        if after:
                            buffer += after
                    continue
                if in_think_block:
                    if "</think>" in token:
                        in_think_block = False
                        after = token.split("</think>", 1)[-1]
                        if after:
                            buffer += after
                    continue

                buffer += token

                # Yield dès qu'on a une phrase complète (rfind-max)
                # Priorite 1 : fin de phrase (.!?…\n)
                last_idx = -1
                for ending in sentence_endings:
                    idx = buffer.rfind(ending)
                    if idx > last_idx:
                        last_idx = idx
                if last_idx >= 0:
                    split_at = last_idx + 1
                    sentence = buffer[:split_at].strip()
                    buffer = buffer[split_at:]
                    if sentence:
                        self._current_response += sentence + " "
                        yield sentence
                # Priorite 2 : virgule si buffer long (reduit latence TTS)
                elif len(buffer) >= 60:
                    last_comma = max(buffer.rfind(","), buffer.rfind(";"))
                    if last_comma >= 20:
                        segment = buffer[:last_comma + 1].strip()
                        buffer = buffer[last_comma + 1:]
                        if segment:
                            self._current_response += segment + " "
                            yield segment
        finally:
            if self._response:
                self._response.close()
                self._response = None

        # Flush le reste du buffer (seulement si pas de barge-in)
        if not self._cancel_event.is_set():
            remaining = buffer.strip()
            if remaining:
                remaining = re.sub(r"<think>.*?</think>", "", remaining, flags=re.DOTALL).strip()
                if remaining:
                    self._current_response += remaining + " "
                    yield remaining

        # Sauvegarder la réponse complète dans l'historique (seulement si pas de barge-in)
        clean_response = re.sub(
            r"<think>.*?</think>", "", full_response, flags=re.DOTALL
        ).strip()
        if clean_response and not self._cancel_event.is_set():
            self.conversation.append(
                {"role": "assistant", "content": clean_response}
            )
        self._trim_history()

    def cancel(self) -> None:
        """Annule la génération en cours.

        Ne ferme pas la réponse ici — le bloc finally de generate_stream()
        s'en charge. Évite une race condition entre les deux threads.
        """
        self._cancel_event.set()

    def pop_last_user_message(self):
        """Retire le dernier message utilisateur de l'historique (nettoyage barge-in)."""
        if self.conversation and self.conversation[-1].get("role") == "user":
            self.conversation.pop()

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

