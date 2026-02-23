import { useState, useEffect, useRef, useCallback } from 'react'
import { useConfig } from '../../stores/useConfig'
import { Section, Field, SegmentControl } from './Section'

/* ───────── Types ───────── */

interface VoiceMeta {
  id: string
  name: string
  lang: string
  gender: string
  source: string
  duration_s: number
  path: string
}

/* ───────── Constants ───────── */

const KOKORO_VOICES = [
  { value: 'ff_siwis', label: 'Siwis (FR femme)' },
  { value: 'ff_alma', label: 'Alma (FR femme)' },
  { value: 'fm_laurent', label: 'Laurent (FR homme)' },
  { value: 'fm_cedric', label: 'Cedric (FR homme)' },
  { value: 'af_heart', label: 'Heart (EN femme)' },
  { value: 'af_bella', label: 'Bella (EN femme)' },
  { value: 'am_adam', label: 'Adam (EN homme)' },
  { value: 'am_michael', label: 'Michael (EN homme)' },
  { value: 'bf_emma', label: 'Emma (EN-GB femme)' },
  { value: 'bm_george', label: 'George (EN-GB homme)' },
]

const LANG_LABELS: Record<string, string> = {
  fr: 'FR', en: 'EN', de: 'DE', es: 'ES', it: 'IT',
  pt: 'PT', ja: 'JA', zh: 'ZH', ko: 'KO', ar: 'AR', unknown: '??',
}

const GENDER_LABELS: Record<string, string> = {
  male: '\u2642', female: '\u2640', unknown: '\u26AA',
}

/* ───────── Main Component ───────── */

export function VoiceSection() {
  const config = useConfig((s) => s.config)
  const updateConfig = useConfig((s) => s.updateConfig)

  // Local state
  const [voices, setVoices] = useState<VoiceMeta[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedId, setSelectedId] = useState('')
  const [playingId, setPlayingId] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  if (!config) return null
  const { persona, tts } = config

  const updatePersona = (fields: Partial<typeof persona>) => {
    updateConfig({ persona: { ...persona, ...fields } })
  }

  const updateTTS = (fields: Partial<typeof tts>) => {
    updateConfig({ tts: { ...tts, ...fields } })
  }

  // Fetch voices when Chatterbox is selected
  const fetchVoices = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/voices')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: VoiceMeta[] = await res.json()
      setVoices(data)
    } catch (err) {
      console.error('[VoiceSection] Failed to fetch voices:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // Sync selected voice from config on mount
  useEffect(() => {
    if (persona.active_voice_id) {
      setSelectedId(persona.active_voice_id)
    }
  }, [persona.active_voice_id])

  useEffect(() => {
    if (persona.tts_backend === 'chatterbox') {
      fetchVoices()
    }
  }, [persona.tts_backend, fetchVoices])

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  // Select a voice
  const selectVoice = (voice: VoiceMeta) => {
    setSelectedId(voice.id)
    updatePersona({
      active_voice_id: voice.id,
      reference_audio: voice.path,
    })
  }

  // Play preview
  const playVoice = (voiceId: string) => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    if (playingId === voiceId) {
      setPlayingId(null)
      return
    }
    const audio = new Audio(`/api/voices/${voiceId}/audio`)
    audio.onended = () => setPlayingId(null)
    audio.onerror = () => setPlayingId(null)
    audio.play().catch(() => setPlayingId(null))
    audioRef.current = audio
    setPlayingId(voiceId)
  }

  // Delete voice
  const deleteVoice = async (voiceId: string) => {
    try {
      const res = await fetch(`/api/voices/${voiceId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setVoices((prev) => prev.filter((v) => v.id !== voiceId))
      if (selectedId === voiceId) {
        setSelectedId('')
        updatePersona({ active_voice_id: '', reference_audio: '' })
      }
    } catch (err) {
      console.error('[VoiceSection] Delete failed:', err)
    }
  }

  // Import WAV
  const handleImport = async (file: File) => {
    setImporting(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('name', file.name.replace(/\.wav$/i, ''))
      formData.append('lang', persona.language || 'fr')
      formData.append('gender', 'unknown')

      const res = await fetch('/api/voices/import', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const newVoice: VoiceMeta = await res.json()
      setVoices((prev) => [...prev, newVoice])
      selectVoice(newVoice)
    } catch (err) {
      console.error('[VoiceSection] Import failed:', err)
    } finally {
      setImporting(false)
    }
  }

  const activeVoice = voices.find((v) => v.id === selectedId)

  return (
    <Section
      title="Voix"
      icon={
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      }
    >
      <Field label="Backend TTS">
        <SegmentControl
          options={[
            { value: 'kokoro', label: 'Kokoro' },
            { value: 'chatterbox', label: 'Chatterbox' },
          ]}
          value={persona.tts_backend}
          onChange={(v) => {
            updatePersona({ tts_backend: v })
            updateTTS({ backend: v })
          }}
        />
      </Field>

      {/* ───── Kokoro voice selector ───── */}
      {persona.tts_backend === 'kokoro' && (
        <Field label="Voix">
          <select
            value={persona.voice_id}
            onChange={(e) => {
              updatePersona({ voice_id: e.target.value })
              updateTTS({ kokoro_voice: e.target.value })
            }}
            className="glass-select"
          >
            {KOKORO_VOICES.map((v) => (
              <option key={v.value} value={v.value}>{v.label}</option>
            ))}
          </select>
        </Field>
      )}

      {/* ───── Chatterbox voice library ───── */}
      {persona.tts_backend === 'chatterbox' && (
        <div className="space-y-3">

          {/* Active voice indicator */}
          {activeVoice ? (
            <div
              className="flex items-center gap-3 px-4 py-3 rounded-xl"
              style={{
                background: 'rgba(52, 211, 153, 0.06)',
                border: '1px solid rgba(52, 211, 153, 0.15)',
              }}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: 'rgba(52, 211, 153, 0.15)' }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-semibold text-text truncate">{activeVoice.name}</div>
                <div className="text-[11px] text-text-muted flex items-center gap-1.5 mt-0.5">
                  <span>{LANG_LABELS[activeVoice.lang] || activeVoice.lang}</span>
                  <span style={{ opacity: 0.3 }}>{'\u00B7'}</span>
                  <span>{GENDER_LABELS[activeVoice.gender] || activeVoice.gender}</span>
                  <span style={{ opacity: 0.3 }}>{'\u00B7'}</span>
                  <span>{activeVoice.duration_s.toFixed(1)}s</span>
                  <span style={{ opacity: 0.3 }}>{'\u00B7'}</span>
                  <span className="opacity-60">{activeVoice.source}</span>
                </div>
              </div>
            </div>
          ) : (
            <div
              className="flex items-center gap-3 px-4 py-3 rounded-xl text-[13px]"
              style={{
                background: 'rgba(251, 191, 36, 0.06)',
                border: '1px solid rgba(251, 191, 36, 0.12)',
                color: '#fbbf24',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              Aucune voix sélectionnée — importez ou sélectionnez ci-dessous
            </div>
          )}

          {/* Voice list */}
          <div
            className="rounded-xl overflow-hidden scrollbar-glass"
            style={{
              border: '1px solid rgba(255, 255, 255, 0.05)',
              maxHeight: 240,
              overflowY: 'auto',
            }}
          >
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-5 h-5 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
              </div>
            ) : voices.length === 0 ? (
              <div className="py-8 text-center text-[12px] text-text-muted">
                Aucune voix installée
              </div>
            ) : (
              <div>
                {voices.map((voice) => {
                  const isSelected = voice.id === selectedId
                  const isPlaying = voice.id === playingId
                  return (
                    <div
                      key={voice.id}
                      className="group flex items-center gap-2.5 px-3 py-2.5 cursor-pointer transition-colors"
                      style={{
                        background: isSelected ? 'rgba(79, 143, 255, 0.08)' : 'transparent',
                        borderLeft: isSelected ? '3px solid #4f8fff' : '3px solid transparent',
                      }}
                      onClick={() => selectVoice(voice)}
                      onMouseEnter={(e) => {
                        if (!isSelected) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) e.currentTarget.style.background = 'transparent'
                      }}
                    >
                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="text-[12.5px] font-medium text-text truncate">
                          {voice.name}
                        </div>
                        <div className="text-[10.5px] text-text-muted flex items-center gap-1 mt-0.5">
                          <span>{LANG_LABELS[voice.lang] || voice.lang}</span>
                          <span style={{ opacity: 0.3 }}>{'\u00B7'}</span>
                          <span>{GENDER_LABELS[voice.gender] || voice.gender}</span>
                          <span style={{ opacity: 0.3 }}>{'\u00B7'}</span>
                          <span>{voice.duration_s.toFixed(1)}s</span>
                        </div>
                      </div>

                      {/* Source badge */}
                      <span
                        className="text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded shrink-0"
                        style={{
                          background: voice.source === 'kyutai'
                            ? 'rgba(79, 143, 255, 0.1)'
                            : 'rgba(255, 255, 255, 0.05)',
                          color: voice.source === 'kyutai'
                            ? '#6aa0ff'
                            : 'var(--color-text-muted)',
                        }}
                      >
                        {voice.source === 'kyutai' ? 'HF' : voice.source}
                      </span>

                      {/* Play button */}
                      <button
                        className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-all cursor-pointer"
                        style={{
                          background: isPlaying ? 'rgba(79, 143, 255, 0.15)' : 'rgba(255, 255, 255, 0.04)',
                          border: `1px solid ${isPlaying ? 'rgba(79, 143, 255, 0.25)' : 'rgba(255, 255, 255, 0.06)'}`,
                        }}
                        onClick={(e) => { e.stopPropagation(); playVoice(voice.id) }}
                        title={isPlaying ? "Arr\u00EAter" : "\u00C9couter"}
                      >
                        {isPlaying ? (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="#4f8fff">
                            <rect x="6" y="4" width="4" height="16" rx="1" />
                            <rect x="14" y="4" width="4" height="16" rx="1" />
                          </svg>
                        ) : (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" className="text-text-secondary">
                            <polygon points="5 3 19 12 5 21 5 3" />
                          </svg>
                        )}
                      </button>

                      {/* Delete button (hidden until hover) */}
                      {voice.source !== 'builtin' && (
                        <button
                          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0
                                     opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                          style={{
                            background: 'rgba(248, 113, 113, 0.08)',
                            border: '1px solid rgba(248, 113, 113, 0.12)',
                          }}
                          onClick={(e) => {
                            e.stopPropagation()
                            if (confirm(`Supprimer la voix "${voice.name}" ?`)) {
                              deleteVoice(voice.id)
                            }
                          }}
                          title="Supprimer"
                        >
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".wav"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleImport(file)
                e.target.value = ''
              }}
            />
            <button
              className="glass-btn flex-1"
              style={{ fontSize: 12.5 }}
              disabled={importing}
              onClick={() => fileInputRef.current?.click()}
            >
              {importing ? (
                <div className="w-3.5 h-3.5 border-2 border-text-muted/40 border-t-text-secondary rounded-full animate-spin" />
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              )}
              Importer un WAV
            </button>

            <button
              className="glass-btn-icon flex items-center justify-center"
              style={{ width: 36, height: 36, borderRadius: 10 }}
              onClick={fetchVoices}
              title="Actualiser"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
            </button>
          </div>

          {/* Chatterbox params */}
          <div className="space-y-3 pt-2">
            <h4 className="text-[11px] font-semibold text-text-muted uppercase tracking-widest">
              Paramètres Chatterbox
            </h4>

            <Field label={"Exagération"} value={tts.chatterbox_exaggeration.toFixed(2)}>
              <input
                type="range" min={0} max={1} step={0.05}
                value={tts.chatterbox_exaggeration}
                onChange={(e) => updateTTS({ chatterbox_exaggeration: parseFloat(e.target.value) })}
                className="glass-slider"
              />
            </Field>

            <Field label="CFG Weight" value={tts.chatterbox_cfg_weight.toFixed(1)}>
              <input
                type="range" min={0} max={1} step={0.1}
                value={tts.chatterbox_cfg_weight}
                onChange={(e) => updateTTS({ chatterbox_cfg_weight: parseFloat(e.target.value) })}
                className="glass-slider"
              />
            </Field>

            <Field label={"Température"} value={tts.chatterbox_temperature.toFixed(2)}>
              <input
                type="range" min={0.1} max={1.5} step={0.05}
                value={tts.chatterbox_temperature}
                onChange={(e) => updateTTS({ chatterbox_temperature: parseFloat(e.target.value) })}
                className="glass-slider"
              />
            </Field>
          </div>
        </div>
      )}

      {/* Speed (both backends) */}
      <Field label="Vitesse" value={tts.speed.toFixed(1)}>
        <input
          type="range"
          min={0.5}
          max={2.0}
          step={0.1}
          value={tts.speed}
          onChange={(e) => updateTTS({ speed: parseFloat(e.target.value) })}
          className="glass-slider"
        />
      </Field>
    </Section>
  )
}
