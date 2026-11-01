import { AnimatePresence, motion } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  Bot,
  Brain,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code2,
  Cpu,
  Database,
  Globe2,
  Info,
  Lightbulb,
  ListChecks,
  Mic,
  Newspaper,
  Play,
  Radio,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  type LucideIcon,
} from 'lucide-react'
import { lazy, Suspense, useMemo, useState } from 'react'
import { useJarvis } from '../store'
import type { FeedKind, HealthKey, HealthStatus } from '../types'
import { send } from '../ws'
import { Card, Chip, Dot, formatInt, PHASE_COLOR, PHASE_LABEL, timeAgo, Waveform, type Tone } from './ui'

const Globe = lazy(() => import('./Globe'))

const statusTone: Record<HealthStatus, Tone> = { ok: 'green', warn: 'amber', off: 'red' }
const STATUS_TEXT: Record<HealthStatus, string> = { ok: 'text-cyan-300', warn: 'text-amber-300', off: 'text-rose-300' }

/* ───────────── AI CORE OVERVIEW ───────────── */

const CORE_TILES: { key: HealthKey; label: string; icon: LucideIcon; color: string }[] = [
  { key: 'core', label: 'AI Core', icon: Brain, color: '#22d3ee' },
  { key: 'memory', label: 'Memória', icon: Database, color: '#a78bfa' },
  { key: 'voice', label: 'Voz', icon: Mic, color: '#34d399' },
  { key: 'agents', label: 'Agentes', icon: Bot, color: '#fbbf24' },
  { key: 'llms', label: 'LLMs', icon: Sparkles, color: '#60a5fa' },
  { key: 'system', label: 'Sistema', icon: ShieldCheck, color: '#2dd4bf' },
]

export function CoreOverview() {
  const health = useJarvis((s) => s.health)
  return (
    <Card title="Visão geral do AI Core" bodyClassName="grid grid-cols-1 gap-1 auto-rows-fr">
      {CORE_TILES.map(({ key, label, icon: Icon, color }) => {
        const h = health[key]
        return (
          <div key={key} className="tile flex min-h-0 min-w-0 items-center gap-2 px-2" title={`${label}: ${h.detail}`}>
            <span
              className="grid h-[24px] w-[24px] shrink-0 place-items-center rounded-full"
              style={{ background: `${color}1f`, boxShadow: `inset 0 0 0 1px ${color}55, 0 0 12px -4px ${color}` }}
            >
              <Icon size={12} style={{ color }} />
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-[11px] font-medium text-cyan-50">{label}</span>
              <span className={`block truncate text-[9.5px] ${STATUS_TEXT[h.status]}`}>{h.detail}</span>
            </span>
            <Dot tone={statusTone[h.status]} />
          </div>
        )
      })}
    </Card>
  )
}

/* ───────────── GLOBO CENTRAL ───────────── */

export function CoreGlobe({ className = '' }: { className?: string }) {
  const phase = useJarvis((s) => s.phase)
  const transcript = useJarvis((s) => s.transcript)
  const last = transcript[transcript.length - 1]
  const color = PHASE_COLOR[phase]
  return (
    <section className={`glass relative min-h-[220px] min-w-0 overflow-hidden ${className}`}>
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: `radial-gradient(ellipse 45% 55% at 50% 45%, ${color}22, transparent 70%)` }}
      />
      <Suspense fallback={null}>
        <Globe />
      </Suspense>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-[6%] text-center">
        <div className="glow-text text-[30px] leading-none font-bold tracking-[0.35em]" style={{ color: '#a5f3fc' }}>
          JARVIS
        </div>
        <div className="mt-1.5 text-[10px] font-semibold tracking-[0.4em]" style={{ color }}>
          AI CORE
        </div>
        <div className="mt-1 font-mono text-[9.5px] text-slate-400">v0.1.0</div>
      </div>
      <div className="pointer-events-none absolute top-2 left-2">
        <Chip tone={phase === 'thinking' ? 'violet' : phase === 'tooling' ? 'amber' : 'cyan'}>
          <Dot tone={phase === 'thinking' ? 'violet' : phase === 'tooling' ? 'amber' : 'cyan'} pulse={phase !== 'idle'} />
          {PHASE_LABEL[phase].replace('…', '')}
        </Chip>
      </div>
      <AnimatePresence>
        {last && phase !== 'idle' && (
          <motion.div
            key={last.role}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute right-6 bottom-1.5 left-6 truncate text-center text-[11px]"
          >
            <span className={last.role === 'user' ? 'text-slate-300' : 'text-cyan-200'}>
              {last.role === 'user' ? 'Você: ' : 'Jarvis: '}
              {last.text}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

/* ───────────── LIVE INTELLIGENCE FEED ───────────── */

const FEED_META: Record<FeedKind, { icon: LucideIcon; tone: Tone; tag: string; color: string }> = {
  info: { icon: Info, tone: 'cyan', tag: 'Info', color: '#22d3ee' },
  warn: { icon: AlertTriangle, tone: 'amber', tag: 'Alerta', color: '#fbbf24' },
  tip: { icon: Lightbulb, tone: 'violet', tag: 'Dica', color: '#a78bfa' },
  live: { icon: Radio, tone: 'red', tag: 'Ao vivo', color: '#f87171' },
  news: { icon: Newspaper, tone: 'green', tag: 'Notícia', color: '#34d399' },
}

export function IntelFeed() {
  const feed = useJarvis((s) => s.feed)
  const [all, setAll] = useState(false)
  const items = all ? feed : feed.slice(0, 5)
  return (
    <Card
      title="Feed de inteligência"
      right={
        <Chip tone="red">
          <Dot tone="red" pulse /> Ao vivo
        </Chip>
      }
      bodyClassName="flex flex-col"
    >
      <ul className="scroll-thin -mr-1 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {items.map((it) => {
            const m = FEED_META[it.kind] ?? FEED_META.info
            const Icon = m.icon
            return (
              <motion.li
                key={it.id}
                layout
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                onClick={() => it.url && window.open(it.url, '_blank', 'noopener')}
                className={`flex min-w-0 items-center gap-2 rounded-md border-b border-cyan-400/[0.07] px-1 py-[5px] ${it.url ? 'cursor-pointer hover:bg-cyan-400/5' : ''}`}
              >
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md" style={{ background: `${m.color}1a` }}>
                  <Icon size={12} style={{ color: m.color }} />
                </span>
                <div className="min-w-0 flex-1 leading-tight">
                  <div className="truncate text-[11.5px] text-cyan-50">{it.title}</div>
                  <div className="truncate text-[9.5px] text-slate-500">
                    {it.subtitle ? `${it.subtitle} · ` : ''}
                    {timeAgo(it.ts)}
                  </div>
                </div>
                <Chip tone={m.tone}>{m.tag}</Chip>
              </motion.li>
            )
          })}
        </AnimatePresence>
        {feed.length === 0 && <li className="py-4 text-center text-[11px] text-slate-500">Sem eventos ainda</li>}
      </ul>
      <button
        onClick={() => setAll((v) => !v)}
        className="mt-1.5 flex shrink-0 items-center gap-0.5 self-start text-[10.5px] text-cyan-300 hover:text-cyan-100"
      >
        {all ? 'Mostrar menos' : 'Ver toda a inteligência'} <ChevronRight size={12} />
      </button>
    </Card>
  )
}

/* ───────────── ACTIVE AGENTS ───────────── */

function agentIcon(id: string): LucideIcon {
  const k = id.toLowerCase()
  if (k.includes('cod')) return Code2
  if (k.includes('research') || k.includes('pesq')) return Search
  if (k.includes('mem')) return Database
  if (k.includes('brows') || k.includes('naveg')) return Globe2
  if (k.includes('task') || k.includes('taref')) return ListChecks
  if (k.includes('sys') || k.includes('sist')) return Server
  return Bot
}

// "Agente de Pesquisa" → "Pesquisa": o tile é estreito e o título do cartão já diz "agentes"
const shortAgentName = (name: string) => name.replace(/^(agente|agent)\s+(de\s+|do\s+|da\s+)?/i, '').replace(/\s+agent$/i, '')

export function ActiveAgents() {
  const agents = useJarvis((s) => s.agents)
  const active = agents.filter((a) => a.status === 'active').length
  return (
    <Card
      title="Agentes ativos"
      right={<span className="text-[10px] text-slate-400">{active} em execução</span>}
      bodyClassName="grid grid-cols-3 gap-1.5 auto-rows-fr"
    >
      {agents.slice(0, 6).map((a) => {
        const Icon = agentIcon(a.id)
        const on = a.status === 'active'
        return (
          <div
            key={a.id}
            className={`tile flex min-w-0 flex-col justify-between gap-1 px-2 py-1.5 ${on ? 'border-emerald-400/25 shadow-[0_0_14px_-8px_#34d399]' : ''}`}
          >
            <div className="flex items-center gap-1.5">
              <Icon size={13} className={on ? 'text-emerald-300' : 'text-slate-500'} />
              <span className="truncate text-[11px] font-medium text-cyan-50" title={a.name}>
                {shortAgentName(a.name)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-1">
              <span className={`text-[9px] font-semibold tracking-wider uppercase ${on ? 'text-emerald-300' : 'text-slate-500'}`}>
                {on ? 'Ativo' : 'Em espera'}
              </span>
              <Waveform bars={7} active={on} height={12} barWidth={2} gap={1.5} color={on ? '#34d399' : '#475569'} />
            </div>
          </div>
        )
      })}
    </Card>
  )
}

/* ───────────── MISSION TIMELINE ───────────── */

const isDone = (s: string) => /conclu|done|feito|ok/i.test(s)

export function MissionTimeline() {
  const events = useJarvis((s) => s.timeline)
  const doneCount = events.filter((e) => isDone(e.status)).length
  const pct = events.length ? (doneCount / events.length) * 100 : 0
  return (
    <Card
      title="Linha do tempo da missão"
      right={<span className="text-[10px] text-slate-400">{doneCount}/{events.length}</span>}
      bodyClassName="flex flex-col"
    >
      <div className="mb-2 h-[3px] shrink-0 overflow-hidden rounded-full bg-slate-700/40">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-emerald-400 shadow-[0_0_8px_#22d3ee] transition-[width] duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <ol className="scroll-thin relative flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
        {events.map((e, i) => {
          const done = isDone(e.status)
          return (
            <li key={`${e.time}-${i}`} className="relative flex items-center gap-2 py-[3px] pl-0.5">
              <span className="w-9 shrink-0 font-mono text-[10.5px] text-cyan-300/90">{e.time}</span>
              <span className="relative flex h-full flex-col items-center">
                <span className={`h-2 w-2 rounded-full ${done ? 'bg-emerald-400 shadow-[0_0_6px_#34d399]' : 'border border-amber-300/70 bg-amber-400/20'}`} />
              </span>
              <span className={`min-w-0 flex-1 truncate text-[11.5px] ${done ? 'text-slate-400' : 'text-cyan-50'}`}>{e.title}</span>
              <span className={`flex shrink-0 items-center gap-1 text-[10px] ${done ? 'text-emerald-300' : 'text-amber-300'}`}>
                {done ? <CheckCircle2 size={11} /> : <Clock3 size={11} />}
                {e.status}
              </span>
            </li>
          )
        })}
        {events.length === 0 && <li className="py-4 text-center text-[11px] text-slate-500">Nada agendado</li>}
      </ol>
    </Card>
  )
}

/* ───────────── QUICK COMMANDS ───────────── */

// ids aceitos pelo daemon: briefing (rodapé), news, agenda, new_task, voice
const COMMANDS: { id: string; label: string; icon: LucideIcon; color: string }[] = [
  { id: 'new_task', label: 'Iniciar tarefa', icon: Play, color: '#22d3ee' },
  { id: 'agenda', label: 'Abrir calendário', icon: CalendarDays, color: '#a78bfa' },
  { id: 'voice', label: 'Iniciar conversa por voz', icon: Mic, color: '#34d399' },
  { id: 'news', label: 'Resumo de notícias', icon: Newspaper, color: '#fbbf24' },
]

export function QuickCommands() {
  return (
    <Card title="Comandos rápidos" bodyClassName="grid grid-cols-1 gap-1.5 auto-rows-fr">
      {COMMANDS.map(({ id, label, icon: Icon, color }) => (
        <motion.button
          key={id}
          whileTap={{ scale: 0.97 }}
          onClick={() => send({ type: 'command', id })}
          className="tile group flex min-w-0 items-center gap-2 px-2.5 text-left transition-colors hover:border-cyan-400/40 hover:bg-cyan-400/5"
        >
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md" style={{ background: `${color}1f` }}>
            <Icon size={12} style={{ color }} />
          </span>
          <span className="flex-1 truncate text-[11.5px] text-cyan-50">{label}</span>
          <ChevronRight size={13} className="text-slate-500 group-hover:text-cyan-300" />
        </motion.button>
      ))}
    </Card>
  )
}

/* ───────────── SYSTEM MONITOR ───────────── */

function Ring({ label, value, color, icon: Icon }: { label: string; value: number; color: string; icon: LucideIcon }) {
  const r = 26
  const c = 2 * Math.PI * r
  const v = Math.min(100, Math.max(0, value))
  return (
    <div className="flex min-w-0 flex-col items-center gap-1">
      <div className="relative">
        <svg width="66" height="66" viewBox="0 0 66 66" className="-rotate-90">
          <circle cx="33" cy="33" r={r} fill="none" stroke="rgba(148,163,184,0.12)" strokeWidth="5" />
          <circle cx="33" cy="33" r={r + 5} fill="none" stroke={color} strokeOpacity="0.15" strokeWidth="1" strokeDasharray="2 4" />
          <circle
            cx="33"
            cy="33"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - v / 100)}
            style={{ filter: `drop-shadow(0 0 4px ${color})`, transition: 'stroke-dashoffset 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span className="font-mono text-[13px] font-semibold text-cyan-50 tabular-nums">{Math.round(v)}%</span>
        </div>
      </div>
      <div className="flex items-center gap-1 text-[9.5px] font-semibold tracking-[0.14em] text-slate-400 uppercase">
        <Icon size={10} style={{ color }} />
        {label}
      </div>
    </div>
  )
}

export function SystemMonitor() {
  const t = useJarvis((s) => s.telemetry)
  return (
    <Card title="Monitor do sistema" right={<Activity size={13} className="text-cyan-400/70" />} bodyClassName="flex items-center justify-around">
      <Ring label="CPU" value={t.cpu} color="#22d3ee" icon={Cpu} />
      <Ring label="RAM" value={t.ram} color="#a78bfa" icon={Server} />
      <Ring label="Disco" value={t.disk} color="#fbbf24" icon={Database} />
    </Card>
  )
}

/* ───────────── MEMORY INSIGHTS ───────────── */

function Constellation() {
  const { nodes, edges } = useMemo(() => {
    let seed = 11
    const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646
    const nodes = Array.from({ length: 16 }, (_, i) => ({
      x: 8 + rand() * 104,
      y: 8 + rand() * 64,
      r: i % 5 === 0 ? 2.6 : 1.4 + rand(),
      c: ['#22d3ee', '#a78bfa', '#67e8f9', '#34d399'][i % 4],
    }))
    const edges: [number, number][] = []
    nodes.forEach((a, i) => {
      const near = nodes
        .map((b, j) => ({ j, d: (a.x - b.x) ** 2 + (a.y - b.y) ** 2 }))
        .filter((o) => o.j !== i)
        .sort((p, q) => p.d - q.d)
        .slice(0, 2)
      near.forEach(({ j }) => i < j && edges.push([i, j]))
    })
    return { nodes, edges }
  }, [])
  return (
    <svg viewBox="0 0 120 80" className="h-full max-h-[96px] w-full" preserveAspectRatio="xMidYMid meet">
      {edges.map(([i, j], k) => (
        <line key={k} x1={nodes[i].x} y1={nodes[i].y} x2={nodes[j].x} y2={nodes[j].y} stroke="#22d3ee" strokeOpacity="0.28" strokeWidth="0.6" />
      ))}
      {nodes.map((n, i) => (
        <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.c} style={{ filter: `drop-shadow(0 0 2px ${n.c})` }}>
          <animate attributeName="opacity" values="1;0.35;1" dur={`${2 + (i % 5) * 0.7}s`} repeatCount="indefinite" />
        </circle>
      ))}
    </svg>
  )
}

export function MemoryInsights() {
  const m = useJarvis((s) => s.memory)
  const rows: [string, number, string][] = [
    ['Memórias', m.memories, '#a78bfa'],
    ['Turnos de sessão', m.sessionTurns, '#22d3ee'],
    ['Chamadas de ferramenta', m.toolCalls, '#34d399'],
  ]
  return (
    <Card title="Insights de memória" bodyClassName="grid grid-cols-[1fr_1.1fr] items-center gap-2">
      <div className="flex h-full min-h-0 items-center">
        <Constellation />
      </div>
      <div className="flex min-w-0 flex-col gap-1.5">
        {rows.map(([label, value, color]) => (
          <div key={label} className="min-w-0 leading-tight">
            <div className="font-mono text-[15px] font-semibold tabular-nums" style={{ color, textShadow: `0 0 10px ${color}66` }}>
              {formatInt(value)}
            </div>
            <div className="truncate text-[9.5px] tracking-wide text-slate-400">{label}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}

/* ───────────── LLM STATUS ───────────── */

export function LlmStatus() {
  const providers = useJarvis((s) => s.llms)
  const n = providers.filter((p) => p.status === 'connected').length
  return (
    <Card
      title="Status dos LLMs"
      right={
        <span className="text-[10px] text-emerald-300">
          {n} {n === 1 ? 'conectado' : 'conectados'}
        </span>
      }
      bodyClassName="grid grid-cols-3 gap-1 auto-rows-fr"
    >
      {providers.slice(0, 9).map((p) => {
        const on = p.status === 'connected'
        return (
          <div key={p.name} className={`tile flex min-h-0 min-w-0 flex-col justify-center px-1.5 py-0 leading-tight ${on ? '' : 'opacity-70'}`}>
            <div className="truncate text-[10.5px] font-medium text-cyan-50">{p.name}</div>
            <div className={`flex items-center gap-1 text-[9px] ${on ? 'text-emerald-300' : 'text-slate-500'}`}>
              <Dot tone={on ? 'green' : 'gray'} />
              <span className="truncate">{on ? 'Conectado' : 'Não vinculado'}</span>
            </div>
          </div>
        )
      })}
    </Card>
  )
}
