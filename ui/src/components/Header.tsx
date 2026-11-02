import { Bell, LayoutGrid, Menu, Search, Settings, UserRound } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useJarvis } from '../store'
import { send, wsUrl } from '../ws'
import { NavList } from './Sidebar'
import { Dot, Popover, timeAgo } from './ui'

const dateFmt = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
const timeFmt = new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

function StatusPill() {
  const connected = useJarvis((s) => s.connected)
  const health = useJarvis((s) => s.health)
  const values = Object.values(health)
  const [label, tone, cls] = !connected
    ? (['OFFLINE', 'red', 'text-rose-300'] as const)
    : values.some((h) => h.status === 'off')
      ? (['DEGRADADO', 'red', 'text-rose-300'] as const)
      : values.some((h) => h.status === 'warn')
        ? (['ATENÇÃO', 'amber', 'text-amber-300'] as const)
        : (['ÓTIMO', 'green', 'text-emerald-300'] as const)
  return (
    <div
      className="glass flex w-fit items-center gap-2 rounded-full px-3.5 py-1.5 text-[10px] font-semibold tracking-[0.16em] whitespace-nowrap"
      title={connected ? 'Conectado ao daemon' : 'Daemon desconectado — exibindo dados de demonstração'}
    >
      <span className="text-slate-400">STATUS DO SISTEMA</span>
      <Dot tone={tone} pulse />
      <span className={cls}>{label}</span>
    </div>
  )
}

/** Alertas e dicas do feed (avisos de voz, falhas de fonte, erros do Claude). O ponto marca o que ainda não foi visto. */
function Notifications() {
  const feed = useJarvis((s) => s.feed)
  const seen = useJarvis((s) => s.alertsSeen)
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const alerts = feed.filter((f) => f.kind === 'warn' || f.kind === 'tip')
  const unseen = alerts.filter((a) => (a.ts < 1e12 ? a.ts * 1000 : a.ts) > seen).length
  return (
    <div className="relative shrink-0">
      <button
        tabIndex={0}
        className="icon-btn relative"
        aria-label={unseen ? `Notificações (${unseen} novas)` : 'Notificações'}
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v)
          useJarvis.getState().markAlertsSeen()
        }}
      >
        <Bell size={15} />
        {unseen > 0 && <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-rose-400 shadow-[0_0_6px_#f87171]" />}
      </button>
      <Popover open={open} onClose={close} label="Notificações">
        {alerts.length === 0 ? (
          <p className="py-2 text-[11.5px] text-slate-400">Nenhum alerta por enquanto.</p>
        ) : (
          <ul className="scroll-thin flex max-h-72 flex-col gap-1.5 overflow-y-auto">
            {alerts.slice(0, 12).map((a) => (
              <li key={a.id} className="tile px-2 py-1.5 leading-tight">
                <div className={`text-[11.5px] ${a.kind === 'warn' ? 'text-amber-200' : 'text-cyan-50'}`}>{a.title}</div>
                <div className="text-[10px] text-slate-400">
                  {a.subtitle ? `${a.subtitle} · ` : ''}
                  {timeAgo(a.ts)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Popover>
    </div>
  )
}

/** O que está em uso agora. Os ajustes em si ficam nas opções de linha de comando e no .env (README). */
function SettingsInfo() {
  const connected = useJarvis((s) => s.connected)
  const health = useJarvis((s) => s.health)
  const llms = useJarvis((s) => s.llms)
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  const rows: [string, string][] = [
    ['Conexão', connected ? 'Conectado ao daemon' : 'Offline · demonstração'],
    ['Endereço', wsUrl],
    ['Cérebro', health.core.detail],
    ['Voz', health.voice.detail],
    ['Modelos', llms.length ? `${llms.filter((p) => p.status === 'connected').length} de ${llms.length} conectados` : '—'],
  ]
  return (
    <div className="relative shrink-0">
      <button tabIndex={0} className="icon-btn" aria-label="Configurações" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <Settings size={15} />
      </button>
      <Popover open={open} onClose={close} label="Configurações">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11.5px]">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-slate-400">{k}</dt>
              <dd className="truncate text-cyan-50" title={v}>
                {v}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-2.5 border-t border-cyan-400/10 pt-2 text-[10.5px] leading-snug text-slate-400">
          Modo de voz, modelo e escrita mudam ao abrir o Jarvis: <code className="text-cyan-200">uv run jarvis --help</code> e
          variáveis do <code className="text-cyan-200">.env</code> (README).
        </p>
      </Popover>
    </div>
  )
}

/** No celular a barra lateral some: as mesmas seções ficam neste menu. */
function MobileNav() {
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  return (
    <div className="relative shrink-0 md:hidden">
      <button tabIndex={0} className="icon-btn" aria-label="Menu de seções" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <Menu size={15} />
      </button>
      <Popover open={open} onClose={close} label="Seções" align="left">
        <nav aria-label="Seções" className="flex flex-col gap-[2px]">
          <NavList onPick={close} />
        </nav>
      </Popover>
    </div>
  )
}

export default function Header() {
  const now = useNow()
  const [q, setQ] = useState('')
  const field = useRef<HTMLInputElement>(null)
  const focusMode = useJarvis((s) => s.focusMode)
  const toggleFocus = useJarvis((s) => s.toggleFocus)

  // ⌘K / Ctrl+K leva ao campo de comando
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        field.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <header className="grid shrink-0 grid-cols-1 items-center gap-3 sm:grid-cols-[1fr_auto_1fr]">
      <div className="flex justify-center sm:justify-start">
        <StatusPill />
      </div>

      <div className="text-center leading-none">
        <div className="text-[11px] tracking-wide text-slate-400 first-letter:uppercase">{dateFmt.format(now)}</div>
        <div className="glow-text mt-1 font-mono text-[28px] font-semibold tabular-nums tracking-[0.08em] text-cyan-200">
          {timeFmt.format(now)}
        </div>
      </div>

      <div className="flex min-w-0 items-center justify-center gap-2 sm:justify-end">
        <MobileNav />
        <form
          className="glass field-ring flex h-8 min-w-0 flex-1 items-center gap-2 rounded-[9px] px-2.5 sm:max-w-[210px]"
          onSubmit={(e) => {
            e.preventDefault()
            const text = q.trim()
            if (text) {
              send({ type: 'say', text })
              useJarvis.getState().setChatOpen(true)
            }
            setQ('')
          }}
        >
          <Search size={13} className="shrink-0 text-cyan-400/70" />
          <input
            ref={field}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Pesquisar ou comandar…"
            aria-label="Pergunte ou dê um comando ao Jarvis"
            className="min-w-0 flex-1 bg-transparent text-[11.5px] text-cyan-50 placeholder:text-slate-400 focus:outline-none"
          />
          <kbd className="hidden rounded border border-slate-600/50 px-1 text-[10px] text-slate-400 lg:block">⌘K</kbd>
        </form>
        <button
          tabIndex={0}
          className="icon-btn shrink-0"
          aria-label="Layout: Modo Foco"
          aria-pressed={focusMode}
          title="Alterna entre o painel completo e o Modo Foco"
          onClick={toggleFocus}
        >
          <LayoutGrid size={15} />
        </button>
        <Notifications />
        <SettingsInfo />
        <div className="glass hidden shrink-0 items-center gap-2 rounded-full py-1 pr-3 pl-1 lg:flex">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-cyan-400/40 to-violet-500/40 ring-1 ring-cyan-300/50">
            <UserRound size={14} className="text-cyan-50" />
          </span>
          <span className="leading-tight">
            <span className="block text-[11px] font-medium text-cyan-50">Operador</span>
            <span className="block text-[10px] tracking-wider text-cyan-400/80">Comandante</span>
          </span>
        </div>
      </div>
    </header>
  )
}
