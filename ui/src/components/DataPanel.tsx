import { AlertTriangle, FileUp, Table2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useJarvis } from '../store'
import type { DataResult } from '../types'
import { uploadFile } from '../upload'
import { alpha, C } from './ui'

// Série única: a primeira cor da ordem categórica do design system (Ciano → Verde → Roxo → Âmbar), sem legenda
// (o título diz o que é). O painel flutua na camada 3 (Grafite secundário).
const MARK = C.primary
const SURFACE = C.raised
const GRID = alpha(C.muted, 30)
const PERIODO = /_(mes|ano|dia|trimestre|dia_semana)$/

const fmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 })
const show = (v: string | number | null) => (v === null ? '—' : typeof v === 'number' ? fmt.format(v) : v)

const FUNCAO: Record<string, string> = {
  soma: 'Soma', media: 'Média', mediana: 'Mediana', desvio: 'Desvio', minimo: 'Mínimo', maximo: 'Máximo',
  p25: 'P25', p75: 'P75', p90: 'P90', contagem: 'Contagem', distintos: 'Distintos', participacao_pct: 'Participação %',
}

/** "Soma de valor_total por uf" a partir do pedido que o Claude fez. */
function titulo(r: DataResult) {
  const m = r.pedido.metricas?.[0]
  const met = m ? `${FUNCAO[m.funcao] ?? m.funcao}${m.coluna ? ` de ${m.coluna}` : ' de linhas'}` : 'Contagem'
  const por = r.pedido.por?.length ? ` por ${r.pedido.por.join(', ').replace(/:/g, ' · ')}` : ''
  return met + por
}

/** Coluna de rótulo (texto/período) e a primeira métrica numérica; sem as duas, só a tabela. */
function eixos(r: DataResult) {
  if (r.linhas.length < 2) return null
  const rotulo = r.colunas.findIndex((_, i) => r.linhas.every((l) => typeof l[i] === 'string' || l[i] === null))
  const metricas = r.colunas.map((_, i) => i).filter((i) => i !== rotulo && r.linhas.every((l) => typeof l[i] === 'number'))
  const valor = metricas.find((i) => r.colunas[i] !== 'linhas_no_grupo') ?? metricas[0]
  if (rotulo < 0 || valor === undefined || r.linhas.some((l) => (l[valor] as number) < 0)) return null
  return { rotulo, valor, tempo: PERIODO.test(r.colunas[rotulo]) }
}

function Barras({ r, rotulo, valor }: { r: DataResult; rotulo: number; valor: number }) {
  const linhas = r.linhas.slice(0, 12)
  const max = Math.max(...linhas.map((l) => l[valor] as number), 0) || 1
  const [hover, setHover] = useState<number | null>(null)
  const h = hover ?? 0
  return (
    <figure className="m-0">
      {/* leitura do item sob o mouse (ou o primeiro): um número de cada vez, não um em cada barra */}
      <figcaption className="mb-1 text-xs text-text-secondary">
        {show(linhas[h][rotulo])}: <span className="font-mono text-text-primary tabular-nums">{show(linhas[h][valor])}</span>
      </figcaption>
      <ul role="img" aria-label={`${titulo(r)}, ${linhas.length} barras`} className="flex flex-col gap-1">
        {linhas.map((l, i) => (
          <li
            key={i}
            onPointerEnter={() => setHover(i)}
            onPointerLeave={() => setHover(null)}
            title={`${show(l[rotulo])}: ${show(l[valor])}`}
            className="grid grid-cols-[minmax(0,7.5rem)_1fr] items-center gap-2"
          >
            <span className={`truncate text-xs ${hover === i ? 'text-text-primary' : 'text-text-secondary'}`}>{show(l[rotulo])}</span>
            <span className="h-3 border-l" style={{ borderColor: GRID }}>
              <span
                className="block h-full rounded-r-base"
                style={{ width: `${Math.max(((l[valor] as number) / max) * 100, 0.5)}%`, background: MARK,
                         opacity: hover === null || hover === i ? 1 : 0.55 }}
              />
            </span>
          </li>
        ))}
      </ul>
      {r.linhas.length > 12 && <p className="mt-1 text-xs text-text-secondary">Mostrando 12 de {r.linhas.length}; todos na tabela.</p>}
    </figure>
  )
}

function Linha({ r, rotulo, valor }: { r: DataResult; rotulo: number; valor: number }) {
  const pts = useMemo(() => [...r.linhas].sort((a, b) => String(a[rotulo]).localeCompare(String(b[rotulo]))), [r, rotulo])
  const [hover, setHover] = useState<number | null>(null)
  const W = 480, H = 130, P = { l: 8, r: 8, t: 10, b: 18 }
  const max = Math.max(...pts.map((p) => p[valor] as number), 0) || 1
  const x = (i: number) => P.l + (pts.length === 1 ? 0 : (i * (W - P.l - P.r)) / (pts.length - 1))
  const y = (v: number) => H - P.b - (v / max) * (H - P.t - P.b)
  const linha = pts.map((p, i) => `${x(i)},${y(p[valor] as number)}`).join(' ')
  const h = hover ?? pts.length - 1 // sem mouse, lê o último ponto
  return (
    <figure className="m-0">
      <figcaption className="mb-1 text-xs text-text-secondary">
        {show(pts[h][rotulo])}: <span className="font-mono text-text-primary tabular-nums">{show(pts[h][valor])}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={`${titulo(r)}, ${pts.length} pontos`}>
        <line x1={P.l} x2={W - P.r} y1={y(0)} y2={y(0)} stroke={GRID} strokeWidth={1} />
        <line x1={P.l} x2={W - P.r} y1={y(max)} y2={y(max)} stroke={GRID} strokeWidth={1} />
        <polygon points={`${x(0)},${y(0)} ${linha} ${x(pts.length - 1)},${y(0)}`} fill={MARK} opacity={0.1} />
        <polyline points={linha} fill="none" stroke={MARK} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {hover !== null && <line x1={x(h)} x2={x(h)} y1={P.t} y2={y(0)} stroke={GRID} strokeWidth={1} />}
        <circle cx={x(h)} cy={y(pts[h][valor] as number)} r={4} fill={MARK} stroke={SURFACE} strokeWidth={2} />
        <text x={P.l} y={H - 4} fontSize={12.8} fill={C.muted} fontFamily="var(--font-family-mono)">{show(pts[0][rotulo])}</text>
        <text x={W - P.r} y={H - 4} fontSize={12.8} fill={C.muted} fontFamily="var(--font-family-mono)" textAnchor="end">{show(pts[pts.length - 1][rotulo])}</text>
        {/* alvos de hover maiores que o ponto: uma faixa vertical por ponto */}
        {pts.map((_, i) => (
          <rect key={i} x={x(i) - (W - P.l - P.r) / Math.max(pts.length - 1, 1) / 2} y={0}
                width={(W - P.l - P.r) / Math.max(pts.length - 1, 1)} height={H} fill="transparent"
                onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} />
        ))}
      </svg>
    </figure>
  )
}

function Resultado({ r }: { r: DataResult }) {
  const e = eixos(r)
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-text-primary">{titulo(r)}</h3>
      {e && (e.tempo ? <Linha r={r} rotulo={e.rotulo} valor={e.valor} /> : <Barras r={r} rotulo={e.rotulo} valor={e.valor} />)}
      <div className="scroll-thin max-h-40 overflow-auto rounded-base border border-text-secondary/30">
        <table className="w-full text-xs tabular-nums">
          <thead className="sticky top-0 bg-surface-raised text-text-secondary">
            <tr>{r.colunas.map((c) => <th key={c} className="px-2 py-1 text-left font-medium">{c}</th>)}</tr>
          </thead>
          <tbody className="text-text-primary">
            {r.linhas.map((l, i) => (
              <tr key={i} className="border-t border-text-secondary/30">
                {l.map((v, j) => <td key={j} className={`px-2 py-1 ${typeof v === 'number' ? 'text-right font-mono' : ''}`}>{show(v)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {r.grupos_omitidos_por_terem_menos_de_k_linhas > 0 && (
        <p className="text-xs text-text-secondary">
          {fmt.format(r.grupos_omitidos_por_terem_menos_de_k_linhas)} grupo(s) com menos de {r.k} linhas omitido(s) por privacidade.
        </p>
      )}
    </div>
  )
}

/** Arquivo aberto e últimos agregados: o mesmo que o Claude viu, nada de linha crua. Abre sozinho a cada resultado. */
export default function DataPanel() {
  const open = useJarvis((s) => s.dataOpen)
  const data = useJarvis((s) => s.data)
  const status = useJarvis((s) => s.uploadStatus)
  const chatOpen = useJarvis((s) => s.chatOpen)
  const kpis = useJarvis((s) => s.kpis)
  const [sel, setSel] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const close = () => useJarvis.getState().setDataOpen(false)
  const resultados = data?.resultados ?? []
  const atual = resultados[Math.min(sel, resultados.length - 1)]
  useEffect(() => setSel(0), [resultados[0]]) // resultado novo entra selecionado

  if (!open) return null
  return (
    // o posicionamento fica num invólucro: o .card (fora das camadas do Tailwind) força position: relative
    <div className="absolute top-16 right-3 z-30 w-[min(520px,calc(100vw-24px))]">
      <section
        id="dados"
        aria-label="Dados"
        tabIndex={-1}
        onKeyDown={(e) => e.key === 'Escape' && close()}
        // com a Conversa aberta (presa ao rodapé, até min(46vh, 420px)), o cartão termina acima dela
        className={`card card-raised flex flex-col gap-2 p-4 focus:outline-none ${
          chatOpen ? 'max-h-[max(220px,calc(100vh-min(46vh,420px)-170px))]' : 'max-h-[min(70vh,620px)]'
        }`}
      >
        <header className="flex shrink-0 items-center justify-between gap-2">
          <h2 className="card-title flex min-w-0 items-center gap-2">
            <Table2 size={12} className="text-data" /> Dados
            {data?.arquivo && <span className="truncate font-mono font-normal tracking-normal text-text-primary normal-case">· {data.arquivo}</span>}
          </h2>
          <div className="flex items-center gap-1">
            <button tabIndex={0} onClick={() => input.current?.click()} className="icon-btn" aria-label="Enviar arquivo CSV"
                    title="Enviar CSV (ou solte o arquivo no painel)">
              <FileUp size={15} />
            </button>
            <button tabIndex={0} onClick={close} aria-label="Fechar dados" className="icon-btn">
              <X size={15} />
            </button>
          </div>
          <input ref={input} type="file" accept=".csv,.tsv" hidden
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadFile(f); e.target.value = '' }} />
        </header>

        {status && <p className="shrink-0 text-xs text-text-primary" role="status">{status}</p>}

        <div className="scroll-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1">
          {!data?.arquivo ? (
            <p className="py-4 text-center text-xs text-text-secondary">
              Nenhum arquivo aberto. Diga “Jarvis, abre o arquivo vendas” ou solte um CSV no painel.
            </p>
          ) : (
            <>
              <p className="text-xs text-text-secondary tabular-nums">
                {fmt.format(data.linhas ?? 0)} linhas · {data.total_colunas} colunas · {data.codificacao}, separador “{data.separador}”
                {data.colunas.some((c) => c.dado_pessoal) &&
                  ` · dado pessoal protegido: ${data.colunas.filter((c) => c.dado_pessoal).map((c) => c.coluna).join(', ')}`}
              </p>
              {data.alertas.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {data.alertas.slice(0, 5).map((a) => (
                    <li key={a} className="flex items-start gap-2 text-xs text-warning">
                      <AlertTriangle size={12} className="mt-1 shrink-0" aria-label="Alerta" /> {a}
                    </li>
                  ))}
                </ul>
              )}
              {(data.graficos?.length ?? 0) > 0 && (
                <div className="flex flex-col gap-2">
                  {data.graficos!.slice(0, 2).map((g) => (
                    <figure key={g.url} className="m-0">
                      {/* PNG do Python isolado, como o matplotlib desenhou */}
                      <img src={`.${g.url}`} alt={g.titulo ?? 'Gráfico gerado pelo Python isolado'}
                           className="w-full rounded-base border border-text-secondary/30" />
                    </figure>
                  ))}
                </div>
              )}
              {resultados.length > 1 && (
                <div role="tablist" aria-label="Últimos resultados" className="flex flex-wrap gap-1">
                  {resultados.map((r, i) => (
                    <button key={i} role="tab" tabIndex={0} aria-selected={atual === r} onClick={() => setSel(i)}
                            className={`max-w-[11rem] truncate rounded-base border px-2 text-xs transition-colors ${
                              atual === r ? 'border-primary/30 bg-primary/15 text-primary'
                                : 'border-transparent text-text-secondary hover:border-primary'}`}>
                      {titulo(r)}
                    </button>
                  ))}
                </div>
              )}
              {atual ? <Resultado r={atual} /> : (
                <p className="text-xs text-text-secondary">Pergunte algo sobre o arquivo: os totais aparecem aqui.</p>
              )}
            </>
          )}
          {kpis.length > 0 && (
            <section aria-label="Monitores de KPI" className="flex flex-col gap-1 border-t border-text-secondary/30 pt-2">
              <h3 className="card-title">Monitores</h3>
              <ul className="flex flex-col gap-1">
                {kpis.map((k) => (
                  <li key={k.nome} className="flex items-start gap-2 text-xs">
                    {k.ultimo?.disparou ? (
                      <AlertTriangle size={12} className="mt-1 shrink-0 text-warning" aria-label="Alerta" />
                    ) : (
                      <span className="mt-1 inline-block h-2 w-2 shrink-0 rounded-full bg-success" aria-label="Normal" />
                    )}
                    <span className={k.ultimo?.disparou ? 'text-warning' : 'text-text-primary'}>
                      {k.ultimo?.texto ?? `${k.nome}: aguardando a primeira conferência`}
                      <span className="font-mono text-text-secondary"> · {k.arquivo}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </section>
    </div>
  )
}
