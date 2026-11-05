import { motion } from 'framer-motion'
import { CloudSun, FileText, MapPin, SendHorizonal, Wifi, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useJarvis } from '../store'
import { send } from '../ws'
import Conversation from './Conversation'
import { PushToTalk } from './Sidebar'
import { PHASE_COLOR, Waveform } from './ui'

function InfoChip({
  icon: Icon,
  label,
  value,
  className = '',
}: {
  icon: LucideIcon
  label: string
  value: string
  className?: string
}) {
  return (
    <div className={`card flex min-w-0 items-center gap-2 px-3 py-2 ${className}`} title={`${label}: ${value}`}>
      <Icon size={14} className="shrink-0 text-text-secondary" />
      <div className="min-w-0 leading-tight">
        <div className="text-xs font-medium tracking-[0.08em] text-text-secondary uppercase">{label}</div>
        {/* quebra em até duas linhas: "Parcialmente nublado" não vira "Parcial…" */}
        <div className="line-clamp-2 text-xs text-text-primary">{value}</div>
      </div>
    </div>
  )
}

const SUBTITLE = {
  listening: 'Ouvindo você…',
  thinking: 'Pensando…',
  tooling: 'Executando…',
  speaking: 'Respondendo…',
} as const

// Em espera, o convite depende do modo de voz (o daemon o descreve em health.voice.detail, ver app.publish_health)
const IDLE_HINT: Record<string, string> = {
  Ouvindo: 'Diga “Ei Jarvis” ou clique para digitar',
  'Segure Option': 'Segure o Option direito ou clique para digitar',
  Desligada: 'Clique para digitar',
  Carregando: 'Carregando a voz… clique para digitar',
}

function TalkPill() {
  const phase = useJarvis((s) => s.phase)
  const level = useJarvis((s) => s.level)
  const transcript = useJarvis((s) => s.transcript)
  const connected = useJarvis((s) => s.connected)
  const voice = useJarvis((s) => s.health.voice.detail)
  const [typing, setTyping] = useState(false)
  const [text, setText] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const opener = useRef<HTMLButtonElement>(null)
  const refocus = useRef(false) // depois de enviar ou de Esc o foco volta à cápsula; depois de Tab, não
  const color = PHASE_COLOR[phase]
  const last = transcript[transcript.length - 1]
  const idle = connected ? (IDLE_HINT[voice] ?? 'Clique para digitar') : 'Modo demonstração · clique para digitar'
  const subtitle = phase === 'idle' ? idle : last ? last.text : SUBTITLE[phase]
  const live = phase !== 'idle'

  useEffect(() => {
    if (typing) input.current?.focus()
    else if (refocus.current) opener.current?.focus()
    refocus.current = false
  }, [typing])

  const close = () => {
    refocus.current = true
    setText('')
    setTyping(false)
  }

  const submit = () => {
    const t = text.trim()
    if (t) {
      send({ type: 'say', text: t })
      useJarvis.getState().setChatOpen(true)
    }
    close()
  }

  return (
    <motion.div
      onClick={() => !typing && setTyping(true)}
      whileHover={typing ? undefined : { scale: 1.01 }}
      className="input field-ring relative flex h-12 w-full min-w-0 cursor-text items-center gap-3 px-4 lg:w-[360px] lg:shrink-0"
    >
      <Waveform bars={14} active={live} amp={phase === 'speaking' ? level : 0.7} height={22} color={color} className="hidden shrink-0 sm:flex" />
      <div className="min-w-0 flex-1 text-center leading-tight">
        {typing ? (
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              submit()
            }}
          >
            <input
              ref={input}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onBlur={() => !text && setTyping(false)}
              onKeyDown={(e) => e.key === 'Escape' && close()}
              aria-label="Comando para o Jarvis"
              placeholder="Digite um comando para o Jarvis…"
              className="min-w-0 flex-1 bg-transparent text-center text-sm text-text-primary placeholder:text-text-secondary focus:outline-none"
            />
            <button tabIndex={0} type="submit" aria-label="Enviar" className="text-primary transition-opacity hover:opacity-80">
              <SendHorizonal size={16} />
            </button>
          </form>
        ) : (
          // botão de verdade: o teclado chega aqui com Tab e abre o campo com Enter ou Espaço
          <button
            tabIndex={0}
            ref={opener}
            type="button"
            aria-label="Fale com o Jarvis — digitar um comando"
            className="block w-full min-w-0 cursor-text"
          >
            <span className="block text-xs font-medium tracking-[0.2em] text-text-primary">FALE COM O JARVIS</span>
            <span
              className={`block truncate text-xs ${phase === 'idle' ? 'text-text-secondary' : ''}`}
              style={phase === 'idle' ? undefined : { color }}
            >
              {subtitle}
            </span>
          </button>
        )}
      </div>
      <Waveform bars={14} active={live} amp={phase === 'speaking' ? level : 0.7} height={22} color={color} className="hidden shrink-0 sm:flex" />
    </motion.div>
  )
}

export default function Footer() {
  const t = useJarvis((s) => s.telemetry)
  return (
    <footer className="flex shrink-0 flex-col items-stretch gap-4 lg:flex-row lg:items-center">
      {/* celular: local e rede lado a lado, clima na linha de baixo com a largura toda */}
      <div className="grid min-w-0 grid-cols-2 gap-2 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(0,1fr)] lg:w-[42%] lg:max-w-[520px] lg:shrink-0">
        {/* posição do navegador (precisa) ou, sem permissão, pelo IP: aí o valor é só aproximado e o campo diz isso */}
        <InfoChip icon={MapPin} label="Local" value={t.location ? `${t.location}${t.locationApprox ? ' (aprox.)' : ''}` : '—'} />
        <InfoChip
          icon={CloudSun}
          label="Clima"
          value={t.weather ? `${Math.round(t.weather.tempC)}°C · ${t.weather.desc}` : '—'}
          className="order-last col-span-2 sm:order-none sm:col-span-1"
        />
        <InfoChip icon={Wifi} label="Rede" value={t.network || '—'} />
      </div>
      <div className="relative flex min-w-0 flex-1 items-center justify-center gap-3">
        <Conversation />
        <span className="hidden flex-1 border-t border-dashed border-surface-raised lg:block" />
        {/* no celular a barra lateral some: o microfone vem para cá */}
        <div className="md:hidden">
          <PushToTalk size={44} compact />
        </div>
        <TalkPill />
        <span className="hidden flex-1 border-t border-dashed border-surface-raised lg:block" />
      </div>
      <motion.button
        whileTap={{ scale: 0.96 }}
        onClick={() => {
          send({ type: 'command', id: 'briefing' })
          useJarvis.getState().setChatOpen(true)
        }}
        className="btn-primary flex h-12 shrink-0 items-center justify-center gap-2 px-4 text-sm whitespace-nowrap"
      >
        <FileText size={16} />
        Briefing Executivo
      </motion.button>
    </footer>
  )
}
