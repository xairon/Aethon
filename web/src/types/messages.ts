// Server -> Client messages

export interface StateMessage {
  type: 'state'
  state: string
  label: string
}

export interface TranscriptMessage {
  type: 'transcript'
  text: string
  timestamp: number
}

export interface ResponseMessage {
  type: 'response'
  text: string
  timestamp: number
}

export interface AudioLevelMessage {
  type: 'audio_level'
  level: number
}

export interface ErrorMessage {
  type: 'error'
  message: string
}

export interface ToastMessage {
  type: 'toast'
  message: string
  level: 'success' | 'warning' | 'error' | 'info'
}

export interface HFProgressMessage {
  type: 'hf_progress'
  current: number
  total: number
  name: string
}

export type ServerMessage =
  | StateMessage
  | TranscriptMessage
  | ResponseMessage
  | AudioLevelMessage
  | ErrorMessage
  | ToastMessage
  | HFProgressMessage

// Client -> Server messages

export interface CommandMessage {
  type: 'command'
  action: 'start' | 'stop'
}

export interface ConfigUpdateMessage {
  type: 'config_update'
  config: Record<string, unknown>
}

export interface TextInputMessage {
  type: 'text_input'
  text: string
}

export type ClientMessage = CommandMessage | ConfigUpdateMessage | TextInputMessage
