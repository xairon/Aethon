import { create } from 'zustand'
import type { PipelineState } from '../lib/theme'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  timestamp: number
}

interface Toast {
  id: string
  message: string
  level: 'success' | 'warning' | 'error' | 'info'
  timestamp: number
}

interface HFProgress {
  current: number
  total: number
  name: string
}

interface PipelineStore {
  state: PipelineState
  audioLevel: number
  messages: ChatMessage[]
  toasts: Toast[]
  connected: boolean
  hfProgress: HFProgress | null

  setState: (state: PipelineState) => void
  setAudioLevel: (level: number) => void
  setConnected: (connected: boolean) => void
  addMessage: (role: 'user' | 'assistant', text: string) => void
  addToast: (message: string, level: Toast['level']) => void
  removeToast: (id: string) => void
  setHfProgress: (progress: HFProgress | null) => void
}

function generateId(): string {
  return crypto.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export const usePipeline = create<PipelineStore>((set) => ({
  state: 'stopped',
  audioLevel: 0,
  messages: [],
  toasts: [],
  connected: false,
  hfProgress: null,

  setState: (state) => set({ state }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setConnected: (connected) => set({ connected }),
  addMessage: (role, text) =>
    set((s) => ({
      messages: [
        ...s.messages.slice(-99),
        { id: generateId(), role, text, timestamp: Date.now() },
      ],
    })),
  addToast: (message, level) =>
    set((s) => ({
      toasts: [
        ...s.toasts.slice(-4),
        { id: generateId(), message, level, timestamp: Date.now() },
      ],
    })),
  removeToast: (id) =>
    set((s) => ({
      toasts: s.toasts.filter((t) => t.id !== id),
    })),
  setHfProgress: (progress) => set({ hfProgress: progress }),
}))
