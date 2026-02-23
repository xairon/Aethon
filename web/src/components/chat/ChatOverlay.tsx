import { useEffect, useRef } from 'react'
import { usePipeline } from '../../stores/usePipeline'
import { useConfig } from '../../stores/useConfig'
import { ChatBubble } from './ChatBubble'

/** Glass chat overlay floating above the orb */
export function ChatOverlay() {
  const messages = usePipeline((s) => s.messages)
  const personaName = useConfig((s) => s.config?.persona.name) ?? 'Assistant'
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div className="fixed bottom-32 left-5 right-5 max-h-[35vh] z-10 pointer-events-none">
      <div
        ref={scrollRef}
        className="overflow-y-auto max-h-[35vh] rounded-2xl px-4 py-3 pointer-events-auto scrollbar-glass"
        style={{
          background: messages.length > 0 ? 'rgba(11, 14, 21, 0.6)' : 'transparent',
          backdropFilter: messages.length > 0 ? 'blur(20px)' : 'none',
          WebkitBackdropFilter: messages.length > 0 ? 'blur(20px)' : 'none',
          border: messages.length > 0 ? '1px solid rgba(255, 255, 255, 0.05)' : 'none',
          boxShadow: messages.length > 0 ? '0 8px 32px rgba(0, 0, 0, 0.3)' : 'none',
          transition: 'all 0.3s ease',
        }}
      >
        {messages.length === 0 ? (
          <div className="flex items-center justify-center py-8 select-none">
            <div className="flex items-center gap-3">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: 'rgba(255, 255, 255, 0.15)' }}
              />
              <span className="text-[13px] text-text-muted tracking-wide">
                En attente de conversation...
              </span>
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: 'rgba(255, 255, 255, 0.15)' }}
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {messages.map((msg) => (
              <ChatBubble key={msg.id} message={msg} personaName={personaName} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
