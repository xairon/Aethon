/** Obsidian Dark theme — matches aethon/gui/theme.py */

export const colors = {
  bg: {
    void: '#08090f',
    base: '#0d1017',
    surface: '#131720',
    raised: '#1a1f2e',
    elevated: '#232a3c',
  },
  text: {
    DEFAULT: '#e2e8f0',
    secondary: '#8b95a8',
    muted: '#4a5568',
    inverse: '#08090f',
  },
  accent: {
    DEFAULT: '#4f8fff',
    hover: '#6aa0ff',
    violet: '#917cf7',
  },
  green: '#34d399',
  amber: '#fbbf24',
  red: '#f87171',
  cyan: '#22d3ee',
  border: {
    DEFAULT: '#1e2536',
    focus: '#4f8fff',
  },
} as const

export type PipelineState = 'stopped' | 'loading' | 'idle' | 'listening' | 'thinking' | 'speaking'

export const stateColors: Record<PipelineState, string> = {
  stopped: '#4a5568',
  loading: '#fbbf24',
  idle: '#34d399',
  listening: '#4f8fff',
  thinking: '#917cf7',
  speaking: '#22d3ee',
}

export const stateLabels: Record<PipelineState, string> = {
  stopped: 'Arrêté',
  loading: 'Chargement...',
  idle: 'Prêt',
  listening: 'Écoute...',
  thinking: 'Réflexion...',
  speaking: 'Parle...',
}
