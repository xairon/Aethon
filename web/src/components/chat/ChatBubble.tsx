interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  timestamp: number
}

export function ChatBubble({ message, personaName = 'Assistant' }: { message: ChatMessage; personaName?: string }) {
  const isUser = message.role === 'user'
  const time = new Date(message.timestamp).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className="max-w-[80%] rounded-2xl px-4 py-2.5"
        style={{
          background: isUser
            ? 'rgba(79, 143, 255, 0.12)'
            : 'rgba(255, 255, 255, 0.04)',
          border: `1px solid ${isUser
            ? 'rgba(79, 143, 255, 0.18)'
            : 'rgba(255, 255, 255, 0.06)'
          }`,
        }}
      >
        <div className="flex items-center gap-2 mb-1">
          {/* Role icon */}
          {isUser ? (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          ) : (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#4f8fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42" />
            </svg>
          )}
          <span className={`text-[11px] font-semibold ${isUser ? 'text-green' : 'text-accent'}`}>
            {isUser ? 'Toi' : personaName}
          </span>
          <span className="text-[10px] text-text-muted ml-auto">{time}</span>
        </div>
        <p className="text-[13px] leading-relaxed text-text">{message.text}</p>
      </div>
    </div>
  )
}
