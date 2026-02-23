import { useConfig } from '../../stores/useConfig'
import { Section, Field, SegmentControl, ToggleRow } from './Section'

export function IntelligenceSection() {
  const config = useConfig((s) => s.config)
  const updateConfig = useConfig((s) => s.updateConfig)

  if (!config) return null
  const { llm } = config

  const update = (fields: Partial<typeof llm>) => {
    updateConfig({ llm: { ...llm, ...fields } })
  }

  return (
    <Section
      title="Intelligence"
      icon={
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      }
    >
      <Field label="Backend LLM">
        <SegmentControl
          options={[
            { value: 'gemini', label: 'Gemini' },
            { value: 'ollama', label: 'Ollama' },
          ]}
          value={llm.backend}
          onChange={(v) => update({ backend: v })}
        />
      </Field>

      {llm.backend === 'gemini' && (
        <>
          <Field label="Modèle">
            <input
              type="text"
              value={llm.model}
              onChange={(e) => update({ model: e.target.value })}
              className="glass-input"
              placeholder="gemini-2.5-flash"
            />
          </Field>

          <Field label="Clé API">
            <input
              type="password"
              value={llm.api_key}
              onChange={(e) => update({ api_key: e.target.value })}
              className="glass-input"
              placeholder="AIza..."
            />
          </Field>

          <ToggleRow label="Google Search" active={llm.enable_search} onChange={() => update({ enable_search: !llm.enable_search })} />
          <ToggleRow label="Function Calling" active={llm.enable_tools} onChange={() => update({ enable_tools: !llm.enable_tools })} />

          <Field label="Thinking Budget" value={String(llm.thinking_budget)}>
            <input type="range" min={0} max={24576} step={1024} value={llm.thinking_budget}
              onChange={(e) => update({ thinking_budget: parseInt(e.target.value) })} className="glass-slider" />
          </Field>
        </>
      )}

      {llm.backend === 'ollama' && (
        <>
          <Field label="URL de base">
            <input type="text" value={llm.base_url} onChange={(e) => update({ base_url: e.target.value })}
              className="glass-input" placeholder="http://localhost:11434" />
          </Field>
          <Field label="Modèle">
            <input type="text" value={llm.ollama_model} onChange={(e) => update({ ollama_model: e.target.value })}
              className="glass-input" placeholder="qwen3:14b" />
          </Field>
        </>
      )}

      <Field label="Température" value={llm.temperature.toFixed(1)}>
        <input type="range" min={0} max={2} step={0.1} value={llm.temperature}
          onChange={(e) => update({ temperature: parseFloat(e.target.value) })} className="glass-slider" />
      </Field>

      <Field label="Tokens max" value={String(llm.max_tokens)}>
        <input type="range" min={50} max={2000} step={50} value={llm.max_tokens}
          onChange={(e) => update({ max_tokens: parseInt(e.target.value) })} className="glass-slider" />
      </Field>
    </Section>
  )
}
