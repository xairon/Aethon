export interface VoiceMeta {
  id: string
  name: string
  lang: string
  gender: string
  source: string
  duration_s: number
  path: string
}

export interface HFVoiceInfo {
  hf_id: string
  display_name: string
  category: string
  size_mb: number
  is_installed: boolean
}
