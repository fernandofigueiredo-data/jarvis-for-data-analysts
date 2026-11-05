import { motion, useReducedMotion } from 'framer-motion'
import {
  Bot,
  Brain,
  CalendarDays,
  Crosshair,
  Database,
  LayoutDashboard,
  MessagesSquare,
  Mic,
  Newspaper,
  Table2,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useJarvis, type Section } from '../store'
import { send } from '../ws'
import { alpha, C, PHASE_COLOR, PHASE_LABEL, prefersStill, spotlight, Waveform } from './ui'

// Cada item leva a um cartão do Command Center (ou abre a conversa). Tarefas, Base de Conhecimento,
// Ferramentas & Skills e Workflows saíram: o daemon não tem nada disso para mostrar.
const NAV: { label: string; icon: LucideIcon; to: Section }[] = [
  { label: 'Command Center', icon: LayoutDashboard, to: 'top' },
  { label: 'AI Core', icon: Brain, to: 'ai-core' },
  { label: 'Agentes', icon: Bot, to: 'agentes' },
  { label: 'Calendário', icon: CalendarDays, to: 'calendario' },
  { label: 'Memória', icon: Database, to: 'memoria' },
  { label: 'Conversas', icon: MessagesSquare, to: 'conversa' },
  { label: 'Notícias', icon: Newspaper, to: 'noticias' },
  { label: 'Dados', icon: Table2, to: 'dados' },
]

export function goTo(to: Section) {
  const s = useJarvis.getState()
  s.setSection(to)
  if (to === 'conversa') s.setChatOpen(true)
  else if (to === 'dados') s.setDataOpen(true)
  // no Modo Foco só o globo e o feed aparecem: o Command Center e os outros cartões pedem o painel completo
  else if (s.focusMode && to !== 'noticias') s.toggleFocus()
  requestAnimationFrame(() => {
    if (to === 'top') {
      document.querySelector('main')?.scrollIntoView({ behavior: prefersStill() ? 'auto' : 'smooth' })
      return
    }
    spotlight(document.getElementById(to))
  })
}

export function NavList({ onPick }: { onPick?: () => void }) {
  const section = useJarvis((s) => s.section)
  return (
    <>
      {NAV.map(({ label, icon: Icon, to }) => {
        const active = to === section
        // tabIndex explícito em botões e links: na janela nativa (WebKit) o Tab do macOS só passa por quem o declara
        return (
          <button
            tabIndex={0}
            key={label}
            aria-current={active ? 'page' : undefined}
            onClick={() => {
              goTo(to)
              onPick?.()
            }}
            className={`group relative flex items-center gap-3 rounded-base px-3 py-1 text-left text-sm transition-colors ${
              active ? 'bg-surface-raised font-medium text-text-primary' : 'text-text-secondary hover:bg-surface-raised hover:text-text-primary'
            }`}
          >
            {active && <span className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-primary" />}
            <Icon size={16} className={active ? 'text-primary' : 'text-text-secondary group-hover:text-primary'} />
            <span className="flex-1 truncate">{label}</span>
          </button>
        )
      })}
    </>
  )
}

export function Reactor({ size = 34 }: { size?: number }) {
  const still = useReducedMotion()
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <circle cx="20" cy="20" r="18" fill="none" stroke={C.muted} strokeOpacity="0.5" strokeWidth="1" />
      <circle cx="20" cy="20" r="14" fill="none" stroke={C.primary} strokeWidth="1.6" strokeDasharray="5 3">
        {!still && (
          <animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="12s" repeatCount="indefinite" />
        )}
      </circle>
      {Array.from({ length: 8 }, (_, i) => (
        <rect key={i} x="19" y="7.5" width="2" height="4" rx="1" fill={C.primary} transform={`rotate(${i * 45} 20 20)`} opacity="0.8" />
      ))}
      <circle cx="20" cy="20" r="6" fill={alpha(C.primary, 30)} />
      <circle cx="20" cy="20" r="3.2" fill={C.text} />
    </svg>
  )
}

/** Segure para falar. Na barra lateral (desktop) e, compacto, no rodapé do celular. */
export function PushToTalk({ size = 54, compact = false }: { size?: number; compact?: boolean }) {
  const phase = useJarvis((s) => s.phase)
  const pttDown = useJarvis((s) => s.pttDown)
  const voiceOff = useJarvis((s) => s.connected && s.health.voice.detail === 'Desligada')
  const holding = useRef(false)
  const since = useRef(0)
  const [hint, setHint] = useState('')

  useEffect(() => {
    if (!hint) return
    const id = setTimeout(() => setHint(''), 3500)
    return () => clearTimeout(id)
  }, [hint])

  const press = (down: boolean) => {
    if (holding.current === down) return
    holding.current = down
    useJarvis.getState().setPtt(down)
    send({ type: 'ptt', down })
    if (down) since.current = performance.now()
    // o daemon descarta menos de 0,3 s de áudio: um clique rápido não vira pergunta, então explica na hora
    else if (performance.now() - since.current < 400 && !voiceOff) setHint('Segure o botão enquanto fala')
  }

  return (
    <div className="relative flex flex-col items-center gap-2">
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
        onContextMenu={(e) => e.preventDefault()} // segurar no celular não abre o menu do sistema
        whileTap={{ scale: 0.94 }}
        className={`btn-primary relative grid shrink-0 touch-none place-items-center rounded-full select-none ${compact ? '' : 'my-1'}`}
        style={{ width: size, height: size }}
      >
        {(pttDown || phase === 'listening') && (
          <span className="pulse-ring absolute inset-0 rounded-full border border-primary" />
        )}
        <Mic size={Math.round(size * 0.4)} />
      </motion.button>
      {compact ? (
        hint && (
          <div
            aria-hidden
            className="tile absolute bottom-[calc(100%+8px)] left-0 bg-surface-raised px-2 py-1 text-xs whitespace-nowrap text-warning"
          >
            {hint}
          </div>
        )
      ) : (
        <div className={`text-center text-xs ${hint ? 'text-warning' : 'text-text-secondary'}`} aria-hidden>
          {hint || (voiceOff ? 'Voz desligada (--mode off)' : 'Segure para falar')}
        </div>
      )}
      <span role="status" className="sr-only">
        {hint}
      </span>
    </div>
  )
}

export default function Sidebar() {
  const phase = useJarvis((s) => s.phase)
  const level = useJarvis((s) => s.level)
  const pttDown = useJarvis((s) => s.pttDown)
  const focusMode = useJarvis((s) => s.focusMode)
  const toggleFocus = useJarvis((s) => s.toggleFocus)

  const live = phase !== 'idle' || pttDown
  const color = PHASE_COLOR[pttDown ? 'listening' : phase]

  return (
    <aside className="hidden w-52 shrink-0 flex-col gap-3 border-r border-surface-raised bg-surface px-3 py-4 md:flex">
      <div className="flex items-center gap-2 px-1">
        <Reactor />
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-[0.24em] text-text-primary">JARVIS</div>
          <div className="text-xs font-medium tracking-[0.08em] text-text-secondary">Command Center</div>
        </div>
      </div>

      <nav aria-label="Seções" className="scroll-thin -mx-1 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-1">
        <NavList />
      </nav>

      <div className="tile flex flex-col items-center gap-2 px-2 py-3">
        <div className="card-title self-start">Status de voz</div>
        <Waveform bars={22} active={live} amp={phase === 'speaking' ? level : 0.8} height={20} color={color} />
        <div className="text-xs font-medium" style={{ color }}>
          {pttDown ? PHASE_LABEL.listening : PHASE_LABEL[phase]}
        </div>
        <PushToTalk />
      </div>

      <button
        tabIndex={0}
        onClick={toggleFocus}
        aria-pressed={focusMode}
        className="btn-secondary flex items-center justify-center gap-2 px-3 py-2 text-xs"
      >
        <Crosshair size={14} />
        Modo Foco {focusMode ? 'ativo' : ''}
      </button>
    </aside>
  )
}
