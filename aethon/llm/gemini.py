"""LLM — Backend Gemini (cloud) via SDK google-genai."""

import logging
import threading
from collections.abc import Generator

from aethon.config import LLMConfig

log = logging.getLogger(__name__)


class GeminiLLM:
    """Backend LLM cloud via Google Gemini API."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._messages: list = []
        self._system_prompt = ""
        self._cancel_event = threading.Event()
        self._current_response = ""
        self._tool_declarations: list = []
        self._tool_executor = None
        self._cached_config = None
        self._init_client()

    def _init_client(self):
        """Initialise le client Gemini."""
        from google import genai

        api_key = getattr(self.config, "api_key", "")
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
        self._cached_config = None  # Invalider le cache (system prompt change)

    def set_tools(self, declarations: list, executor=None):
        """Configure les tools (function calling).

        Args:
            declarations: Liste de types.FunctionDeclaration.
            executor: Callable(name, args) -> str pour exécuter les tools.
        """
        self._tool_declarations = declarations
        self._tool_executor = executor
        self._cached_config = None  # Invalider le cache (tools changent)

    def add_user_message(self, text: str) -> None:
        """Ajoute un message utilisateur."""
        self._messages.append({"role": "user", "parts": [{"text": text}]})

    def _build_config(self):
        """Construit la config de generation avec tools, thinking et safety.

        Google Search et function calling sont mutuellement exclusifs dans
        l'API Gemini generateContent. Quand les deux sont actives, on
        priorise Google Search (plus utile pour un assistant vocal).
        """
        if self._cached_config is not None:
            return self._cached_config

        from google.genai import types

        # Google Search et function calling : mutuellement exclusifs
        tools = []
        if getattr(self.config, "enable_search", True):
            tools.append(types.Tool(google_search=types.GoogleSearch()))
        elif self._tool_declarations:
            tools.append(types.Tool(function_declarations=self._tool_declarations))

        # Safety settings permissifs (evite les refus intempestifs)
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_ONLY_HIGH"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_ONLY_HIGH"),
        ]

        # Thinking config : desactive par defaut (reduit TTFT de 1-3s)
        thinking_budget = getattr(self.config, "thinking_budget", 0)
        thinking_config = None
        try:
            thinking_config = types.ThinkingConfig(thinking_budget=thinking_budget)
        except Exception:
            log.debug("ThinkingConfig non supporte par cette version du SDK")

        config_kwargs = dict(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_tokens,
            system_instruction=self._system_prompt,
            tools=tools if tools else None,
            safety_settings=safety_settings,
        )
        if thinking_config is not None:
            config_kwargs["thinking_config"] = thinking_config

        self._cached_config = types.GenerateContentConfig(**config_kwargs)
        return self._cached_config

    # ── Extraction de texte depuis un chunk streaming ──

    @staticmethod
    def _extract_text(chunk) -> str:
        """Extrait le texte d'un chunk de réponse streaming.

        Priorité : chunk.text (rapide) puis traversée des candidates/parts.
        """
        # Accès rapide — couvre 99% des cas
        try:
            if chunk.text:
                return chunk.text
        except (AttributeError, ValueError):
            pass

        # Fallback : parcourir la structure complète
        text = ""
        if chunk.candidates:
            for candidate in chunk.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            text += part.text
        return text

    # ── Découpage par phrases pour le TTS ──
    #
    # Strategie a deux niveaux pour minimiser la latence :
    # 1. Split aux fins de phrases (.!?…\n) — prioritaire
    # 2. Split aux virgules si le buffer depasse un seuil (~60 chars)
    #    → lance le TTS plus tot au lieu d'attendre le prochain point
    #
    # Le seuil de 60 chars correspond a ~2-3 secondes d'audio parle,
    # ce qui est un bon compromis entre naturalite et latence.

    _COMMA_SPLIT_THRESHOLD = 60  # Caracteres min avant split a la virgule

    @staticmethod
    def _split_at_last_sentence(buffer: str) -> tuple[str, str]:
        """Découpe le buffer au dernier séparateur de phrase.

        Retourne (phrase_complete, reste). Si pas de séparateur trouvé,
        retourne ('', buffer) — rien à yield.
        """
        last_idx = -1
        for ending in (".", "!", "?", "…", "\n"):
            idx = buffer.rfind(ending)
            if idx > last_idx:
                last_idx = idx
        if last_idx < 0:
            return "", buffer
        split = last_idx + 1
        return buffer[:split].strip(), buffer[split:]

    @classmethod
    def _split_early(cls, buffer: str) -> tuple[str, str]:
        """Split agressif : virgule/point-virgule si buffer long.

        Permet de lancer le TTS ~200-300ms plus tot sur les longues phrases.
        Retourne ('', buffer) si pas de split possible.
        """
        if len(buffer) < cls._COMMA_SPLIT_THRESHOLD:
            return "", buffer
        # Chercher la derniere virgule ou point-virgule
        last_comma = -1
        for sep in (",", ";"):
            idx = buffer.rfind(sep)
            if idx > last_comma:
                last_comma = idx
        # Ne pas split trop pres du debut (min 20 chars pour un segment TTS utile)
        if last_comma < 20:
            return "", buffer
        split = last_comma + 1
        return buffer[:split].strip(), buffer[split:]

    def _split_and_yield(self, buffer: str) -> tuple[str | None, str]:
        """Split buffer, yield la phrase ou le segment le plus long possible.

        Priorite : fin de phrase (.!?) > virgule (si buffer long) > attendre.
        """
        # Priorite 1 : split aux fins de phrases
        sentence, remaining = self._split_at_last_sentence(buffer)
        if sentence:
            self._current_response += sentence + " "
            return sentence, remaining
        # Priorite 2 : split aux virgules si buffer long (reduit latence TTS)
        segment, remaining = self._split_early(buffer)
        if segment:
            self._current_response += segment + " "
            return segment, remaining
        return None, buffer

    # ── Génération streaming ──

    def generate_stream(self) -> Generator[str, None, None]:
        """Génère une réponse en streaming, yield par phrase complète.

        Gère automatiquement le function calling : si le modèle demande
        d'exécuter un outil, on l'exécute, on renvoie le résultat au modèle,
        et on stream la réponse finale en langage naturel.
        """
        self._cancel_event.clear()
        self._current_response = ""

        if not self._client:
            yield "Erreur : client Gemini non initialisé. Vérifie ta clé API."
            return

        config = self._build_config()
        pending_calls = []
        buffer = ""
        full_text = ""

        try:
            for chunk in self._client.models.generate_content_stream(
                model=self.config.model,
                contents=self._messages,
                config=config,
            ):
                if self._cancel_event.is_set():
                    break

                # Collecter les function calls
                if chunk.function_calls:
                    pending_calls.extend(chunk.function_calls)
                    continue

                text = self._extract_text(chunk)
                if not text:
                    continue

                full_text += text
                buffer += text

                sentence, buffer = self._split_and_yield(buffer)
                if sentence:
                    yield sentence

        except Exception as e:
            yield from self._handle_error(e, "streaming")
            return

        # Function calls à traiter
        if pending_calls and not self._cancel_event.is_set():
            # Sauvegarder le texte preliminaire s'il existe
            if full_text.strip():
                self._messages.append(
                    {"role": "model", "parts": [{"text": full_text.strip()}]}
                )
            yield from self._execute_and_continue(pending_calls)
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

    # ── Function calling ──

    def _execute_and_continue(
        self, function_calls, depth: int = 0
    ) -> Generator[str, None, None]:
        """Exécute les function calls et relance la génération.

        Flux :
        1. Le modèle retourne des FunctionCall
        2. On exécute les fonctions
        3. On ajoute la réponse du modèle (avec les function calls) à l'historique
        4. On ajoute les résultats (FunctionResponse) à l'historique
        5. On relance la génération pour obtenir une réponse en langage naturel
        """
        max_depth = 5
        if depth >= max_depth:
            log.warning("Profondeur maximale de function calling atteinte (%d)", max_depth)
            yield "Désolé, trop d'appels d'outils enchaînés."
            return

        from google.genai import types

        if not self._tool_executor:
            log.warning("Function calls reçus mais pas d'executor configuré.")
            return

        model_parts = []
        function_responses = []

        for fc in function_calls:
            name = fc.name
            args = dict(fc.args) if fc.args else {}
            log.info("Function call: %s(%s)", name, args)

            model_parts.append(types.Part.from_function_call(
                name=name, args=args,
            ))

            try:
                result = self._tool_executor(name, args)
                log.info("Function result: %s", result[:200] if result else "")
            except Exception as e:
                log.error("Erreur exécution tool %s: %s", name, e)
                result = f"Erreur: {e}"

            function_responses.append(types.Part.from_function_response(
                name=name,
                response={"result": result},
            ))

        # Historique : réponse modèle (function calls) + résultats
        self._messages.append({"role": "model", "parts": model_parts})
        self._messages.append({"role": "user", "parts": function_responses})

        # Relancer la génération
        config = self._build_config()
        buffer = ""
        full_text = ""

        try:
            for chunk in self._client.models.generate_content_stream(
                model=self.config.model,
                contents=self._messages,
                config=config,
            ):
                if self._cancel_event.is_set():
                    break

                # Chaînage de function calls (récursif)
                if chunk.function_calls:
                    remaining = buffer.strip()
                    if remaining:
                        self._current_response += remaining + " "
                        yield remaining
                    yield from self._execute_and_continue(chunk.function_calls, depth + 1)
                    return

                text = self._extract_text(chunk)
                if not text:
                    continue

                full_text += text
                buffer += text

                sentence, buffer = self._split_and_yield(buffer)
                if sentence:
                    yield sentence

        except Exception as e:
            yield from self._handle_error(e, "post-tool")
            return

        # Flush le reste
        remaining = buffer.strip()
        if remaining:
            self._current_response += remaining + " "
            yield remaining

        if full_text.strip():
            self._messages.append(
                {"role": "model", "parts": [{"text": full_text.strip()}]}
            )
        self._trim_history()

    # ── Gestion d'erreurs ──

    def _handle_error(self, error: Exception, context: str) -> Generator[str, None, None]:
        """Gère les erreurs API Gemini avec messages adaptés."""
        from google.genai import errors

        if isinstance(error, errors.ClientError):
            if error.code == 429:
                log.warning("Rate limit Gemini atteint: %s", error.message)
                yield "Désolé, trop de requêtes. Réessaie dans quelques secondes."
            elif error.code == 400:
                log.error("Requête invalide Gemini (%s): %s", context, error.message)
                yield "Désolé, erreur de requête vers Gemini."
            elif error.code == 403:
                log.error("Accès refusé Gemini: %s", error.message)
                yield "Erreur d'authentification Gemini. Vérifie ta clé API."
            else:
                log.error("Erreur client Gemini %d (%s): %s", error.code, context, error.message)
                yield "Désolé, erreur de communication avec Gemini."
        elif isinstance(error, errors.ServerError):
            log.error("Erreur serveur Gemini %d (%s): %s", error.code, context, error.message)
            yield "Gemini est temporairement indisponible. Réessaie."
        else:
            log.error("Erreur Gemini (%s): %s", context, error, exc_info=True)
            yield "Désolé, erreur de communication avec Gemini."

    # ── Contrôle ──

    def cancel(self) -> None:
        """Annule la génération en cours."""
        self._cancel_event.set()

    def pop_last_user_message(self):
        """Retire le dernier message utilisateur (nettoyage barge-in)."""
        if self._messages and self._messages[-1].get("role") == "user":
            self._messages.pop()

    def get_partial_response(self) -> str:
        """Retourne la réponse partielle."""
        return self._current_response.strip()

    def check_connection(self) -> bool:
        """Vérifie que l'API Gemini est accessible."""
        if not self._client:
            return False
        try:
            result = self._client.models.get(model=self.config.model)
            return result is not None
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
