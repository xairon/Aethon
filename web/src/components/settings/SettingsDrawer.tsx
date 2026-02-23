import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useConfig } from '../../stores/useConfig'
import { PersonaSection } from './PersonaSection'
import { IntelligenceSection } from './IntelligenceSection'
import { VoiceSection } from './VoiceSection'
import { ToolsSection } from './ToolsSection'
import { AdvancedSection } from './AdvancedSection'

interface SettingsDrawerProps {
  open: boolean
  onClose: () => void
}

export function SettingsDrawer({ open, onClose }: SettingsDrawerProps) {
  const config = useConfig((s) => s.config)
  const loading = useConfig((s) => s.loading)
  const saving = useConfig((s) => s.saving)
  const dirty = useConfig((s) => s.dirty)
  const fetchConfig = useConfig((s) => s.fetchConfig)
  const saveConfig = useConfig((s) => s.saveConfig)

  useEffect(() => {
    if (open) fetchConfig()
  }, [open, fetchConfig])

  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(0, 0, 0, 0.5)' }}
            onClick={onClose}
          />

          {/* Panel */}
          <motion.div
            initial={{ x: '100%', opacity: 0.8 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0.8 }}
            transition={{ type: 'spring', damping: 28, stiffness: 280 }}
            className="fixed top-0 right-0 bottom-0 z-50 w-full sm:w-[440px] flex flex-col"
            style={{
              background: 'rgba(11, 14, 21, 0.82)',
              backdropFilter: 'blur(40px)',
              WebkitBackdropFilter: 'blur(40px)',
              borderLeft: '1px solid rgba(255, 255, 255, 0.06)',
              boxShadow: '-20px 0 60px rgba(0, 0, 0, 0.5)',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-6 py-5 shrink-0"
              style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center"
                  style={{
                    background: 'rgba(79, 143, 255, 0.12)',
                    border: '1px solid rgba(79, 143, 255, 0.2)',
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4f8fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                  </svg>
                </div>
                <h2 className="text-[15px] font-semibold text-text">Paramètres</h2>
              </div>
              <button
                onClick={onClose}
                className="glass-btn-icon flex items-center justify-center"
                style={{ width: 32, height: 32, borderRadius: 10 }}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-6 py-4 scrollbar-glass">
              {loading && !config ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-7 h-7 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />
                </div>
              ) : config ? (
                <div className="space-y-1">
                  <PersonaSection />
                  <IntelligenceSection />
                  <VoiceSection />
                  <ToolsSection />
                  <AdvancedSection />
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <div className="w-10 h-10 rounded-xl glass-elevated flex items-center justify-center">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-muted">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                  </div>
                  <p className="text-sm text-text-muted">Connexion au serveur requise</p>
                </div>
              )}
            </div>

            {/* Save footer */}
            <AnimatePresence>
              {dirty && (
                <motion.div
                  initial={{ y: 20, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: 20, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-6 py-4 shrink-0"
                  style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}
                >
                  <button
                    onClick={() => saveConfig()}
                    disabled={saving}
                    className={`glass-btn glass-btn-primary w-full ${saving ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {saving ? (
                      <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    ) : (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                        <polyline points="17 21 17 13 7 13 7 21" />
                        <polyline points="7 3 7 8 15 8" />
                      </svg>
                    )}
                    {saving ? 'Sauvegarde...' : 'Sauvegarder'}
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
