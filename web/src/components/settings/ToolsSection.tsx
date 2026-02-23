import { useConfig } from '../../stores/useConfig'
import { Section, Field, ToggleRow } from './Section'

export function ToolsSection() {
  const config = useConfig((s) => s.config)
  const updateConfig = useConfig((s) => s.updateConfig)

  if (!config) return null
  const { tools } = config

  const updateTools = (fields: Partial<typeof tools>) => {
    updateConfig({ tools: { ...tools, ...fields } })
  }

  return (
    <Section
      title="Outils"
      icon={
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
        </svg>
      }
    >
      <ToggleRow label="Date & Heure" active={tools.enable_datetime} onChange={() => updateTools({ enable_datetime: !tools.enable_datetime })} />
      <ToggleRow label="Info Système" active={tools.enable_system_info} onChange={() => updateTools({ enable_system_info: !tools.enable_system_info })} />

      <div className="space-y-3 pt-1">
        <ToggleRow label="Serveur API" active={tools.enable_api_server} onChange={() => updateTools({ enable_api_server: !tools.enable_api_server })} />
        {tools.enable_api_server && (
          <Field label="Port">
            <input
              type="number"
              value={tools.api_port}
              onChange={(e) => updateTools({ api_port: parseInt(e.target.value) || 8741 })}
              className="glass-input"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            />
          </Field>
        )}
      </div>
    </Section>
  )
}
