import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import type { Phase } from '../types'

export function Card({
  id,
  title,
  right,
  children,
  className = '',
  bodyClassName = '',
}: {
  id?: string // destino da navegação lateral
  title: string
  right?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section
      id={id}
      tabIndex={id ? -1 : undefined}
      className={`card flex min-h-0 min-w-0 flex-col p-6 focus:outline-none ${className}`}
    >
      <header className="mb-2 flex shrink-0 items-center justify-between gap-2">
        {/* cartão estreito (tablet): o título cede espaço com reticências, o selo da direita fica dentro */}
        <h2 className="card-title min-w-0 truncate" title={title}>
          {title}
        </h2>
        {right}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  )
}

/** Painel flutuante preso ao botão que o abre (o pai precisa ser `relative`). Fecha com Esc ou clique fora. */
export function Popover({
  open,
  onClose,
  label,
  children,
  align = 'right',
}: {
  open: boolean
  onClose: () => void
  label: string
  children: ReactNode
  align?: 'left' | 'right'
}) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    const onDown = (e: PointerEvent) => {
      if (!box.current?.parentElement?.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    box.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open, onClose])
  if (!open) return null
  // o .card (fora das camadas do Tailwind) força position: relative, então ele fica por dentro do diálogo
  return (
    <div
      ref={box}
      role="dialog"
      aria-label={label}
      tabIndex={-1}
      className={`absolute top-[calc(100%+8px)] z-40 w-[min(300px,calc(100vw-24px))] text-left focus:outline-none ${
        align === 'left' ? 'left-0' : 'right-0'
      }`}
    >
      <div className="card card-raised p-4">
        <div className="card-title mb-2">{label}</div>
        {children}
      </div>
    </div>
  )
}

/** Destaca e foca um cartão quando a navegação lateral leva até ele. */
export const prefersStill = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

export function spotlight(el: HTMLElement | null) {
  if (!el) return
  el.scrollIntoView({ behavior: prefersStill() ? 'auto' : 'smooth', block: 'nearest' })
  el.focus({ preventScroll: true })
  el.classList.remove('spotlight')
  void el.offsetWidth // reinicia a animação se o mesmo cartão for escolhido de novo
  el.classList.add('spotlight')
  el.addEventListener('animationend', () => el.classList.remove('spotlight'), { once: true })
}

/** Cores do design system como valores CSS (para style e SVG). Cada acento tem uma pergunta só (§1):
 *  primary "onde eu clico", success "isso funcionou / rodando", data "isso é dado ou modelo", warning "atenção". */
export const C = {
  base: 'var(--color-bg-base)',
  surface: 'var(--color-bg-surface)',
  raised: 'var(--color-bg-surface-raised)',
  primary: 'var(--color-accent-primary)',
  success: 'var(--color-accent-success)',
  data: 'var(--color-accent-data)',
  warning: 'var(--color-accent-warning)',
  text: 'var(--color-text-primary)',
  muted: 'var(--color-text-secondary)',
} as const

/** Valor resolvido de um token (o WebGL do globo não entende var(--…)). */
export function resolveToken(value: string) {
  const name = value.match(/var\((--[\w-]+)\)/)?.[1]
  return name ? getComputedStyle(document.documentElement).getPropertyValue(name).trim() : value
}

/** Cor com transparência a partir de um token: alpha(C.primary, 30) */
export const alpha = (color: string, pct: number) => `color-mix(in oklab, ${color} ${pct}%, transparent)`

// §6 Badge: fundo do acento a 15%, texto no acento sólido, borda 1px no acento a 30%. Não há vermelho no sistema:
// erro e atenção usam o Âmbar (§7).
const TONES = {
  cyan: 'text-primary border-primary/30 bg-primary/15',
  green: 'text-success border-success/30 bg-success/15',
  amber: 'text-warning border-warning/30 bg-warning/15',
  // Roxo é exceção: o fundo a 15% clareia a base e o texto cai para 4,25:1 (abaixo de AA, §2). Sem o fundo,
  // Roxo sobre Grafite dá 5,23:1. Use só sobre a camada 2: sobre o Grafite secundário o Roxo não vira texto pequeno.
  violet: 'text-data border-data/30',
  gray: 'text-text-secondary border-text-secondary/30 bg-text-secondary/15',
} as const
export type Tone = keyof typeof TONES

export function Chip({ tone = 'cyan', children, className = '' }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded-base border px-2 text-xs font-medium uppercase tracking-[0.08em] ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

export function Dot({ tone = 'green', pulse = false }: { tone?: Tone; pulse?: boolean }) {
  const color = { cyan: 'bg-primary', green: 'bg-success', amber: 'bg-warning', violet: 'bg-data', gray: 'bg-text-secondary' }[tone]
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${color} ${pulse ? 'blink' : ''}`} />
}

const BAR_SEED = [0.9, 0.55, 1.15, 0.7, 1.3, 0.8, 1.05, 0.6, 1.2, 0.75, 0.95, 0.65, 1.1, 0.85, 1.25, 0.7]

/** Forma de onda decorativa em CSS. `amp` 0..1 escala a altura (nível da voz). */
export function Waveform({
  bars = 16,
  active = true,
  amp = 1,
  height = 24,
  color = C.primary,
  className = '',
  barWidth = 2,
  gap = 2,
}: {
  bars?: number
  active?: boolean
  amp?: number
  height?: number
  color?: string
  className?: string
  barWidth?: number
  gap?: number
}) {
  const scale = active ? 0.35 + 0.65 * Math.min(1, Math.max(0, amp)) : 0.18
  return (
    <div
      className={`flex items-center ${active ? '' : 'wave-idle'} ${className}`}
      style={{ height, gap }}
      aria-hidden
    >
      {Array.from({ length: bars }, (_, i) => {
        const seed = BAR_SEED[i % BAR_SEED.length]
        const envelope = 0.45 + 0.55 * Math.sin(((i + 0.5) / bars) * Math.PI)
        return (
          <span
            key={i}
            className="wave-bar rounded-full"
            style={
              {
                width: barWidth,
                height: `${Math.max(12, envelope * scale * 100)}%`,
                background: color,
                opacity: active ? 0.95 : 0.45,
                transition: 'height 120ms linear',
                '--d': `${0.7 * seed + 0.35}s`,
                '--delay': `${-(i * 0.13) % 1}s`,
              } as CSSProperties
            }
          />
        )
      })}
    </div>
  )
}

export const PHASE_LABEL: Record<Phase, string> = {
  idle: 'Em espera',
  listening: 'Ouvindo…',
  thinking: 'Pensando…',
  tooling: 'Executando ferramenta…',
  speaking: 'Falando…',
}

// em espera = neutro; ouvindo = sua vez de agir (Ciano); pensando e falando = o modelo (Roxo); ferramenta = execução (Verde)
export const PHASE_COLOR: Record<Phase, string> = {
  idle: C.muted,
  listening: C.primary,
  thinking: C.data,
  tooling: C.success,
  speaking: C.data,
}

export function formatInt(n: number) {
  return new Intl.NumberFormat('pt-BR').format(n)
}

export function timeAgo(ts: number) {
  const ms = ts < 1e12 ? ts * 1000 : ts
  const s = Math.max(0, Math.round((Date.now() - ms) / 1000))
  if (s < 45) return 'agora'
  const m = Math.round(s / 60)
  if (m < 60) return `há ${m} min`
  const h = Math.round(m / 60)
  if (h < 24) return `há ${h} h`
  return `há ${Math.round(h / 24)} d`
}
