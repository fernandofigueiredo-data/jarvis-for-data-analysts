import { create } from 'zustand'
import type {
  Agent,
  FeedItem,
  Health,
  MemoryStats,
  Phase,
  Provider,
  ServerMessage,
  Telemetry,
  TimelineEvent,
  TranscriptLine,
} from './types'

const FEED_MAX = 30
const TRANSCRIPT_MAX = 20

export interface JarvisState {
  connected: boolean
  phase: Phase
  level: number
  pttDown: boolean
  transcript: TranscriptLine[]
  feed: FeedItem[]
  health: Health
  telemetry: Telemetry
  agents: Agent[]
  timeline: TimelineEvent[]
  memory: MemoryStats
  llms: Provider[]
  focusMode: boolean
  apply: (msg: ServerMessage) => void
  setConnected: (v: boolean) => void
  setPtt: (v: boolean) => void
  toggleFocus: () => void
}

const off = (detail: string) => ({ status: 'off' as const, detail })

export const useJarvis = create<JarvisState>((set) => ({
  connected: false,
  phase: 'idle',
  level: 0,
  pttDown: false,
  transcript: [],
  feed: [],
  health: {
    core: off('—'),
    memory: off('—'),
    voice: off('—'),
    agents: off('—'),
    llms: off('—'),
    system: off('—'),
  },
  telemetry: { cpu: 0, ram: 0, disk: 0, network: '—' },
  agents: [],
  timeline: [],
  memory: { memories: 0, sessionTurns: 0, toolCalls: 0 },
  llms: [],
  focusMode: false,

  setConnected: (connected) => set({ connected }),
  setPtt: (pttDown) => set({ pttDown }),
  toggleFocus: () => set((s) => ({ focusMode: !s.focusMode })),

  apply: (msg) =>
    set((s): Partial<JarvisState> => {
      switch (msg.type) {
        case 'state':
          return { phase: msg.phase, level: clamp01(msg.level) }
        case 'transcript': {
          const line: TranscriptLine = { role: msg.role, text: msg.text, final: msg.final }
          const last = s.transcript[s.transcript.length - 1]
          // parcial do mesmo papel substitui a linha anterior em vez de empilhar
          const base = last && !last.final && last.role === msg.role ? s.transcript.slice(0, -1) : s.transcript
          return { transcript: [...base, line].slice(-TRANSCRIPT_MAX) }
        }
        case 'feed':
          return { feed: [msg.item, ...s.feed.filter((f) => f.id !== msg.item.id)].slice(0, FEED_MAX) }
        case 'health':
          return { health: { ...s.health, ...msg.components } }
        case 'telemetry': {
          const { type: _t, ...telemetry } = msg
          return { telemetry: { ...s.telemetry, ...telemetry } }
        }
        case 'agents':
          return { agents: msg.agents }
        case 'timeline':
          return { timeline: msg.events }
        case 'memory':
          return { memory: { memories: msg.memories, sessionTurns: msg.sessionTurns, toolCalls: msg.toolCalls } }
        case 'llms':
          return { llms: msg.providers }
        case 'snapshot': {
          const out: Partial<JarvisState> = {}
          if (msg.feed) out.feed = msg.feed.slice(0, FEED_MAX)
          if (msg.state) Object.assign(out, { phase: msg.state.phase, level: clamp01(msg.state.level) })
          if (msg.health) out.health = { ...s.health, ...msg.health.components }
          if (msg.telemetry) out.telemetry = { ...s.telemetry, ...msg.telemetry }
          if (msg.agents) out.agents = msg.agents.agents
          if (msg.timeline) out.timeline = msg.timeline.events
          if (msg.memory) out.memory = msg.memory
          if (msg.llms) out.llms = msg.llms.providers
          return out
        }
        default:
          return {}
      }
    }),
}))

function clamp01(n: number) {
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : 0
}
