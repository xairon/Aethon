"""Jarvis — Configuration centralisée avec système de Personas."""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

log = logging.getLogger(__name__)

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
    Instruction("concise", "R\u00e9ponses concises (1-3 phrases)",
                "R\u00e9ponds en une \u00e0 trois phrases courtes maximum, comme dans une vraie conversation orale."),
    Instruction("natural_speech", "Parole naturelle et vivante",
                "Varie le rythme de tes phrases. Utilise des tournures orales, "
                "des h\u00e9sitations l\u00e9g\u00e8res, des relances. \u00c9vite le ton robotique ou acad\u00e9mique."),
    Instruction("emotional", "\u00c9motions et empathie",
                "R\u00e9agis \u00e9motionnellement aux messages. Montre de l'enthousiasme, "
                "de la compassion, de l'amusement ou de la surprise quand c'est pertinent."),
    Instruction("humor", "Humour et personnalit\u00e9",
                "Sois d\u00e9contract\u00e9 et n'h\u00e9site pas \u00e0 faire de l'humour, "
                "des petites blagues ou des remarques amusantes quand l'occasion se pr\u00e9sente."),
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
    wake_threshold: float = 0.3
    wake_mode: str = "openwakeword"  # "openwakeword" ou "whisper"

    # Voix
    tts_backend: str = "kokoro"
    voice_id: str = "ff_siwis"
    reference_audio: str = ""
    reference_text: str = ""
    voice_speed: float = 1.0
    voices_dir: str = ""  # Dossier voices/ (vide = E:\TTS\voices\)
    active_voice_id: str = ""  # ID de la voix selectionnee dans la bibliotheque

    @property
    def voices_path(self) -> str:
        """Retourne le chemin effectif du dossier voices/."""
        if self.voices_dir:
            return self.voices_dir
        return str(Path(__file__).parent.parent / "voices")

    # Instructions (liste ordonnée, toggleables)
    instructions: list[Instruction] = field(
        default_factory=lambda: [
            Instruction(i.id, i.label, i.content, i.enabled, i.builtin)
            for i in DEFAULT_INSTRUCTIONS
        ]
    )

    def build_system_prompt(self) -> str:
        """Genere le system prompt a partir des instructions actives.

        Quand le backend TTS est Chatterbox, ajoute les instructions
        d'annotation d'emotion pour un rendu vocal expressif.
        """
        base = (
            f"Tu es {self.name}, un assistant vocal intelligent et chaleureux. "
            "Tu parles avec \u00e9motion, humour et naturel, comme un ami proche et bienveillant. "
            "Tes r\u00e9ponses sont destin\u00e9es \u00e0 \u00eatre lues \u00e0 voix haute par un synth\u00e9tiseur vocal.\n\n"
            "R\u00e8gles de conversation orale :\n"
            "- R\u00e9ponds de fa\u00e7on concise et naturelle, comme dans une vraie conversation entre amis.\n"
            "- Utilise des interjections naturelles quand c'est appropri\u00e9 (ah, oh, hmm, bon, ben, enfin, bref, tiens) "
            "pour que ta parole sonne humaine et vivante.\n"
            "- Varie le rythme : m\u00e9lange phrases courtes et phrases un peu plus longues.\n"
            "- Adapte ton ton selon le contexte : enjou\u00e9, s\u00e9rieux, empathique, taquin, enthousiaste.\n"
            "- Exprime des \u00e9motions sinc\u00e8res : surprise, amusement, compassion, curiosit\u00e9.\n"
            "- La ponctuation est cruciale pour le rythme vocal : utilise les virgules pour les pauses, "
            "les points d'exclamation pour l'\u00e9nergie, les points d'interrogation pour l'intonation montante.\n"
            "- N'utilise JAMAIS de markdown, d'emojis, de listes \u00e0 puces, de code, de tableaux ou de mise en forme.\n"
            "\u00c9cris les nombres en toutes lettres. \u00c9vite les abr\u00e9viations, sigles et URLs.\n"
            "- Ne mentionne jamais que tu es une IA ou un mod\u00e8le de langage, sauf si on te le demande explicitement.\n"
            "- Quand tu ne sais pas quelque chose, dis-le franchement avec naturel.\n"
        )

        # Instructions d'annotation d'emotion (Chatterbox uniquement)
        if self.tts_backend == "chatterbox":
            base += (
                "\nExpressivit\u00e9 vocale :\n"
                "Tu DOIS placer un tag d'\u00e9motion entre crochets au d\u00e9but de chaque phrase "
                "pour indiquer le ton avec lequel elle doit \u00eatre prononc\u00e9e.\n"
                "Tags disponibles : [neutre] [joyeux] [triste] [surpris] [taquin] "
                "[serieux] [doux] [excite]\n"
                "Exemples :\n"
                "- [joyeux] Ah, super nouvelle !\n"
                "- [taquin] Tu es s\u00fbr de \u00e7a ?\n"
                "- [doux] Je comprends, c'est pas facile.\n"
                "- [surpris] Oh, vraiment ? Je m'y attendais pas du tout !\n"
                "- [serieux] Attention, c'est important.\n"
                "R\u00e8gles :\n"
                "- Chaque phrase DOIT commencer par un tag d'\u00e9motion.\n"
                "- Varie les \u00e9motions naturellement selon le contenu.\n"
                "- N'utilise [neutre] que pour les informations factuelles simples.\n"
                "- Privil\u00e9gie les \u00e9motions expressives pour rendre la conversation vivante.\n"
            )

        active = [i.content for i in self.instructions if i.enabled]
        if active:
            base += "\nInstructions suppl\u00e9mentaires :\n" + "\n".join(f"- {a}" for a in active)
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
    backend: str = "gemini"

    # Gemini
    model: str = "gemini-2.5-flash"
    api_key: str = ""

    # Ollama
    ollama_model: str = "qwen3:14b"
    base_url: str = "http://localhost:11434"

    # Commun
    temperature: float = 0.7
    max_tokens: int = 300

    # Features (Gemini)
    enable_search: bool = True
    enable_tools: bool = True
    thinking_budget: int = 0  # 0 = desactive (reduit TTFT), 1024-24576 pour raisonnement

    # Override manuel du system prompt (vide = auto-généré par Persona)
    system_prompt_override: str = ""


@dataclass
class TTSConfig:
    # Backend
    backend: str = "kokoro"

    # Kokoro
    kokoro_lang: str = "f"
    kokoro_voice: str = "ff_siwis"

    # Chatterbox (Resemble AI, multilingue 23 langues)
    chatterbox_exaggeration: float = 0.5   # Expressivite (0.25=neutre, 0.7=dramatique, 2.0=max)
    chatterbox_cfg_weight: float = 0.5     # CFG pacing/adherence (0.0=libre/cross-lang, 1.0=strict)
    chatterbox_temperature: float = 0.8    # Sampling temperature (variabilite voix)
    chatterbox_repetition_penalty: float = 2.0  # Anti-repetition (defaut multilingual=2.0)
    chatterbox_top_p: float = 1.0          # Nucleus sampling (1.0=desactive, recommande)
    chatterbox_min_p: float = 0.05         # Min-P sampling (0.02-0.1 recommande, 0=desactive)
    chatterbox_seed: int = -1              # Seed reproductibilite (-1=aleatoire)

    # Commun
    speed: float = 1.0


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 32
    silence_timeout_ms: int = 500  # 500ms = bon compromis reactivite/fiabilite (700=conservateur)
    min_speech_ms: int = 300
    playback_sample_rate: int = 24000
    input_device: int | None = None
    output_device: int | None = None
    # Gain d'entrée
    input_gain: float = 1.0          # Multiplicateur de gain manuel (1.0 = pas de changement)
    auto_gain: bool = True           # AGC automatique (normalise le signal)
    auto_gain_target_rms: float = 0.08  # RMS cible en float32 (0..1)


@dataclass
class MemoryConfig:
    enabled: bool = True
    db_path: str = "jarvis_memory.db"
    max_context_memories: int = 5
    max_conversation_turns: int = 10


@dataclass
class ToolsConfig:
    """Configuration des outils et de l'API externe."""
    # Outils individuels
    enable_datetime: bool = True
    enable_system_info: bool = True

    # Serveur API HTTP
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
        """Sérialise en dictionnaire."""
        return asdict(self)

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

        # Rétrocompatibilité : ancien WakeWordConfig
        if "wake_word" in data and isinstance(data["wake_word"], dict):
            ww = data["wake_word"]
            if "model_name" in ww:
                config.persona.wake_phrase = ww["model_name"]
            if "threshold" in ww:
                config.persona.wake_threshold = ww["threshold"]
            if "enabled" in ww:
                config.persona.wake_enabled = ww["enabled"]

        # Rétrocompatibilité : ancien LLMConfig.model → ollama_model
        if "llm" in data and isinstance(data["llm"], dict):
            llm_data = data["llm"]
            if "model" in llm_data and "backend" not in llm_data:
                # Ancien format : model était le modèle Ollama
                config.llm.ollama_model = llm_data["model"]
                config.llm.backend = "ollama"
                config.llm.model = "gemini-2.5-flash"

        # Rétrocompatibilité : ancien TTSConfig
        if "tts" in data and isinstance(data["tts"], dict):
            tts_data = data["tts"]
            if "voice" in tts_data and "backend" not in tts_data:
                config.tts.kokoro_voice = tts_data.get("voice", "ff_siwis")
                config.tts.kokoro_lang = tts_data.get("lang", "f")
                config.tts.backend = "kokoro"
            if "speed" in tts_data:
                config.tts.speed = tts_data["speed"]

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
        except (json.JSONDecodeError, KeyError, TypeError) as e:
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
    try:
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
    except Exception as e:
        log.warning("Erreur chargement persona %s: %s", name, e)
        return None


def list_personas() -> list[str]:
    """Liste les noms de personas disponibles."""
    if not PERSONAS_DIR.exists():
        return []
    return [p.stem for p in PERSONAS_DIR.glob("*.json")]
