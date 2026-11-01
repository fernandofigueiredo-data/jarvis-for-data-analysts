import { Bell, LayoutGrid, Search, Settings, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useJarvis } from '../store'
import { send } from '../ws'
import { Dot } from './ui'

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

export default function Header() {
  const now = useNow()
  const [q, setQ] = useState('')

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
        <form
          className="glass flex h-8 min-w-0 flex-1 items-center gap-2 rounded-[9px] px-2.5 sm:max-w-[210px]"
          onSubmit={(e) => {
            e.preventDefault()
            const text = q.trim()
            if (text) send({ type: 'say', text })
            setQ('')
          }}
        >
          <Search size={13} className="shrink-0 text-cyan-400/70" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Pesquisar ou comandar…"
            className="min-w-0 flex-1 bg-transparent text-[11.5px] text-cyan-50 placeholder:text-slate-500 focus:outline-none"
          />
          <kbd className="hidden rounded border border-slate-600/50 px-1 text-[9px] text-slate-500 lg:block">⌘K</kbd>
        </form>
        <button className="icon-btn shrink-0" aria-label="Layout">
          <LayoutGrid size={15} />
        </button>
        <button className="icon-btn relative shrink-0" aria-label="Notificações">
          <Bell size={15} />
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-rose-400 shadow-[0_0_6px_#f87171]" />
        </button>
        <button className="icon-btn shrink-0" aria-label="Configurações">
          <Settings size={15} />
        </button>
        <div className="glass hidden shrink-0 items-center gap-2 rounded-full py-1 pr-3 pl-1 lg:flex">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-cyan-400/40 to-violet-500/40 ring-1 ring-cyan-300/50">
            <UserRound size={14} className="text-cyan-50" />
          </span>
          <span className="leading-tight">
            <span className="block text-[11px] font-medium text-cyan-50">Operador</span>
            <span className="block text-[9px] tracking-wider text-cyan-400/70">Comandante</span>
          </span>
        </div>
      </div>
    </header>
  )
}
