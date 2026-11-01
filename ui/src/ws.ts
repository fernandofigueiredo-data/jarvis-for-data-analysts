// Conexão com o daemon. Sem conexão, o mock assume para o painel nunca ficar parado.
import { mockHandle, startMock, stopMock } from './mock'
import { useJarvis } from './store'
import type { ClientMessage, ServerMessage } from './types'

const DEFAULT_URL = 'ws://127.0.0.1:8787/ws'

function resolveUrl(): string {
  const q = new URLSearchParams(location.search).get('ws')
  if (q) return q
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL as string
  // servido pelo próprio daemon → mesma origem
  if (location.port === '8787') return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
  return DEFAULT_URL
}

const url = resolveUrl()
let socket: WebSocket | null = null
let attempt = 0
let retryTimer: ReturnType<typeof setTimeout> | undefined
let started = false

function open() {
  clearTimeout(retryTimer)
  let ws: WebSocket
  try {
    ws = new WebSocket(url)
  } catch {
    return scheduleRetry()
  }
  socket = ws

  ws.onopen = () => {
    attempt = 0
    stopMock()
    useJarvis.getState().setConnected(true)
  }
  ws.onmessage = (ev) => {
    if (typeof ev.data !== 'string') return
    try {
      const msg = JSON.parse(ev.data) as ServerMessage
      if (msg && typeof msg.type === 'string') useJarvis.getState().apply(msg)
    } catch {
      // mensagem malformada: ignora
    }
  }
  ws.onerror = () => ws.close()
  ws.onclose = () => {
    if (socket !== ws) return
    socket = null
    if (useJarvis.getState().connected) useJarvis.getState().setConnected(false)
    startMock()
    scheduleRetry()
  }
}

function scheduleRetry() {
  // 1s, 2s, 4s… até 10s
  const delay = Math.min(10_000, 1000 * 2 ** Math.min(attempt++, 4))
  retryTimer = setTimeout(open, delay)
}

export function startConnection() {
  if (started) return
  started = true
  startMock()
  open()
}

export function send(msg: ClientMessage) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg))
  else mockHandle(msg)
}

export const wsUrl = url
