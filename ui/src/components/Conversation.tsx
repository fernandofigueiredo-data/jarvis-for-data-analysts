import { MessagesSquare, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useJarvis } from '../store'
import type { TranscriptLine } from '../types'

function Line({ line, old = false }: { line: TranscriptLine; old?: boolean }) {
  const user = line.role === 'user'
  return (
    <li className={`flex flex-col gap-0.5 ${user ? 'items-end' : 'items-start'}`}>
      <span className="text-[10px] font-semibold tracking-[0.14em] text-slate-400 uppercase">{user ? 'Você' : 'Jarvis'}</span>
      {/* conversas antigas ficam mais apagadas só no balão: os rótulos mantêm o contraste */}
      <span
        className={`max-w-[92%] rounded-lg px-2.5 py-1.5 text-[12.5px] leading-snug whitespace-pre-wrap ${
          user ? 'bg-cyan-400/10 text-cyan-50' : 'border border-cyan-400/15 bg-slate-900/40 text-cyan-100'
        } ${old ? 'opacity-75' : ''}`}
      >
        {line.text}
        {!line.final && <span className="blink ml-0.5 text-cyan-300">▍</span>}
      </span>
    </li>
  )
}

/** Conversa da sessão (e as anteriores, quando o daemon as fornece). Fica aberta até ser fechada. */
export default function Conversation() {
  const open = useJarvis((s) => s.chatOpen)
  const history = useJarvis((s) => s.history)
  const transcript = useJarvis((s) => s.transcript)
  const phase = useJarvis((s) => s.phase)
  const list = useRef<HTMLOListElement>(null)
  const lastAnswer = [...transcript].reverse().find((l) => l.role === 'assistant' && l.final)
  // pergunta feita e nada escrito ainda: mostra que ele está trabalhando (a resposta pode levar segundos)
  const waiting = (phase === 'thinking' || phase === 'tooling') && transcript[transcript.length - 1]?.role === 'user'
  const close = () => useJarvis.getState().setChatOpen(false)

  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight })
  }, [open, history, transcript, waiting])

  if (!open) return null
  return (
    // o posicionamento fica num invólucro: o .glass (fora das camadas do Tailwind) força position: relative
    <div className="absolute bottom-[calc(100%+10px)] left-1/2 z-30 w-[min(560px,calc(100vw-24px))] -translate-x-1/2">
      <section
        id="conversa"
        aria-label="Conversa"
        tabIndex={-1}
        onKeyDown={(e) => e.key === 'Escape' && close()}
        className="glass glass-solid flex max-h-[min(46vh,420px)] flex-col p-3 focus:outline-none"
      >
        <header className="mb-2 flex shrink-0 items-center justify-between">
          <h2 className="card-title flex items-center gap-1.5">
            <MessagesSquare size={12} /> Conversa
          </h2>
          <button tabIndex={0} onClick={close} aria-label="Fechar conversa" className="icon-btn">
            <X size={15} />
          </button>
        </header>
        <ol ref={list} className="scroll-thin flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {history.map((l, i) => (
            <Line key={`h${i}`} line={l} old />
          ))}
          {history.length > 0 && transcript.length > 0 && (
            <li role="separator" className="my-1 flex items-center gap-2 text-[10px] tracking-[0.16em] text-slate-400 uppercase">
              <span className="flex-1 border-t border-cyan-400/15" /> Agora <span className="flex-1 border-t border-cyan-400/15" />
            </li>
          )}
          {transcript.map((l, i) => (
            <Line key={`t${i}`} line={l} />
          ))}
          {waiting && (
            <li className="flex items-center gap-1.5 text-[11.5px] text-slate-400">
              <span className="blink inline-block h-1.5 w-1.5 rounded-full bg-violet-400" />
              {phase === 'tooling' ? 'Jarvis está consultando uma ferramenta…' : 'Jarvis está pensando…'}
            </li>
          )}
          {history.length === 0 && transcript.length === 0 && (
            <li className="py-4 text-center text-[11.5px] text-slate-400">
              Pergunte pelo campo abaixo, pelo ⌘K ou dizendo “Ei Jarvis”.
            </li>
          )}
        </ol>
        {/* leitores de tela anunciam só a resposta final, não cada pedaço do streaming */}
        <p className="sr-only" aria-live="polite">
          {lastAnswer?.text}
        </p>
      </section>
    </div>
  )
}
