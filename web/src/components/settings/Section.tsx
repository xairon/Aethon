import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface SectionProps {
  title: string
  icon?: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}

/** Collapsible glass section for settings */
export function Section({ title, icon, defaultOpen = false, children }: SectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="w-full flex items-center gap-2.5 py-4 text-left group"
      >
        {icon && (
          <span className="text-text-muted group-hover:text-text-secondary transition-colors">
            {icon}
          </span>
        )}
        <span className="text-[13px] font-semibold text-text-secondary group-hover:text-text transition-colors flex-1">
          {title}
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-text-muted transition-transform duration-300 ease-out"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="pb-5 space-y-4">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ========== Reusable sub-components for glass form controls ========== */

/** Glass toggle switch */
export function GlassToggle({ active, onChange }: { active: boolean; onChange: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      className="glass-toggle"
      data-active={active}
      onClick={onChange}
    >
      <div className="toggle-dot" />
    </button>
  )
}

/** Glass checkbox — visual indicator only, interaction handled by parent button */
export function GlassCheckbox({ checked }: { checked: boolean }) {
  return (
    <div
      aria-hidden="true"
      className="glass-checkbox"
      data-checked={checked}
    >
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </div>
  )
}

/** Segment control (radio buttons replacement) */
export function SegmentControl({ options, value, onChange }: {
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="segment-control" role="radiogroup">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          className="segment-btn"
          data-active={value === opt.value}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

/** Labeled field wrapper */
export function Field({ label, children, value }: {
  label: string
  children: React.ReactNode
  value?: string
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="field-label">{label}</span>
        {value && <span className="field-value">{value}</span>}
      </div>
      {children}
    </div>
  )
}

/** Toggle row: label on left, toggle on right */
export function ToggleRow({ label, active, onChange }: {
  label: string
  active: boolean
  onChange: () => void
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-[13px] text-text">{label}</span>
      <GlassToggle active={active} onChange={onChange} />
    </div>
  )
}
