import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
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
import type { FeedKind, HealthKey, HealthStatus, Phase } from '../types'
import { send } from '../ws'
import { alpha, C, Card, Chip, Dot, formatInt, PHASE_COLOR, PHASE_LABEL, timeAgo, Waveform, type Tone } from './ui'

const Globe = lazy(() => import('./Globe'))

// sem vermelho no sistema: desligado também é "precisa da sua atenção" (§7)
const statusTone: Record<HealthStatus, Tone> = { ok: 'green', warn: 'amber', off: 'amber' }
const STATUS_TEXT: Record<HealthStatus, string> = { ok: 'text-success', warn: 'text-warning', off: 'text-warning' }

/* ───────────── AI CORE OVERVIEW ───────────── */

// os ícones ficam neutros: quem tem cor é o estado (verde ok, âmbar atenção), não a categoria
const CORE_TILES: { key: HealthKey; label: string; icon: LucideIcon }[] = [
  { key: 'core', label: 'AI Core', icon: Brain },
  { key: 'memory', label: 'Memória', icon: Database },
  { key: 'voice', label: 'Voz', icon: Mic },
  { key: 'agents', label: 'Agentes', icon: Bot },
  { key: 'llms', label: 'LLMs', icon: Sparkles },
  { key: 'system', label: 'Sistema', icon: ShieldCheck },
]

export function CoreOverview() {
  const health = useJarvis((s) => s.health)
  return (
    <Card id="ai-core" title="Visão geral do AI Core" bodyClassName="grid grid-cols-1 gap-1 auto-rows-fr">
      {CORE_TILES.map(({ key, label, icon: Icon }) => {
        const h = health[key]
        return (
          <div key={key} className="tile flex min-h-0 min-w-0 items-center gap-2 px-2" title={`${label}: ${h.detail}`}>
            <Icon size={14} className="shrink-0 text-text-secondary" />
            {/* nome à esquerda, estado à direita: uma linha por item cabe na altura da janela nativa */}
            <span className="min-w-0 shrink-0 truncate text-xs leading-tight font-medium text-text-primary">{label}</span>
            <span className={`min-w-0 flex-1 truncate text-right text-xs leading-tight ${STATUS_TEXT[h.status]}`}>{h.detail}</span>
            <Dot tone={statusTone[h.status]} />
          </div>
        )
      })}
    </Card>
  )
}

/* ───────────── GLOBO CENTRAL ───────────── */

const PHASE_TONE: Record<Phase, Tone> = { idle: 'gray', listening: 'cyan', thinking: 'violet', tooling: 'green', speaking: 'violet' }

export function CoreGlobe({ className = '' }: { className?: string }) {
  const phase = useJarvis((s) => s.phase)
  const transcript = useJarvis((s) => s.transcript)
  const last = transcript[transcript.length - 1]
  const color = PHASE_COLOR[phase]
  return (
    // §8: o globo é o único elemento com brilho na tela (a atmosfera dele, no WebGL); o resto é plano
    <section className={`card relative min-h-[220px] min-w-0 overflow-hidden ${className}`}>
      <Suspense fallback={null}>
        <Globe />
      </Suspense>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-[6%] text-center">
        <div className="text-2xl leading-none font-semibold tracking-[0.3em] text-text-primary">JARVIS</div>
        <div className="mt-2 text-xs font-medium tracking-[0.3em]" style={{ color }}>
          AI CORE
        </div>
        <div className="mt-1 font-mono text-xs text-text-secondary">v0.1.0</div>
      </div>
      <div className="pointer-events-none absolute top-4 left-4">
        <Chip tone={PHASE_TONE[phase]}>
          <Dot tone={PHASE_TONE[phase]} pulse={phase !== 'idle'} />
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
            className="pointer-events-none absolute right-6 bottom-2 left-6 truncate text-center text-xs"
          >
            <span className={last.role === 'user' ? 'text-text-secondary' : 'text-text-primary'}>
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

// info neutro; alerta = atenção; dica = algo a fazer (interação); ao vivo = rodando; notícia = domínio de dados
const FEED_META: Record<FeedKind, { icon: LucideIcon; tone: Tone; tag: string; color: string }> = {
  info: { icon: Info, tone: 'gray', tag: 'Info', color: C.muted },
  warn: { icon: AlertTriangle, tone: 'amber', tag: 'Alerta', color: C.warning },
  tip: { icon: Lightbulb, tone: 'cyan', tag: 'Dica', color: C.primary },
  live: { icon: Radio, tone: 'green', tag: 'Ao vivo', color: C.success },
  news: { icon: Newspaper, tone: 'violet', tag: 'Notícia', color: C.data },
}

export function IntelFeed() {
  const feed = useJarvis((s) => s.feed)
  const [all, setAll] = useState(false)
  const items = all ? feed : feed.slice(0, 5)
  return (
    <Card
      id="noticias"
      title="Feed de inteligência"
      right={
        <Chip tone="green">
          <Dot tone="green" pulse /> Ao vivo
        </Chip>
      }
      bodyClassName="flex flex-col"
    >
      <ul className="scroll-thin -mr-1 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {items.map((it) => {
            const m = FEED_META[it.kind] ?? FEED_META.info
            const Icon = m.icon
            const body = (
              <>
                <Icon size={14} className="shrink-0" style={{ color: m.color }} />
                <div className="min-w-0 flex-1 leading-tight">
                  <div className="truncate text-xs text-text-primary">{it.title}</div>
                  <div className="truncate text-xs text-text-secondary">
                    {it.subtitle ? `${it.subtitle} · ` : ''}
                    {timeAgo(it.ts)}
                  </div>
                </div>
                <Chip tone={m.tone}>{m.tag}</Chip>
              </>
            )
            const row = 'flex min-w-0 flex-1 items-center gap-2 rounded-base px-1 py-1'
            return (
              <motion.li
                key={it.id}
                layout
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                title={it.title}
                className="flex min-w-0 border-b border-surface-raised"
              >
                {it.url ? (
                  <a tabIndex={0} href={it.url} target="_blank" rel="noopener noreferrer" className={`${row} transition-colors hover:bg-surface-raised`}>
                    {body}
                  </a>
                ) : (
                  <div className={row}>{body}</div>
                )}
              </motion.li>
            )
          })}
        </AnimatePresence>
        {feed.length === 0 && <li className="py-4 text-center text-xs text-text-secondary">Sem eventos ainda</li>}
      </ul>
      <button
        tabIndex={0}
        onClick={() => setAll((v) => !v)}
        className="mt-2 flex shrink-0 items-center gap-1 self-start text-xs font-medium text-primary hover:underline"
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
      id="agentes"
      title="Agentes ativos"
      right={<span className="text-xs text-text-secondary"><span className="font-mono">{active}</span> em execução</span>}
      bodyClassName="grid grid-cols-3 gap-2 auto-rows-fr"
    >
      {agents.slice(0, 6).map((a) => {
        const Icon = agentIcon(a.id)
        const on = a.status === 'active'
        return (
          <div
            key={a.id}
            className={`tile flex min-w-0 flex-col justify-between gap-1 px-2 py-1 ${on ? 'border-success/30' : ''}`}
          >
            <div className="flex items-center gap-2">
              <Icon size={14} className={on ? 'text-success' : 'text-text-secondary'} />
              <span className="truncate text-xs font-medium text-text-primary" title={a.name}>
                {shortAgentName(a.name)}
              </span>
            </div>
            {/* o rótulo não quebra; a onda (decorativa) é que cede espaço em tiles estreitos */}
            <div className="flex min-w-0 items-center justify-between gap-1">
              <span className={`shrink-0 text-xs font-medium whitespace-nowrap ${on ? 'text-success' : 'text-text-secondary'}`}>
                {on ? 'Ativo' : 'Em espera'}
              </span>
              <Waveform
                bars={7}
                active={on}
                height={12}
                barWidth={2}
                gap={2}
                color={on ? C.success : C.muted}
                className="min-w-0 overflow-hidden"
              />
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
  // conectado e ainda sem a 1ª leitura do Calendário (pode levar um minuto): "carregando", não "nada agendado"
  const loading = useJarvis((s) => s.connected && !s.timelineReady)
  const doneCount = events.filter((e) => isDone(e.status)).length
  const pct = events.length ? (doneCount / events.length) * 100 : 0
  return (
    <Card
      id="calendario"
      title="Linha do tempo da missão"
      right={<span className="font-mono text-xs text-text-secondary">{doneCount}/{events.length}</span>}
      bodyClassName="flex flex-col"
    >
      <div className="mb-2 h-1 shrink-0 overflow-hidden rounded-full bg-surface-raised">
        <div
          className="h-full rounded-full bg-success transition-[width] duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
      <ol className="scroll-thin relative flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
        {events.map((e, i) => {
          const done = isDone(e.status)
          return (
            <li key={`${e.time}-${i}`} className="relative flex items-center gap-2">
              <span className="w-12 shrink-0 font-mono text-xs text-text-secondary">{e.time}</span>
              <span className="relative flex h-full flex-col items-center">
                <span className={`h-2 w-2 rounded-full ${done ? 'bg-success' : 'border border-warning bg-warning/15'}`} />
              </span>
              <span className={`min-w-0 flex-1 truncate text-xs ${done ? 'text-text-secondary' : 'text-text-primary'}`}>{e.title}</span>
              <span className={`flex shrink-0 items-center gap-1 text-xs ${done ? 'text-success' : 'text-warning'}`}>
                {done ? <CheckCircle2 size={12} /> : <Clock3 size={12} />}
                {e.status}
              </span>
            </li>
          )
        })}
        {events.length === 0 && (
          <li className="py-4 text-center text-xs text-text-secondary">
            {loading ? 'Lendo a agenda do Calendário…' : 'Nada agendado para hoje'}
          </li>
        )}
      </ol>
    </Card>
  )
}

/* ───────────── QUICK COMMANDS ───────────── */

// ids aceitos pelo daemon: briefing (rodapé), news, agenda, new_task, voice
const COMMANDS: { id: string; label: string; icon: LucideIcon; hint: string }[] = [
  {
    id: 'new_task',
    label: 'Iniciar tarefa',
    icon: Play,
    hint: 'O Jarvis pergunta a tarefa. Gravar no Todoist exige abrir o Jarvis com --writes.',
  },
  { id: 'agenda', label: 'Abrir calendário', icon: CalendarDays, hint: 'O Jarvis lê os compromissos de hoje.' },
  {
    id: 'voice',
    label: 'Iniciar conversa por voz',
    icon: Mic,
    hint: 'A próxima frase vale sem dizer “Jarvis” (só com a escuta contínua ligada).',
  },
  { id: 'news', label: 'Resumo de notícias', icon: Newspaper, hint: 'O Jarvis resume as manchetes das suas fontes.' },
]

export function QuickCommands() {
  return (
    <Card title="Comandos rápidos" bodyClassName="grid grid-cols-1 gap-1 auto-rows-fr">
      {COMMANDS.map(({ id, label, icon: Icon, hint }) => (
        <motion.button
          key={id}
          title={hint}
          whileTap={{ scale: 0.97 }}
          onClick={() => {
            send({ type: 'command', id })
            if (id !== 'voice') useJarvis.getState().setChatOpen(true)
          }}
          className="tile group flex min-w-0 items-center gap-2 px-3 text-left hover:border-primary hover:bg-surface-raised"
        >
          <Icon size={14} className="shrink-0 text-primary" />
          <span className="flex-1 truncate text-xs font-medium text-text-primary">{label}</span>
          <ChevronRight size={14} className="text-text-secondary group-hover:text-primary" />
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
          <circle cx="33" cy="33" r={r} fill="none" stroke={C.raised} strokeWidth="5" />
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
            style={{ transition: 'stroke-dashoffset 0.8s ease' }}
          />
        </svg>
        <div className="absolute inset-0 grid place-items-center">
          <span className="font-mono text-xs font-medium text-text-primary tabular-nums">{Math.round(v)}%</span>
        </div>
      </div>
      <div className="flex items-center gap-1 text-xs font-medium text-text-secondary">
        <Icon size={12} style={{ color }} />
        {label}
      </div>
    </div>
  )
}

export function SystemMonitor() {
  const t = useJarvis((s) => s.telemetry)
  return (
    <Card title="Monitor do sistema" right={<Activity size={14} className="text-text-secondary" />} bodyClassName="flex items-center justify-around">
      <Ring label="CPU" value={t.cpu} color={C.primary} icon={Cpu} />
      <Ring label="RAM" value={t.ram} color={C.success} icon={Server} />
      <Ring label="Disco" value={t.disk} color={C.data} icon={Database} />
    </Card>
  )
}

/* ───────────── MEMORY INSIGHTS ───────────── */

function Constellation() {
  const still = useReducedMotion()
  const { nodes, edges } = useMemo(() => {
    let seed = 11
    const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646
    const nodes = Array.from({ length: 16 }, (_, i) => ({
      x: 8 + rand() * 104,
      y: 8 + rand() * 64,
      r: i % 5 === 0 ? 2.6 : 1.4 + rand(),
      c: i % 5 === 0 ? C.data : alpha(C.data, 60),
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
        <line key={k} x1={nodes[i].x} y1={nodes[i].y} x2={nodes[j].x} y2={nodes[j].y} stroke={C.muted} strokeOpacity="0.3" strokeWidth="0.6" />
      ))}
      {nodes.map((n, i) => (
        <circle key={i} cx={n.x} cy={n.y} r={n.r} fill={n.c}>
          {!still && <animate attributeName="opacity" values="1;0.35;1" dur={`${2 + (i % 5) * 0.7}s`} repeatCount="indefinite" />}
        </circle>
      ))}
    </svg>
  )
}

export function MemoryInsights() {
  const m = useJarvis((s) => s.memory)
  const rows: [string, number][] = [
    ['Memórias', m.memories],
    ['Turnos de sessão', m.sessionTurns],
    ['Chamadas de ferramenta', m.toolCalls],
  ]
  return (
    <Card id="memoria" title="Insights de memória" bodyClassName="grid grid-cols-[1fr_1.1fr] items-center gap-2">
      <div className="flex h-full min-h-0 items-center">
        <Constellation />
      </div>
      <div className="flex min-w-0 flex-col gap-1">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0 leading-tight">
            <div className="font-mono text-sm font-medium text-text-primary tabular-nums">{formatInt(value)}</div>
            <div className="truncate text-xs text-text-secondary">{label}</div>
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
        <span className="text-xs text-success">
          <span className="font-mono">{n}</span> {n === 1 ? 'conectado' : 'conectados'}
        </span>
      }
      bodyClassName="grid grid-cols-3 gap-1 auto-rows-fr"
    >
      {providers.slice(0, 9).map((p) => {
        const on = p.status === 'connected'
        return (
          // o ponto diz o estado (verde conectado, cinza não vinculado); o texto completo fica no title
          <div
            key={p.name}
            title={`${p.name}: ${on ? 'Conectado' : 'Não vinculado'}`}
            className="tile flex min-h-0 min-w-0 items-center gap-2 px-2 leading-tight"
          >
            <Dot tone={on ? 'green' : 'gray'} />
            <span className={`truncate text-xs ${on ? 'font-medium text-text-primary' : 'text-text-secondary'}`}>{p.name}</span>
            <span className="sr-only">{on ? 'Conectado' : 'Não vinculado'}</span>
          </div>
        )
      })}
    </Card>
  )
}
