export interface Instruction {
  id: string
  label: string
  content: string
  enabled: boolean
  builtin: boolean
}

export interface PersonaConfig {
  name: string
  language: string
  wake_phrase: string
  wake_enabled: boolean
  wake_threshold: number
  wake_mode: string
  tts_backend: string
  voice_id: string
  reference_audio: string
  voice_speed: number
  voices_dir: string
  reference_text: string
  active_voice_id: string
  instructions: Instruction[]
}

export interface LLMConfig {
  backend: string
  model: string
  api_key: string
  ollama_model: string
  base_url: string
  temperature: number
  max_tokens: number
  system_prompt_override: string
  enable_search: boolean
  enable_tools: boolean
  thinking_budget: number
}

export interface TTSConfig {
  backend: string
  kokoro_lang: string
  kokoro_voice: string
  chatterbox_exaggeration: number
  chatterbox_cfg_weight: number
  chatterbox_temperature: number
  chatterbox_repetition_penalty: number
  chatterbox_top_p: number
  chatterbox_min_p: number
  chatterbox_seed: number
  speed: number
}

export interface STTConfig {
  model: string
  device: string
  compute_type: string
  language: string
  beam_size: number
  vad_filter: boolean
  vad_threshold: number
}

export interface AudioConfig {
  sample_rate: number
  channels: number
  chunk_duration_ms: number
  silence_timeout_ms: number
  min_speech_ms: number
  playback_sample_rate: number
  input_device: number | null
  output_device: number | null
  input_gain: number
  auto_gain: boolean
  auto_gain_target_rms: number
}

export interface MemoryConfig {
  enabled: boolean
  db_path: string
  max_context_memories: number
  max_conversation_turns: number
}

export interface ToolsConfig {
  enable_datetime: boolean
  enable_system_info: boolean
  enable_api_server: boolean
  api_port: number
}

export interface AethonConfig {
  persona: PersonaConfig
  llm: LLMConfig
  tts: TTSConfig
  stt: STTConfig
  audio: AudioConfig
  memory: MemoryConfig
  tools: ToolsConfig
}
