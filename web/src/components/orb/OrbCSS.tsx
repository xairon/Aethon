import { usePipeline } from '../../stores/usePipeline'
import { stateColors } from '../../lib/theme'

/** CSS-only orb fallback — works in headless browsers and without WebGL */
export function OrbCSS() {
  const state = usePipeline((s) => s.state)
  const audioLevel = usePipeline((s) => s.audioLevel)
  const color = stateColors[state] || stateColors.idle

  const scale = 1 + audioLevel * 0.15
  const glowSize = 120 + audioLevel * 80
  const isIdle = state === 'idle' || state === 'stopped'

  return (
    <div className="fixed inset-0 flex items-center justify-center" style={{ zIndex: 0 }}>
      {/* Ambient background glow */}
      <div
        className="absolute rounded-full transition-all duration-700"
        style={{
          width: `${glowSize * 3}px`,
          height: `${glowSize * 3}px`,
          background: `radial-gradient(circle, ${color}15 0%, ${color}08 40%, transparent 70%)`,
        }}
      />

      {/* Outer glow ring */}
      <div
        className="absolute rounded-full transition-all duration-500"
        style={{
          width: `${glowSize * 1.8}px`,
          height: `${glowSize * 1.8}px`,
          background: `radial-gradient(circle, ${color}20 0%, ${color}10 50%, transparent 70%)`,
          filter: `blur(20px)`,
        }}
      />

      {/* Main orb */}
      <div
        className="relative rounded-full transition-all duration-300"
        style={{
          width: '200px',
          height: '200px',
          transform: `scale(${scale})`,
          background: `radial-gradient(circle at 35% 35%, ${color}cc, ${color}66 50%, ${color}22 80%, transparent)`,
          boxShadow: `
            0 0 60px ${color}40,
            0 0 120px ${color}20,
            inset 0 0 60px ${color}30,
            inset -20px -20px 40px ${color}10
          `,
          animation: isIdle ? 'breathe 4s ease-in-out infinite' : 'none',
        }}
      >
        {/* Inner highlight / specular */}
        <div
          className="absolute rounded-full"
          style={{
            top: '15%',
            left: '20%',
            width: '35%',
            height: '35%',
            background: `radial-gradient(circle, rgba(255,255,255,0.25), transparent)`,
            filter: 'blur(8px)',
          }}
        />

        {/* Surface sheen */}
        <div
          className="absolute inset-0 rounded-full"
          style={{
            background: `linear-gradient(135deg, rgba(255,255,255,0.08) 0%, transparent 50%)`,
          }}
        />
      </div>

      {/* State-specific effects */}
      {state === 'listening' && (
        <div
          className="absolute rounded-full animate-ping"
          style={{
            width: '220px',
            height: '220px',
            border: `2px solid ${color}40`,
            animationDuration: '1.5s',
          }}
        />
      )}

      {state === 'thinking' && (
        <>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="absolute"
              style={{
                left: '50%',
                top: '50%',
                marginLeft: '-4px',
                marginTop: '-4px',
                animation: `orbit 2s linear infinite`,
                animationDelay: `${i * 0.66}s`,
              }}
            >
              <div
                className="rounded-full"
                style={{
                  width: '8px',
                  height: '8px',
                  backgroundColor: color,
                  boxShadow: `0 0 12px ${color}`,
                }}
              />
            </div>
          ))}
        </>
      )}

      {state === 'speaking' && (
        <div className="absolute flex items-center gap-[3px]" style={{ bottom: 'calc(50% - 130px)' }}>
          {Array.from({ length: 16 }).map((_, i) => (
            <div
              key={i}
              className="rounded-full orb-waveform-bar"
              style={{
                width: '3px',
                height: `${8 + audioLevel * 30}px`,
                backgroundColor: color,
                opacity: 0.6 + audioLevel * 0.4,
                boxShadow: `0 0 4px ${color}60`,
                animationDelay: `${i * 0.08}s`,
              }}
            />
          ))}
        </div>
      )}

      <style>{`
        @keyframes breathe {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.04); }
        }
        @keyframes orbit {
          0% { transform: rotate(0deg) translateX(120px) rotate(0deg); }
          100% { transform: rotate(360deg) translateX(120px) rotate(-360deg); }
        }
        @keyframes waveform {
          0%, 100% { transform: scaleY(0.4); }
          50% { transform: scaleY(1); }
        }
        .orb-waveform-bar {
          animation: waveform 0.6s ease-in-out infinite;
          transform-origin: center bottom;
        }
      `}</style>
    </div>
  )
}
