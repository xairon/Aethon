import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChatOverlay } from './components/chat/ChatOverlay'
import { ChatInput } from './components/chat/ChatInput'
import { ControlBar } from './components/controls/ControlBar'
import { SettingsDrawer } from './components/settings/SettingsDrawer'
import { OrbCSS } from './components/orb/OrbCSS'
import { useConnection } from './stores/useConnection'
import { usePipeline } from './stores/usePipeline'

/** Toast notification renderer */
function ToastContainer() {
  const toasts = usePipeline((s) => s.toasts)
  const removeToast = usePipeline((s) => s.removeToast)
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  // Per-toast auto-dismiss — only creates a timer for new toasts
  useEffect(() => {
    toasts.forEach((t) => {
      if (!timersRef.current.has(t.id)) {
        const timer = setTimeout(() => {
          removeToast(t.id)
          timersRef.current.delete(t.id)
        }, 4000)
        timersRef.current.set(t.id, timer)
      }
    })
    // Cleanup stale timers for toasts removed by user click
    timersRef.current.forEach((_timer, id) => {
      if (!toasts.some((t) => t.id === id)) {
        clearTimeout(timersRef.current.get(id))
        timersRef.current.delete(id)
      }
    })
  }, [toasts, removeToast])

  // Cleanup all timers on unmount
  useEffect(() => {
    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      timersRef.current.forEach(clearTimeout)
    }
  }, [])

  const toastStyle = useCallback((level: string) => {
    const colors: Record<string, { bg: string; border: string; text: string }> = {
      error:   { bg: 'rgba(248,113,113,0.12)', border: 'rgba(248,113,113,0.25)', text: '#f87171' },
      warning: { bg: 'rgba(251,191,36,0.12)',  border: 'rgba(251,191,36,0.25)',  text: '#fbbf24' },
      success: { bg: 'rgba(52,211,153,0.12)',  border: 'rgba(52,211,153,0.25)',  text: '#34d399' },
      info:    { bg: 'rgba(79,143,255,0.12)',   border: 'rgba(79,143,255,0.25)',  text: '#4f8fff' },
    }
    return colors[level] || colors.info
  }, [])

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => {
          const c = toastStyle(t.level)
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: -8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.96 }}
              transition={{ duration: 0.2 }}
              className="px-4 py-3 rounded-xl text-[13px] font-medium pointer-events-auto cursor-pointer max-w-[360px]"
              style={{
                background: c.bg,
                border: `1px solid ${c.border}`,
                color: c.text,
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
              }}
              onClick={() => removeToast(t.id)}
            >
              {t.message}
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

/** HuggingFace download progress overlay */
function HFProgressOverlay() {
  const progress = usePipeline((s) => s.hfProgress)
  if (!progress) return null
  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[90] pointer-events-none">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="px-5 py-3 rounded-xl text-[13px] font-medium"
        style={{
          background: 'rgba(13, 16, 23, 0.8)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          border: '1px solid rgba(79, 143, 255, 0.2)',
          minWidth: 280,
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-text-secondary">
            Téléchargement : {progress.name}
          </span>
          <span className="text-accent font-semibold tabular-nums">{pct}%</span>
        </div>
        <div
          className="h-1.5 rounded-full overflow-hidden"
          style={{ background: 'rgba(255, 255, 255, 0.06)' }}
        >
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{
              width: `${pct}%`,
              background: 'linear-gradient(90deg, #4f8fff, #6aa0ff)',
              boxShadow: '0 0 8px rgba(79, 143, 255, 0.4)',
            }}
          />
        </div>
      </motion.div>
    </div>
  )
}

function App() {
  const [OrbWebGL, setOrbWebGL] = useState<React.ComponentType | null>(null)
  const [webglFailed, setWebglFailed] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Connect to WebSocket on mount
  useEffect(() => {
    useConnection.getState().connect()
    return () => useConnection.getState().disconnect()
  }, [])

  // Lazy-load WebGL orb; fallback to CSS if unavailable
  useEffect(() => {
    try {
      const canvas = document.createElement('canvas')
      const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
      if (!gl) { setWebglFailed(true); return }

      import('./components/orb/Orb')
        .then((mod) => setOrbWebGL(() => mod.Orb))
        .catch(() => setWebglFailed(true))
    } catch {
      setWebglFailed(true)
    }
  }, [])

  const OrbComponent = webglFailed || !OrbWebGL ? OrbCSS : OrbWebGL

  return (
    <div className="relative w-full h-full">
      <OrbComponent />
      <ChatOverlay />
      {/* Text input — between chat and control bar */}
      <div className="fixed bottom-[76px] left-5 right-5 z-15">
        <ChatInput />
      </div>
      <ControlBar onOpenSettings={() => setSettingsOpen(true)} />
      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <HFProgressOverlay />
      <ToastContainer />
    </div>
  )
}

export default App
