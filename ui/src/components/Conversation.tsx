import { MessagesSquare, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useJarvis } from '../store'
import type { TranscriptLine } from '../types'

function Line({ line, old = false }: { line: TranscriptLine; old?: boolean }) {
  const user = line.role === 'user'
  return (
    <li className={`flex flex-col gap-1 ${user ? 'items-end' : 'items-start'}`}>
      <span className="text-xs font-medium tracking-[0.08em] text-text-secondary uppercase">{user ? 'Você' : 'Jarvis'}</span>
      {/* conversas antigas ficam mais apagadas só no balão: os rótulos mantêm o contraste.
          O que o modelo escreveu leva a borda-esquerda Roxa (§12): "isto o modelo escreveu" × "isto você escreveu" */}
      <span
        className={`max-w-[92%] rounded-base px-3 py-2 text-sm leading-snug whitespace-pre-wrap text-text-primary ${
          user ? 'border border-text-secondary/30' : 'border border-text-secondary/30 border-l-2 border-l-data'
        } ${old ? 'opacity-75' : ''}`}
      >
        {line.text}
        {!line.final && <span className="blink ml-1 text-primary">▍</span>}
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
    // o posicionamento fica num invólucro: o .card (fora das camadas do Tailwind) força position: relative
    <div className="absolute bottom-[calc(100%+8px)] left-1/2 z-30 w-[min(560px,calc(100vw-24px))] -translate-x-1/2">
      <section
        id="conversa"
        aria-label="Conversa"
        tabIndex={-1}
        onKeyDown={(e) => e.key === 'Escape' && close()}
        className="card card-raised flex max-h-[min(46vh,420px)] flex-col p-4 focus:outline-none"
      >
        <header className="mb-2 flex shrink-0 items-center justify-between">
          <h2 className="card-title flex items-center gap-2">
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
            <li role="separator" className="my-1 flex items-center gap-2 text-xs tracking-[0.08em] text-text-secondary uppercase">
              <span className="flex-1 border-t border-text-secondary/30" /> Agora <span className="flex-1 border-t border-text-secondary/30" />
            </li>
          )}
          {transcript.map((l, i) => (
            <Line key={`t${i}`} line={l} />
          ))}
          {waiting && (
            <li className="flex items-center gap-2 text-xs text-text-secondary">
              <span className="blink inline-block h-2 w-2 rounded-full bg-data" />
              {phase === 'tooling' ? 'Jarvis está consultando uma ferramenta…' : 'Jarvis está pensando…'}
            </li>
          )}
          {history.length === 0 && transcript.length === 0 && (
            <li className="py-4 text-center text-xs text-text-secondary">
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
