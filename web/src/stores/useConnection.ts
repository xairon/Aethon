import { create } from 'zustand'
import { usePipeline } from './usePipeline'
import type { ServerMessage } from '../types/messages'

interface ConnectionStore {
  ws: WebSocket | null
  connected: boolean
  reconnectTimer: ReturnType<typeof setTimeout> | null
  intentionalClose: boolean

  connect: () => void
  disconnect: () => void
  send: (msg: Record<string, unknown>) => void
  startPipeline: () => void
  stopPipeline: () => void
  sendText: (text: string) => void
}

/** Backend WebSocket URL — always direct to FastAPI (port 8765).
 *  In production the frontend is served by the same FastAPI, so we use
 *  window.location.host. In dev (Vite on 5173), we connect directly
 *  to the backend to bypass the broken Vite WS proxy. */
function getWsUrl(): string {
  // If we're on the FastAPI host (port 8765), use relative URL
  if (window.location.port === '8765') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/ws`
  }
  // Otherwise (Vite dev on 5173, or any other port), connect directly
  return 'ws://127.0.0.1:8765/ws'
}

export const useConnection = create<ConnectionStore>((set, get) => ({
  ws: null,
  connected: false,
  reconnectTimer: null,
  intentionalClose: false,

  connect: () => {
    const existing = get().ws
    // Only skip if an existing socket is actively CONNECTING or OPEN.
    // CLOSING/CLOSED sockets are stale (e.g. React StrictMode cleanup) — proceed.
    if (existing && existing.readyState <= WebSocket.OPEN) {
      console.log('[WS] connect() skipped — existing socket readyState:', existing.readyState)
      return
    }

    set({ intentionalClose: false })

    const wsUrl = getWsUrl()
    console.log('[WS] Connecting to', wsUrl, '...')
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[WS] Connected! readyState:', ws.readyState)
      set({ connected: true })
      usePipeline.getState().setConnected(true)
      const timer = get().reconnectTimer
      if (timer) clearTimeout(timer)
      set({ reconnectTimer: null })
    }

    ws.onmessage = (event) => {
      let msg: ServerMessage
      try {
        msg = JSON.parse(event.data)
      } catch {
        console.error('[WS] Malformed message:', event.data)
        return
      }

      const pipeline = usePipeline.getState()

      switch (msg.type) {
        case 'state':
          console.log('[WS] State:', msg.state)
          pipeline.setState(msg.state as Parameters<typeof pipeline.setState>[0])
          break
        case 'transcript':
          pipeline.addMessage('user', msg.text)
          break
        case 'response':
          pipeline.addMessage('assistant', msg.text)
          break
        case 'audio_level':
          pipeline.setAudioLevel(msg.level)
          break
        case 'error':
          console.error('[WS Error]', msg.message)
          pipeline.addToast(msg.message, 'error')
          break
        case 'toast':
          console.log('[WS] Toast:', msg.message)
          pipeline.addToast(msg.message, msg.level)
          break
        case 'hf_progress':
          pipeline.setHfProgress({ current: msg.current, total: msg.total, name: msg.name })
          if (msg.current >= msg.total) {
            setTimeout(() => pipeline.setHfProgress(null), 1500)
          }
          break
        default:
          console.warn('[WS] Unhandled message type:', (msg as { type: string }).type)
      }
    }

    ws.onclose = () => {
      // Ignore stale close events from a previous socket (React StrictMode
      // unmounts and remounts — the old socket's onclose must not clobber
      // the new socket's state).
      if (get().ws !== ws) {
        console.log('[WS] Stale onclose ignored (old socket)')
        return
      }

      console.log('[WS] Connection closed. intentionalClose:', get().intentionalClose)
      set({ connected: false, ws: null })
      usePipeline.getState().setConnected(false)
      usePipeline.getState().setAudioLevel(0)

      if (get().intentionalClose) {
        set({ intentionalClose: false })
        return
      }

      console.log('[WS] Will reconnect in 2s...')
      const timer = setTimeout(() => get().connect(), 2000)
      set({ reconnectTimer: timer })
    }

    ws.onerror = (e) => {
      console.error('[WS] Error event:', e)
      // onclose will fire after onerror, reconnect handled there
    }

    set({ ws })
  },

  disconnect: () => {
    const { ws, reconnectTimer } = get()
    if (reconnectTimer) clearTimeout(reconnectTimer)
    set({ intentionalClose: true, reconnectTimer: null })
    if (ws) {
      ws.close()
      // Don't null ws/connected here — let onclose handle cleanup
      // to avoid a race where connect() is called before onclose fires
    }
  },

  send: (msg) => {
    const ws = get().ws
    if (ws && ws.readyState === WebSocket.OPEN) {
      console.log('[WS] Sending:', msg)
      ws.send(JSON.stringify(msg))
    } else {
      console.warn('[WS] Message dropped — ws:', ws ? `readyState=${ws.readyState}` : 'null', 'msg:', msg)
    }
  },

  startPipeline: () => {
    console.log('[WS] startPipeline() called, connected:', get().connected)
    get().send({ type: 'command', action: 'start' })
  },
  stopPipeline: () => {
    console.log('[WS] stopPipeline() called, connected:', get().connected)
    get().send({ type: 'command', action: 'stop' })
  },
  sendText: (text: string) => {
    get().send({ type: 'text_input', text })
  },
}))
