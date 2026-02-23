import { useConfig } from '../../stores/useConfig'
import { Section, Field, GlassToggle, GlassCheckbox } from './Section'
import { LANGUAGES } from '../../lib/constants'

const WAKE_PHRASES = [
  { value: 'hey_jarvis', label: 'Hey Aethon' },
  { value: 'alexa', label: 'Alexa' },
  { value: 'hey_mycroft', label: 'Hey Mycroft' },
  { value: 'ok_google', label: 'OK Google' },
]

export function PersonaSection() {
  const config = useConfig((s) => s.config)
  const updateConfig = useConfig((s) => s.updateConfig)

  if (!config) return null
  const { persona } = config

  const update = (fields: Partial<typeof persona>) => {
    updateConfig({ persona: { ...persona, ...fields } })
  }

  return (
    <Section
      title="Identité"
      icon={
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      }
      defaultOpen
    >
      <Field label="Nom">
        <input
          type="text"
          value={persona.name}
          onChange={(e) => update({ name: e.target.value })}
          className="glass-input"
          placeholder="Nom de l'assistant"
        />
      </Field>

      <Field label="Langue">
        <select
          value={persona.language}
          onChange={(e) => update({ language: e.target.value })}
          className="glass-select"
        >
          {LANGUAGES.map((l) => (
            <option key={l.value} value={l.value}>{l.label}</option>
          ))}
        </select>
      </Field>

      {/* Wake word */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="field-label">Mot de reveil</span>
          <GlassToggle
            active={persona.wake_enabled}
            onChange={() => update({ wake_enabled: !persona.wake_enabled })}
          />
        </div>
        {persona.wake_enabled && (
          <select
            value={persona.wake_phrase}
            onChange={(e) => update({ wake_phrase: e.target.value })}
            className="glass-select"
          >
            {WAKE_PHRASES.map((w) => (
              <option key={w.value} value={w.value}>{w.label}</option>
            ))}
          </select>
        )}
      </div>

      {/* Instructions */}
      {persona.instructions.length > 0 && (
        <div className="space-y-3">
          <span className="field-label">Instructions</span>
          <div className="space-y-0.5">
            {persona.instructions.map((instr) => (
              <button
                key={instr.id}
                onClick={() => {
                  const updated = persona.instructions.map((i) =>
                    i.id === instr.id ? { ...i, enabled: !i.enabled } : i
                  )
                  update({ instructions: updated })
                }}
                className="flex items-center gap-3 w-full py-2 px-1 rounded-lg
                           hover:bg-white/[0.03] transition-colors text-left"
              >
                <GlassCheckbox checked={instr.enabled} />
                <span className={`text-[13px] transition-colors ${
                  instr.enabled ? 'text-text' : 'text-text-muted'
                }`}>
                  {instr.label}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </Section>
  )
}
