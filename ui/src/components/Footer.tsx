import { motion } from 'framer-motion'
import { CloudSun, FileText, MapPin, SendHorizonal, Wifi, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useJarvis } from '../store'
import { send } from '../ws'
import { PHASE_COLOR, Waveform } from './ui'

function InfoChip({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <div className="glass flex min-w-0 items-center gap-2 rounded-lg px-2.5 py-1.5" title={`${label}: ${value}`}>
      <Icon size={14} className="shrink-0 text-cyan-300" />
      <div className="min-w-0 leading-tight">
        <div className="text-[8.5px] font-semibold tracking-[0.16em] text-slate-500 uppercase">{label}</div>
        <div className="truncate text-[11px] text-cyan-50">{value}</div>
      </div>
    </div>
  )
}

const SUBTITLE = {
  idle: 'Estou ouvindo…',
  listening: 'Ouvindo você…',
  thinking: 'Pensando…',
  tooling: 'Executando…',
  speaking: 'Respondendo…',
} as const

function TalkPill() {
  const phase = useJarvis((s) => s.phase)
  const level = useJarvis((s) => s.level)
  const transcript = useJarvis((s) => s.transcript)
  const [typing, setTyping] = useState(false)
  const [text, setText] = useState('')
  const input = useRef<HTMLInputElement>(null)
  const color = PHASE_COLOR[phase]
  const last = transcript[transcript.length - 1]
  const subtitle = phase !== 'idle' && last ? last.text : SUBTITLE[phase]
  const live = phase !== 'idle'

  useEffect(() => {
    if (typing) input.current?.focus()
  }, [typing])

  const submit = () => {
    const t = text.trim()
    if (t) send({ type: 'say', text: t })
    setText('')
    setTyping(false)
  }

  return (
    <motion.div
      onClick={() => !typing && setTyping(true)}
      whileHover={typing ? undefined : { scale: 1.01 }}
      className="relative flex h-[46px] w-full min-w-0 cursor-text items-center gap-3 rounded-full px-4 lg:w-[360px] lg:shrink-0"
      style={{
        background: 'linear-gradient(180deg, rgba(14,40,64,0.85), rgba(8,22,40,0.85))',
        boxShadow: `0 0 0 1px ${color}66, 0 0 28px -6px ${color}aa, inset 0 0 22px -10px ${color}`,
      }}
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
              onKeyDown={(e) => e.key === 'Escape' && (setText(''), setTyping(false))}
              placeholder="Digite um comando para o Jarvis…"
              className="min-w-0 flex-1 bg-transparent text-center text-[12.5px] text-cyan-50 placeholder:text-slate-500 focus:outline-none"
            />
            <button type="submit" aria-label="Enviar" className="text-cyan-300 hover:text-cyan-100">
              <SendHorizonal size={15} />
            </button>
          </form>
        ) : (
          <>
            <div className="glow-text text-[11px] font-bold tracking-[0.3em] text-cyan-100">FALE COM O JARVIS</div>
            <div className="truncate text-[11px]" style={{ color }}>
              {subtitle}
            </div>
          </>
        )}
      </div>
      <Waveform bars={14} active={live} amp={phase === 'speaking' ? level : 0.7} height={22} color={color} className="hidden shrink-0 sm:flex" />
    </motion.div>
  )
}

export default function Footer() {
  const t = useJarvis((s) => s.telemetry)
  return (
    <footer className="flex shrink-0 flex-col items-stretch gap-2 lg:flex-row lg:items-center">
      <div className="grid min-w-0 grid-cols-3 gap-2 lg:w-[34%] lg:max-w-[400px] lg:shrink-0">
        <InfoChip icon={MapPin} label="Local" value={t.location ?? '—'} />
        <InfoChip icon={CloudSun} label="Clima" value={t.weather ? `${Math.round(t.weather.tempC)}°C · ${t.weather.desc}` : '—'} />
        <InfoChip icon={Wifi} label="Rede" value={t.network || '—'} />
      </div>
      <div className="flex min-w-0 flex-1 items-center justify-center gap-3">
        <span className="hidden flex-1 border-t border-dashed border-cyan-400/25 lg:block" />
        <TalkPill />
        <span className="hidden flex-1 border-t border-dashed border-cyan-400/25 lg:block" />
      </div>
      <motion.button
        whileTap={{ scale: 0.96 }}
        onClick={() => send({ type: 'command', id: 'briefing' })}
        className="flex h-[42px] shrink-0 items-center justify-center gap-2 rounded-xl border border-violet-400/40 bg-gradient-to-r from-violet-500/20 to-cyan-500/15 px-3.5 text-[12px] font-semibold whitespace-nowrap text-violet-100 shadow-[0_0_20px_-6px_#a78bfa] transition-colors hover:border-violet-300/70"
      >
        <FileText size={15} />
        Briefing Executivo
      </motion.button>
    </footer>
  )
}
