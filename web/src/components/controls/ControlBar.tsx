import { usePipeline } from '../../stores/usePipeline'
import { useConnection } from '../../stores/useConnection'
import { stateColors, stateLabels } from '../../lib/theme'

interface ControlBarProps {
  onOpenSettings: () => void
}

/** Floating glass control bar */
export function ControlBar({ onOpenSettings }: ControlBarProps) {
  const state = usePipeline((s) => s.state)
  const connected = usePipeline((s) => s.connected)
  const wsConnected = useConnection((s) => s.connected)

  const isRunning = state !== 'stopped'
  const color = stateColors[state]
  const label = stateLabels[state]

  const handleStart = () => {
    console.log('[UI] Start clicked — connected:', connected, 'wsConnected:', wsConnected)
    useConnection.getState().startPipeline()
  }
  const handleStop = () => {
    console.log('[UI] Stop clicked — connected:', connected, 'wsConnected:', wsConnected)
    useConnection.getState().stopPipeline()
  }

  return (
    <div className="fixed bottom-5 left-5 right-5 z-20">
      <div
        className="flex items-center px-4 py-3 gap-3 rounded-2xl glass"
        style={{
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.04)',
        }}
      >
        {/* State indicator with pulse */}
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <div
              className="w-2.5 h-2.5 rounded-full transition-colors duration-500"
              style={{ backgroundColor: color }}
            />
            {/* Pulse ring when active */}
            {state !== 'stopped' && (
              <div
                className="absolute inset-0 rounded-full animate-pulse-glow"
                style={{
                  backgroundColor: color,
                  filter: `blur(4px)`,
                }}
              />
            )}
          </div>
          <span className="text-[13px] text-text-secondary font-medium tracking-wide">
            {label}
          </span>
        </div>

        {/* Connection badge */}
        {!connected && (
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium"
            style={{
              background: 'rgba(251, 191, 36, 0.1)',
              border: '1px solid rgba(251, 191, 36, 0.2)',
              color: '#fbbf24',
            }}
          >
            <div className="w-1.5 h-1.5 rounded-full bg-amber" />
            Hors ligne
          </div>
        )}

        <div className="flex-1" />

        {/* Settings button */}
        <button
          onClick={onOpenSettings}
          className="glass-btn-icon flex items-center justify-center"
          title="Paramètres"
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>

        {/* Start / Stop button */}
        {!isRunning ? (
          <button
            onClick={handleStart}
            disabled={!connected}
            className={`glass-btn glass-btn-success ${!connected ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            Démarrer
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={!connected}
            className={`glass-btn glass-btn-danger ${!connected ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
            Arrêter
          </button>
        )}
      </div>
    </div>
  )
}
