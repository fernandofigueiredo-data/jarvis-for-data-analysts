// Contrato WebSocket entre o daemon (src/jarvis) e o painel.

export type Phase = 'idle' | 'listening' | 'thinking' | 'tooling' | 'speaking'
export type Role = 'user' | 'assistant'
export type FeedKind = 'info' | 'warn' | 'tip' | 'live' | 'news'
export type HealthStatus = 'ok' | 'warn' | 'off'
export type HealthKey = 'core' | 'memory' | 'voice' | 'agents' | 'llms' | 'system'

export interface FeedItem {
  id: string
  title: string
  subtitle?: string
  kind: FeedKind
  ts: number // segundos ou ms desde epoch (o daemon manda segundos)
  url?: string
}

export interface TranscriptLine {
  role: Role
  text: string
  final: boolean
}

export type Health = Record<HealthKey, { status: HealthStatus; detail: string }>

export interface Telemetry {
  cpu: number
  ram: number
  disk: number
  network: string
  weather?: { tempC: number; desc: string }
  location?: string
}

export interface Agent {
  id: string
  name: string
  status: 'active' | 'standby'
}

export interface TimelineEvent {
  time: string
  title: string
  status: string
}

export interface MemoryStats {
  memories: number
  sessionTurns: number
  toolCalls: number
}

export interface Provider {
  name: string
  status: 'connected' | 'not_linked'
}

export interface DataColumn {
  coluna: string
  tipo: string
  nulos_pct: number
  dado_pessoal?: boolean
}

/** Um resultado de `agregar`: o mesmo que o Claude viu (grupos com menos de k linhas já omitidos). */
export interface DataResult {
  pedido: { metricas?: { funcao: string; coluna?: string }[]; por?: string[]; filtros?: unknown[] }
  colunas: string[]
  linhas: (string | number | null)[][]
  grupos_omitidos_por_terem_menos_de_k_linhas: number
  k: number
  total_de_grupos: number
}

export interface DataState {
  arquivo: string | null
  linhas: number | null
  total_colunas: number | null
  codificacao?: string
  separador?: string
  colunas: DataColumn[]
  alertas: string[]
  resultados: DataResult[] // mais recente primeiro
  graficos?: { url: string; titulo: string | null }[] // do Python isolado; só no painel, não vão para o Claude
}

export type StateMsg = { type: 'state'; phase: Phase; level: number }
export type TranscriptMsg = { type: 'transcript' } & TranscriptLine
export type FeedMsg = { type: 'feed'; item: FeedItem }
export type HealthMsg = { type: 'health'; components: Health }
export type TelemetryMsg = { type: 'telemetry' } & Telemetry
export type AgentsMsg = { type: 'agents'; agents: Agent[] }
export type TimelineMsg = { type: 'timeline'; events: TimelineEvent[] }
export type MemoryMsg = { type: 'memory' } & MemoryStats
export type LlmsMsg = { type: 'llms'; providers: Provider[] }
export type DataMsg = { type: 'data' } & DataState

/** Monitor de KPI: o daemon confere sozinho e fala quando a regra dispara. */
export interface KpiItem {
  nome: string
  arquivo: string
  ultimo: { texto: string; disparou: boolean; valor: number | null; periodo?: string; conferido?: number } | null
}
export type KpisMsg = { type: 'kpis'; itens: KpiItem[] }

type Body<T> = Omit<T, 'type'>

// Snapshot como o daemon monta (events.Bus.snapshot): cada tipo aninhado sem o campo "type",
// e o feed como lista (mais recente primeiro).
export type SnapshotMsg = {
  type: 'snapshot'
  feed?: FeedItem[]
  state?: Body<StateMsg>
  health?: Body<HealthMsg>
  telemetry?: Body<TelemetryMsg>
  agents?: Body<AgentsMsg>
  timeline?: Body<TimelineMsg>
  memory?: Body<MemoryMsg>
  llms?: Body<LlmsMsg>
  data?: Body<DataMsg>
  kpis?: Body<KpisMsg>
}

export type ServerMessage =
  | StateMsg
  | TranscriptMsg
  | FeedMsg
  | HealthMsg
  | TelemetryMsg
  | AgentsMsg
  | TimelineMsg
  | MemoryMsg
  | LlmsMsg
  | DataMsg
  | KpisMsg
  | SnapshotMsg

export type ClientMessage =
  | { type: 'ptt'; down: boolean }
  | { type: 'say'; text: string }
  | { type: 'command'; id: string }
