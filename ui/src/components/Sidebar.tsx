import { motion } from 'framer-motion'
import {
  Bot,
  BookOpen,
  Brain,
  CalendarDays,
  Crosshair,
  Database,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
  Mic,
  Newspaper,
  Workflow,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import { useRef } from 'react'
import { useJarvis } from '../store'
import { send } from '../ws'
import { PHASE_COLOR, PHASE_LABEL, Waveform } from './ui'

const NAV: { label: string; icon: LucideIcon; badge?: number }[] = [
  { label: 'Command Center', icon: LayoutDashboard },
  { label: 'AI Core', icon: Brain },
  { label: 'Agentes', icon: Bot },
  { label: 'Tarefas', icon: ListChecks, badge: 3 },
  { label: 'Calendário', icon: CalendarDays },
  { label: 'Memória', icon: Database },
  { label: 'Conversas', icon: MessagesSquare, badge: 12 },
  { label: 'Base de Conhecimento', icon: BookOpen },
  { label: 'Ferramentas & Skills', icon: Wrench, badge: 18 },
  { label: 'Workflows', icon: Workflow },
  { label: 'Notícias', icon: Newspaper },
]

export function Reactor({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <radialGradient id="rc" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#e0fbff" />
          <stop offset="45%" stopColor="#22d3ee" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="18" fill="none" stroke="#22d3ee" strokeOpacity="0.5" strokeWidth="1" />
      <circle cx="20" cy="20" r="14" fill="none" stroke="#67e8f9" strokeWidth="1.6" strokeDasharray="5 3">
        <animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="12s" repeatCount="indefinite" />
      </circle>
      {Array.from({ length: 8 }, (_, i) => (
        <rect key={i} x="19" y="7.5" width="2" height="4" rx="1" fill="#67e8f9" transform={`rotate(${i * 45} 20 20)`} opacity="0.8" />
      ))}
      <circle cx="20" cy="20" r="8" fill="url(#rc)" />
      <circle cx="20" cy="20" r="3.2" fill="#ecfeff" />
    </svg>
  )
}

export default function Sidebar() {
  const phase = useJarvis((s) => s.phase)
  const level = useJarvis((s) => s.level)
  const pttDown = useJarvis((s) => s.pttDown)
  const focusMode = useJarvis((s) => s.focusMode)
  const toggleFocus = useJarvis((s) => s.toggleFocus)
  const holding = useRef(false)

  const press = (down: boolean) => {
    if (holding.current === down) return
    holding.current = down
    useJarvis.getState().setPtt(down)
    send({ type: 'ptt', down })
  }

  const live = phase !== 'idle' || pttDown
  const color = PHASE_COLOR[pttDown ? 'listening' : phase]

  return (
    <aside className="glass hidden w-[184px] shrink-0 flex-col gap-2.5 rounded-none border-y-0 border-l-0 px-3 py-3 md:flex">
      <div className="flex items-center gap-2 px-1">
        <Reactor />
        <div className="leading-tight">
          <div className="glow-text text-[15px] font-bold tracking-[0.28em] text-cyan-200">JARVIS</div>
          <div className="text-[8.5px] font-semibold tracking-[0.22em] text-cyan-400/70">COMMAND CENTER</div>
        </div>
      </div>

      <nav className="scroll-thin -mx-1 flex min-h-0 flex-1 flex-col gap-[2px] overflow-y-auto px-1">
        {NAV.map(({ label, icon: Icon, badge }, i) => {
          const active = i === 0
          return (
            <button
              key={label}
              className={`group relative flex items-center gap-2.5 rounded-lg px-2.5 py-[5px] text-left text-[12px] transition-colors ${
                active
                  ? 'bg-gradient-to-r from-cyan-400/20 to-cyan-400/5 text-cyan-100 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.35),0_0_16px_-6px_rgba(34,211,238,0.7)]'
                  : 'text-slate-400 hover:bg-cyan-400/5 hover:text-cyan-100'
              }`}
            >
              {active && <span className="absolute top-1.5 bottom-1.5 left-0 w-[2px] rounded-full bg-cyan-300 shadow-[0_0_8px_#22d3ee]" />}
              <Icon size={15} className={active ? 'text-cyan-300' : 'text-slate-500 group-hover:text-cyan-300'} />
              <span className="flex-1 truncate">{label}</span>
              {badge !== undefined && (
                <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-1.5 text-[9.5px] font-semibold text-cyan-300">
                  {badge}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      <div className="tile flex flex-col items-center gap-1.5 px-2 py-2.5">
        <div className="card-title self-start">Status de voz</div>
        <Waveform bars={22} active={live} amp={phase === 'speaking' ? level : 0.8} height={20} color={color} />
        <div className="text-[11px] font-medium" style={{ color }}>
          {pttDown ? PHASE_LABEL.listening : PHASE_LABEL[phase]}
        </div>
        <motion.button
          aria-label="Segure para falar"
          onPointerDown={(e) => {
            ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
            press(true)
          }}
          onPointerUp={() => press(false)}
          onPointerCancel={() => press(false)}
          onLostPointerCapture={() => press(false)}
          onKeyDown={(e) => (e.key === ' ' || e.key === 'Enter') && !e.repeat && press(true)}
          onKeyUp={(e) => (e.key === ' ' || e.key === 'Enter') && press(false)}
          whileTap={{ scale: 0.94 }}
          className="relative my-0.5 grid h-[54px] w-[54px] place-items-center rounded-full outline-none"
          style={{
            background: `radial-gradient(circle at 50% 40%, ${color}55, #0b2236 70%)`,
            boxShadow: `0 0 0 1px ${color}88, 0 0 ${pttDown ? 36 : 22}px ${color}88, inset 0 0 18px ${color}55`,
          }}
        >
          <span className="pulse-ring absolute inset-0 rounded-full border" style={{ borderColor: color }} />
          <Mic size={22} className="text-cyan-50" />
        </motion.button>
        <div className="text-[10px] text-slate-400">Toque para falar</div>
      </div>

      <button
        onClick={toggleFocus}
        className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-1.5 text-[11.5px] font-medium transition-all ${
          focusMode
            ? 'border-violet-400/50 bg-violet-400/15 text-violet-200 shadow-[0_0_16px_-4px_#a78bfa]'
            : 'border-cyan-400/25 bg-cyan-400/5 text-cyan-200 hover:border-cyan-400/50'
        }`}
      >
        <Crosshair size={14} />
        Modo Foco {focusMode ? 'ativo' : ''}
      </button>
    </aside>
  )
}
