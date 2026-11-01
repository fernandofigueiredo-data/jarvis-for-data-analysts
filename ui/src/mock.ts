// Gerador de dados de demonstração: mantém o painel vivo enquanto o daemon não está conectado.
import { useJarvis } from './store'
import type { ClientMessage, FeedItem, Phase, ServerMessage, SnapshotMsg } from './types'

const apply = (m: ServerMessage) => useJarvis.getState().apply(m)
const now = () => Date.now() / 1000

let seq = 0
const feedItem = (kind: FeedItem['kind'], title: string, subtitle: string, agoSec = 0): FeedItem => ({
  id: `mock-${++seq}`,
  kind,
  title,
  subtitle,
  ts: now() - agoSec,
})

const FEED_POOL: [FeedItem['kind'], string, string][] = [
  ['info', 'Agenda sincronizada', '2 compromissos hoje'],
  ['news', 'Manchetes do dia prontas', '12 notícias de 4 fontes'],
  ['tip', 'Diga “Jarvis, briefing”', 'Resumo executivo do seu dia'],
  ['live', 'Monitorando a rede', 'Latência estável · 18 ms'],
  ['warn', 'Uso de RAM elevado', 'Considere fechar abas inativas'],
  ['info', 'Memória consolidada', '+24 memórias desta sessão'],
  ['news', 'Novo resumo de tecnologia', 'Gerado a partir das suas fontes'],
  ['tip', 'Segure o microfone para falar', 'Ou digite um comando no rodapé'],
]

export function mockSnapshot(): SnapshotMsg {
  return {
    type: 'snapshot',
    state: { phase: 'idle', level: 0 },
    feed: [
      feedItem('live', 'Jarvis online', 'Modo demonstração · daemon desconectado', 5),
      feedItem('news', 'Manchetes do dia prontas', '12 notícias de 4 fontes', 120),
      feedItem('tip', 'Diga “Jarvis, briefing”', 'Resumo executivo do seu dia', 600),
      feedItem('warn', 'Bateria em 18%', 'Conecte o carregador', 1500),
      feedItem('info', 'Lembrete às 14:00', 'Reunião de projeto', 3600),
    ],
    health: {
      components: {
        core: { status: 'ok', detail: 'Ativo' },
        memory: { status: 'ok', detail: '3.380 salvas' },
        voice: { status: 'ok', detail: 'Online' },
        agents: { status: 'ok', detail: '2 em execução' },
        llms: { status: 'ok', detail: '4 conectados' },
        system: { status: 'ok', detail: 'Ótimo' },
      },
    },
    telemetry: {
      cpu: 24,
      ram: 61,
      disk: 58,
      network: 'Wi-Fi · 5 GHz',
      weather: { tempC: 24, desc: 'Parcialmente nublado' },
      location: 'São Paulo, BR',
    },
    agents: {
      agents: [
        { id: 'coding', name: 'Código', status: 'active' },
        { id: 'research', name: 'Pesquisa', status: 'active' },
        { id: 'memory', name: 'Memória', status: 'standby' },
        { id: 'browser', name: 'Navegador', status: 'standby' },
        { id: 'task', name: 'Tarefas', status: 'standby' },
        { id: 'system', name: 'Sistema', status: 'standby' },
      ],
    },
    timeline: {
      events: [
        { time: '08:00', title: 'Briefing matinal', status: 'Concluído' },
        { time: '10:30', title: 'Revisão de código', status: 'Concluído' },
        { time: '14:00', title: 'Reunião de projeto', status: 'Em 42 min' },
        { time: '16:30', title: 'Treino', status: 'Em 3 h' },
      ],
    },
    memory: { memories: 3380, sessionTurns: 128, toolCalls: 47 },
    llms: {
      providers: [
        { name: 'Claude Code', status: 'connected' },
        { name: 'Claude', status: 'connected' },
        { name: 'OpenAI', status: 'connected' },
        { name: 'Gemini', status: 'not_linked' },
        { name: 'Groq', status: 'connected' },
        { name: 'OpenRouter', status: 'not_linked' },
        { name: 'Ollama', status: 'not_linked' },
        { name: 'Cursor', status: 'not_linked' },
        { name: 'Copilot', status: 'not_linked' },
      ],
    },
  }
}

const timers = new Set<ReturnType<typeof setTimeout>>()
let running = false
let speakingRaf = 0

function later(ms: number, fn: () => void) {
  const id = setTimeout(() => {
    timers.delete(id)
    if (running) fn()
  }, ms)
  timers.add(id)
}

function setPhase(phase: Phase, level = 0) {
  cancelAnimationFrame(speakingRaf)
  apply({ type: 'state', phase, level })
  if (phase === 'speaking') {
    // nível de voz sintético, parecido com fala
    const t0 = performance.now()
    const tick = () => {
      const t = (performance.now() - t0) / 1000
      const lvl = 0.35 + 0.3 * Math.sin(t * 9) * Math.sin(t * 2.3) + 0.25 * Math.random()
      apply({ type: 'state', phase: 'speaking', level: lvl })
      speakingRaf = requestAnimationFrame(tick)
    }
    speakingRaf = requestAnimationFrame(tick)
  }
}

function typeOut(role: 'user' | 'assistant', text: string, msPerWord: number, done?: () => void) {
  const words = text.split(' ')
  words.forEach((_, i) =>
    later(i * msPerWord, () =>
      apply({ type: 'transcript', role, text: words.slice(0, i + 1).join(' '), final: i === words.length - 1 }),
    ),
  )
  if (done) later(words.length * msPerWord, done)
}

function converse(userText: string | null, answer: string) {
  const respond = () => {
    setPhase('thinking')
    later(1600, () => {
      setPhase('speaking')
      typeOut('assistant', answer, 260, () => setPhase('idle'))
    })
  }
  if (userText === null) return respond()
  setPhase('listening')
  typeOut('user', userText, 220, () => later(300, respond))
}

const DEMOS: [string, string][] = [
  ['Jarvis, como está minha agenda hoje?', 'Você tem dois compromissos hoje. O próximo é a reunião de projeto às 14:00.'],
  ['Jarvis, resuma as notícias de tecnologia.', 'Separei doze manchetes de quatro fontes. Quer que eu leia as três principais?'],
  ['Jarvis, abra o Spotify.', 'Pronto, o Spotify está aberto.'],
]
let demoIdx = 0

function demoLoop() {
  const [q, a] = DEMOS[demoIdx++ % DEMOS.length]
  if (useJarvis.getState().phase === 'idle' && !useJarvis.getState().pttDown) converse(q, a)
  later(22000, demoLoop)
}

function telemetryLoop() {
  const t = useJarvis.getState().telemetry
  const walk = (v: number, lo: number, hi: number, step: number) =>
    Math.round(Math.min(hi, Math.max(lo, v + (Math.random() - 0.5) * step)))
  apply({ type: 'telemetry', ...t, cpu: walk(t.cpu, 8, 72, 12), ram: walk(t.ram, 48, 78, 4), disk: t.disk })
  later(2000, telemetryLoop)
}

function feedLoop() {
  const [kind, title, subtitle] = FEED_POOL[Math.floor(Math.random() * FEED_POOL.length)]
  apply({ type: 'feed', item: feedItem(kind, title, subtitle) })
  const m = useJarvis.getState().memory
  apply({ type: 'memory', ...m, memories: m.memories + Math.floor(Math.random() * 3), toolCalls: m.toolCalls + 1 })
  later(9000 + Math.random() * 6000, feedLoop)
}

export function startMock() {
  if (running) return
  running = true
  apply(mockSnapshot())
  later(2000, telemetryLoop)
  later(7000, feedLoop)
  later(4000, demoLoop)
}

export function stopMock() {
  running = false
  cancelAnimationFrame(speakingRaf)
  timers.forEach(clearTimeout)
  timers.clear()
}

/** Responde localmente ao que o painel enviaria ao daemon. */
export function mockHandle(msg: ClientMessage) {
  if (!running) return
  switch (msg.type) {
    case 'ptt':
      if (msg.down) setPhase('listening')
      else converse(null, 'Modo demonstração: conecte o daemon para eu ouvir de verdade.')
      break
    case 'say':
      apply({ type: 'transcript', role: 'user', text: msg.text, final: true })
      converse(null, `Entendido: “${msg.text}”. No modo demonstração eu só finjo executar.`)
      break
    case 'command':
      apply({ type: 'feed', item: feedItem('info', `Comando: ${msg.id}`, 'Executado em modo demonstração') })
      if (msg.id === 'briefing')
        converse(null, 'Bom dia. Você tem dois compromissos, doze manchetes novas e todos os sistemas estão normais.')
      break
  }
}
