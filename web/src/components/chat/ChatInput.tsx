import { useState, useRef, useCallback } from 'react'
import { usePipeline } from '../../stores/usePipeline'
import { useConnection } from '../../stores/useConnection'

/** Floating glass text input — bypasses STT, sends text directly to the pipeline. */
export function ChatInput() {
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const state = usePipeline((s) => s.state)
  const connected = usePipeline((s) => s.connected)

  const isRunning = state !== 'stopped' && state !== 'loading'
  const canSend = connected && isRunning && text.trim().length > 0

  const handleSend = useCallback(() => {
    const msg = text.trim()
    if (!msg || !isRunning || !connected) return
    useConnection.getState().sendText(msg)
    setText('')
    inputRef.current?.focus()
  }, [text, isRunning, connected])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  return (
    <div className="flex items-center gap-2">
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={isRunning ? 'Taper un message...' : 'Pipeline arrete'}
        disabled={!isRunning || !connected}
        className="glass-input flex-1"
        style={{ height: 40, borderRadius: 14 }}
      />
      <button
        onClick={handleSend}
        disabled={!canSend}
        className="flex items-center justify-center shrink-0"
        style={{
          width: 40,
          height: 40,
          borderRadius: 14,
          background: canSend ? 'rgba(79, 143, 255, 0.25)' : 'rgba(255, 255, 255, 0.03)',
          border: `1px solid ${canSend ? 'rgba(79, 143, 255, 0.4)' : 'rgba(255, 255, 255, 0.06)'}`,
          color: canSend ? '#a5c8ff' : 'var(--color-text-muted)',
          cursor: canSend ? 'pointer' : 'default',
          transition: 'all 0.25s ease',
        }}
        title="Envoyer (Enter)"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  )
}
