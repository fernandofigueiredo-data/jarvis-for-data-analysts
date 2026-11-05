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
  // sem vermelho no sistema (§7): offline e degradado são "precisa da sua atenção"
  const [label, tone, cls] = !connected
    ? (['OFFLINE', 'amber', 'text-warning'] as const)
    : values.some((h) => h.status === 'off')
      ? (['DEGRADADO', 'amber', 'text-warning'] as const)
      : values.some((h) => h.status === 'warn')
        ? (['ATENÇÃO', 'amber', 'text-warning'] as const)
        : (['ÓTIMO', 'green', 'text-success'] as const)
  return (
    <div
      className="card flex w-fit items-center gap-2 px-4 py-2 text-xs font-medium tracking-[0.12em] whitespace-nowrap"
      title={connected ? 'Conectado ao daemon' : 'Daemon desconectado — exibindo dados de demonstração'}
    >
      <span className="text-text-secondary">STATUS DO SISTEMA</span>
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
        {unseen > 0 && <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-warning" />}
      </button>
      <Popover open={open} onClose={close} label="Notificações">
        {alerts.length === 0 ? (
          <p className="py-2 text-xs text-text-secondary">Nenhum alerta por enquanto.</p>
        ) : (
          <ul className="scroll-thin flex max-h-72 flex-col gap-2 overflow-y-auto">
            {alerts.slice(0, 12).map((a) => (
              <li key={a.id} className="tile px-2 py-2 leading-tight">
                <div className={`text-xs ${a.kind === 'warn' ? 'text-warning' : 'text-text-primary'}`}>{a.title}</div>
                <div className="text-xs text-text-secondary">
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
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-text-secondary">{k}</dt>
              <dd className="truncate text-text-primary" title={v}>
                {v}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 border-t border-text-secondary/30 pt-2 text-xs leading-snug text-text-secondary">
          Modo de voz, modelo e escrita mudam ao abrir o Jarvis: <code className="font-mono text-success">uv run jarvis --help</code> e
          variáveis do <code className="font-mono text-success">.env</code> (README).
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
        <nav aria-label="Seções" className="flex flex-col gap-1">
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
    <header className="grid shrink-0 grid-cols-1 items-center gap-4 sm:grid-cols-[1fr_auto_1fr]">
      <div className="flex justify-center sm:justify-start">
        <StatusPill />
      </div>

      <div className="text-center leading-none">
        <div className="text-xs text-text-secondary first-letter:uppercase">{dateFmt.format(now)}</div>
        <div className="mt-1 font-mono text-xl font-medium tabular-nums tracking-[0.08em] text-text-primary">
          {timeFmt.format(now)}
        </div>
      </div>

      <div className="flex min-w-0 items-center justify-center gap-2 sm:justify-end">
        <MobileNav />
        <form
          className="input field-ring flex h-8 min-w-0 flex-1 items-center gap-2 px-3 sm:max-w-[210px]"
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
          <Search size={14} className="shrink-0 text-text-secondary" />
          <input
            ref={field}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Pesquisar ou comandar…"
            aria-label="Pergunte ou dê um comando ao Jarvis"
            className="min-w-0 flex-1 bg-transparent text-xs text-text-primary placeholder:text-text-secondary focus:outline-none"
          />
          <kbd className="hidden rounded-base border border-text-secondary/30 px-1 font-mono text-xs text-text-secondary lg:block">⌘K</kbd>
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
        <div className="card hidden shrink-0 items-center gap-2 py-1 pr-3 pl-1 lg:flex">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-surface-raised">
            <UserRound size={14} className="text-text-primary" />
          </span>
          <span className="leading-tight">
            <span className="block text-xs font-medium text-text-primary">Operador</span>
            <span className="block text-xs text-text-secondary">Comandante</span>
          </span>
        </div>
      </div>
    </header>
  )
}
