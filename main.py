"""Aethon — Point d'entrée principal (CLI)."""

import argparse
import logging
import os
import sys

# Assurer l'encodage UTF-8 sur Windows (émojis dans les réponses LLM)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ajouter espeak-ng au PATH si installé (requis par Kokoro TTS)
_espeak_dir = r"C:\Program Files\eSpeak NG"
if os.path.isdir(_espeak_dir) and _espeak_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + _espeak_dir

# Supprimer les warnings HuggingFace symlinks
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from aethon.config import AethonConfig
from aethon.pipeline import AethonPipeline


def setup_logging(verbose: bool = False):
    """Configure le logging global."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Réduire le bruit des libs tierces
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Aethon — Assistant vocal hybride")
    parser.add_argument(
        "--no-wake-word",
        action="store_true",
        help="Désactive le wake word (écoute en permanence)",
    )
    parser.add_argument(
        "--wake-mode",
        type=str,
        default=None,
        choices=["openwakeword", "whisper"],
        help="Mode de détection du wake word (default: openwakeword)",
    )
    parser.add_argument(
        "--wake-phrase",
        type=str,
        default=None,
        help="Phrase de réveil personnalisée (mode whisper: n'importe quelle phrase)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="ollama",
        choices=["gemini", "ollama"],
        help="Backend LLM (default: ollama)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Modèle LLM (ollama: qwen3:14b, gemini: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Clé API Gemini (ou variable GEMINI_API_KEY)",
    )
    parser.add_argument(
        "--tts-backend",
        type=str,
        default=None,
        choices=["kokoro", "cosyvoice"],
        help="Backend TTS (default: kokoro)",
    )
    parser.add_argument(
        "--reference-audio",
        type=str,
        default=None,
        help="Audio de référence pour CosyVoice (clonage de voix)",
    )
    parser.add_argument(
        "--reference-text",
        type=str,
        default=None,
        help="Transcription de l'audio de référence CosyVoice",
    )
    parser.add_argument(
        "--stt-model",
        type=str,
        default="large-v3-turbo",
        help="Modèle faster-whisper (default: large-v3-turbo)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="fr",
        choices=["fr", "en"],
        help="Langue de reconnaissance vocale (default: fr)",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Désactive la mémoire longue",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mode verbose (debug)",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    log = logging.getLogger("aethon")

    # Configuration — charger depuis fichier (fallback vers défauts)
    config = AethonConfig.load()

    # Surcharges CLI
    config.llm.backend = args.backend
    if args.model:
        if args.backend == "gemini":
            config.llm.model = args.model
        else:
            config.llm.ollama_model = args.model
    if args.api_key:
        config.llm.api_key = args.api_key

    config.stt.model = args.stt_model
    config.stt.language = args.language
    config.persona.language = args.language
    config.persona.wake_enabled = not args.no_wake_word
    if args.wake_mode:
        config.persona.wake_mode = args.wake_mode
    if args.wake_phrase:
        config.persona.wake_phrase = args.wake_phrase
    config.memory.enabled = not args.no_memory

    # TTS backend override
    if args.tts_backend:
        config.tts.backend = args.tts_backend
        config.persona.tts_backend = args.tts_backend
    if args.reference_audio:
        config.persona.reference_audio = args.reference_audio
    if args.reference_text:
        config.persona.reference_text = args.reference_text

    # Adapter la voix TTS à la langue (Kokoro uniquement)
    if args.language == "en" and config.tts.backend == "kokoro" and config.tts.kokoro_voice == "ff_siwis":
        config.tts.kokoro_lang = "a"
        config.tts.kokoro_voice = "af_heart"
        config.persona.voice_id = "af_heart"

    # Affichage bannière
    if args.backend == "gemini":
        llm_display = f"Gemini {config.llm.model}"
    else:
        llm_display = f"Ollama {config.llm.ollama_model}"

    if config.tts.backend == "cosyvoice":
        tts_display = f"CosyVoice2 (GPU)"
    else:
        tts_display = f"Kokoro ({config.tts.kokoro_voice})"

    log.info("╔══════════════════════════════════════╗")
    log.info("║        AETHON — Assistant Vocal       ║")
    log.info("╠══════════════════════════════════════╣")
    log.info("║  LLM : %-30s ║", llm_display)
    log.info("║  STT : %-30s ║", config.stt.model)
    log.info("║  TTS : %-30s ║", tts_display)
    if config.persona.wake_enabled:
        wake_display = f"{config.persona.wake_phrase} ({config.persona.wake_mode})"
    else:
        wake_display = "Désactivé"
    log.info("║  Wake: %-30s ║", wake_display)
    log.info("║  Mem : %-30s ║", "Activée" if config.memory.enabled else "Désactivée")
    log.info("╚══════════════════════════════════════╝")

    # Lancer le pipeline
    pipeline = AethonPipeline(config)

    try:
        pipeline.load_all()
        log.info("")
        log.info("%s est prêt. Ctrl+C pour arrêter.", config.name)
        log.info("")
        pipeline.run()
    except ConnectionError as e:
        log.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
