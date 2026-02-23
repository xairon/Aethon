import { useState, useEffect } from 'react'
import { useConfig } from '../../stores/useConfig'
import { Section, Field, SegmentControl, ToggleRow } from './Section'
import { LANGUAGES } from '../../lib/constants'

interface AudioDevice {
  id: number
  name: string
  channels: number
}

export function AdvancedSection() {
  const config = useConfig((s) => s.config)
  const updateConfig = useConfig((s) => s.updateConfig)
  const [inputDevices, setInputDevices] = useState<AudioDevice[]>([])
  const [outputDevices, setOutputDevices] = useState<AudioDevice[]>([])
  const [devicesLoading, setDevicesLoading] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    setDevicesLoading(true)
    fetch('/api/devices', { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: { inputs: AudioDevice[]; outputs: AudioDevice[] }) => {
        if (!Array.isArray(data.inputs) || !Array.isArray(data.outputs)) {
          throw new Error('Unexpected response shape')
        }
        setInputDevices(data.inputs)
        setOutputDevices(data.outputs)
        setDevicesLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') {
          setDevicesLoading(false)
          return
        }
        console.error('[AdvancedSection] Failed to fetch devices:', err)
        setDevicesLoading(false)
      })
    return () => controller.abort()
  }, [])

  if (!config) return null
  const { audio, stt, memory } = config

  const updateAudio = (fields: Partial<typeof audio>) => {
    updateConfig({ audio: { ...audio, ...fields } })
  }

  const updateSTT = (fields: Partial<typeof stt>) => {
    updateConfig({ stt: { ...stt, ...fields } })
  }

  const updateMemory = (fields: Partial<typeof memory>) => {
    updateConfig({ memory: { ...memory, ...fields } })
  }

  return (
    <Section
      title="Avancé"
      icon={
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" />
          <line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" />
          <line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" />
          <line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" />
          <line x1="17" y1="16" x2="23" y2="16" />
        </svg>
      }
    >
      {/* Audio */}
      <div className="space-y-3">
        <h4 className="text-[11px] font-semibold text-text-muted uppercase tracking-widest">Audio</h4>

        <Field label="Périphérique d'entrée">
          <select
            value={audio.input_device ?? ''}
            onChange={(e) => updateAudio({ input_device: e.target.value ? parseInt(e.target.value) : null })}
            className="glass-select"
            disabled={devicesLoading}
          >
            <option value="">{devicesLoading ? 'Chargement...' : 'Par défaut'}</option>
            {inputDevices.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </Field>

        <Field label="Périphérique de sortie">
          <select
            value={audio.output_device ?? ''}
            onChange={(e) => updateAudio({ output_device: e.target.value ? parseInt(e.target.value) : null })}
            className="glass-select"
            disabled={devicesLoading}
          >
            <option value="">{devicesLoading ? 'Chargement...' : 'Par défaut'}</option>
            {outputDevices.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </Field>

        <Field label="Gain" value={audio.input_gain.toFixed(1)}>
          <input type="range" min={0.1} max={5.0} step={0.1} value={audio.input_gain}
            onChange={(e) => updateAudio({ input_gain: parseFloat(e.target.value) })} className="glass-slider" />
        </Field>

        <ToggleRow label="AGC (gain auto)" active={audio.auto_gain} onChange={() => updateAudio({ auto_gain: !audio.auto_gain })} />
      </div>

      {/* STT */}
      <div className="space-y-3 pt-3">
        <h4 className="text-[11px] font-semibold text-text-muted uppercase tracking-widest">Reconnaissance vocale</h4>

        <Field label="Modèle">
          <input type="text" value={stt.model} onChange={(e) => updateSTT({ model: e.target.value })}
            className="glass-input" placeholder="large-v3-turbo" />
        </Field>

        <Field label="Device">
          <SegmentControl
            options={[
              { value: 'cuda', label: 'CUDA (GPU)' },
              { value: 'cpu', label: 'CPU' },
            ]}
            value={stt.device}
            onChange={(v) => updateSTT({ device: v })}
          />
        </Field>

        <Field label="Langue STT">
          <select value={stt.language} onChange={(e) => updateSTT({ language: e.target.value })}
            className="glass-select">
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
        </Field>
      </div>

      {/* Memory */}
      <div className="space-y-3 pt-3">
        <h4 className="text-[11px] font-semibold text-text-muted uppercase tracking-widest">Mémoire</h4>

        <ToggleRow label="Activée" active={memory.enabled} onChange={() => updateMemory({ enabled: !memory.enabled })} />

        {memory.enabled && (
          <Field label="Souvenirs max" value={String(memory.max_context_memories)}>
            <input type="range" min={1} max={20} step={1} value={memory.max_context_memories}
              onChange={(e) => updateMemory({ max_context_memories: parseInt(e.target.value) })} className="glass-slider" />
          </Field>
        )}
      </div>
    </Section>
  )
}
