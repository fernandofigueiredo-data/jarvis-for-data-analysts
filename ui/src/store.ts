import { create } from 'zustand'
import type {
  Agent,
  DataState,
  KpiItem,
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
const TRANSCRIPT_MAX = 40

/** Destinos da navegação lateral: 'top' é o Command Center inteiro; os outros são ids de cartões. */
export type Section = 'top' | 'ai-core' | 'agentes' | 'calendario' | 'memoria' | 'conversa' | 'noticias' | 'dados'

export interface JarvisState {
  connected: boolean
  phase: Phase
  level: number
  pttDown: boolean
  transcript: TranscriptLine[]
  history: TranscriptLine[] // conversas anteriores, do SQLite do daemon
  feed: FeedItem[]
  health: Health
  telemetry: Telemetry
  agents: Agent[]
  timeline: TimelineEvent[]
  timelineReady: boolean // a 1ª leitura do Calendário já chegou (vazia ou não)
  memory: MemoryStats
  llms: Provider[]
  data: DataState | null // arquivo aberto e últimos agregados
  dataOpen: boolean
  kpis: KpiItem[]
  uploadStatus: string | null
  focusMode: boolean
  chatOpen: boolean
  section: Section
  alertsSeen: number // ms do último clique no sino
  apply: (msg: ServerMessage) => void
  reset: () => void
  setConnected: (v: boolean) => void
  setPtt: (v: boolean) => void
  setHistory: (h: TranscriptLine[]) => void
  setChatOpen: (v: boolean) => void
  setDataOpen: (v: boolean) => void
  setUploadStatus: (v: string | null) => void
  setSection: (s: Section) => void
  markAlertsSeen: () => void
  toggleFocus: () => void
}

const off = (detail: string) => ({ status: 'off' as const, detail })

// Estado sem dados: o de partida e o que fica ao conectar, para nada da demonstração passar por dado real
const blank = () => ({
  phase: 'idle' as Phase,
  level: 0,
  transcript: [],
  history: [],
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
  timelineReady: false,
  memory: { memories: 0, sessionTurns: 0, toolCalls: 0 },
  llms: [],
  data: null,
  kpis: [],
})

export const useJarvis = create<JarvisState>((set) => ({
  connected: false,
  pttDown: false,
  focusMode: false,
  chatOpen: false,
  dataOpen: false,
  uploadStatus: null,
  section: 'top',
  alertsSeen: 0,
  ...blank(),

  reset: () => set(blank()),
  setConnected: (connected) => set({ connected }),
  setPtt: (pttDown) => set({ pttDown }),
  setHistory: (history) => set({ history }),
  setChatOpen: (chatOpen) => set({ chatOpen }),
  setDataOpen: (dataOpen) => set({ dataOpen }),
  setUploadStatus: (uploadStatus) => set({ uploadStatus }),
  setSection: (section) => set({ section }),
  markAlertsSeen: () => set({ alertsSeen: Date.now() }),
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
          // uma pergunta nova (de verdade, não da demonstração) abre a conversa; os pedaços da resposta não a
          // reabrem, para dar para fechá-la enquanto ele fala
          const opens = s.connected && msg.role === 'user'
          return { transcript: [...base, line].slice(-TRANSCRIPT_MAX), chatOpen: s.chatOpen || opens }
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
          return { timeline: msg.events, timelineReady: true }
        case 'memory':
          return { memory: { memories: msg.memories, sessionTurns: msg.sessionTurns, toolCalls: msg.toolCalls } }
        case 'llms':
          return { llms: msg.providers }
        case 'kpis':
          return { kpis: msg.itens }
        case 'data': {
          const { type: _t, ...data } = msg
          // arquivo novo, resultado novo ou gráfico novo (Python isolado) abre o painel; o mesmo estado repetido não o reabre
          const novo =
            data.arquivo !== s.data?.arquivo || data.resultados.length !== s.data?.resultados.length ||
            JSON.stringify(data.resultados[0]) !== JSON.stringify(s.data?.resultados[0]) ||
            data.graficos?.[0]?.url !== s.data?.graficos?.[0]?.url
          return { data, dataOpen: s.dataOpen || (s.connected && novo), uploadStatus: null }
        }
        case 'snapshot': {
          const out: Partial<JarvisState> = {}
          if (msg.feed) out.feed = msg.feed.slice(0, FEED_MAX)
          if (msg.state) Object.assign(out, { phase: msg.state.phase, level: clamp01(msg.state.level) })
          if (msg.health) out.health = { ...s.health, ...msg.health.components }
          if (msg.telemetry) out.telemetry = { ...s.telemetry, ...msg.telemetry }
          if (msg.agents) out.agents = msg.agents.agents
          if (msg.timeline) Object.assign(out, { timeline: msg.timeline.events, timelineReady: true })
          if (msg.memory) out.memory = msg.memory
          if (msg.llms) out.llms = msg.llms.providers
          if (msg.data) out.data = msg.data
          if (msg.kpis) out.kpis = msg.kpis.itens
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
