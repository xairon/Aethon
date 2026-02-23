import { create } from 'zustand'
import type { JarvisConfig } from '../types/config'
import { usePipeline } from './usePipeline'

interface ConfigStore {
  config: JarvisConfig | null
  loading: boolean
  saving: boolean
  dirty: boolean

  fetchConfig: () => Promise<void>
  updateConfig: (partial: Partial<JarvisConfig>) => void
  saveConfig: () => Promise<void>
  resetConfig: () => Promise<void>
}

function deepMerge(target: Record<string, any>, source: Record<string, any>): Record<string, any> {
  const result = { ...target }
  for (const key of Object.keys(source)) {
    const sv = source[key]
    const tv = target[key]
    if (
      sv && typeof sv === 'object' && !Array.isArray(sv) &&
      tv && typeof tv === 'object' && !Array.isArray(tv)
    ) {
      result[key] = deepMerge(tv, sv)
    } else if (sv !== undefined) {
      result[key] = sv
    }
  }
  return result
}

export const useConfig = create<ConfigStore>((set, get) => ({
  config: null,
  loading: false,
  saving: false,
  dirty: false,

  fetchConfig: async () => {
    if (get().loading) return
    set({ loading: true })
    try {
      const res = await fetch('/api/config')
      if (!res.ok) throw new Error(`Fetch failed: HTTP ${res.status}`)
      const config: JarvisConfig = await res.json()
      set({ config, loading: false, dirty: false })
    } catch (err) {
      console.error('[Config] fetch failed:', err)
      set({ loading: false })
    }
  },

  updateConfig: (partial) => {
    const current = get().config
    if (!current) return
    const merged = deepMerge(current as any, partial as any) as JarvisConfig
    set({ config: merged, dirty: true })
  },

  saveConfig: async () => {
    const { config, dirty, saving } = get()
    if (!config || !dirty || saving) return
    set({ saving: true })
    try {
      const res = await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      if (!res.ok) throw new Error(`Save failed: HTTP ${res.status}`)
      set({ dirty: false, saving: false })
    } catch (err) {
      console.error('[Config] save failed:', err)
      set({ saving: false })
      usePipeline.getState().addToast(
        `Sauvegarde échouée : ${err instanceof Error ? err.message : String(err)}`,
        'error'
      )
    }
  },

  resetConfig: async () => {
    await get().fetchConfig()
  },
}))
