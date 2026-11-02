import { AlertTriangle, FileUp, Table2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useJarvis } from '../store'
import type { DataResult } from '../types'
import { uploadFile } from '../upload'

// Série única: um tom só, sem legenda (o título diz o que é). #0891b2 passou no validador de paleta sobre o
// fundo dos painéis (#0a1626); o ciano da interface (#22d3ee) é claro demais para marca de dado no escuro.
const MARK = '#0891b2'
const SURFACE = '#0a1626'
const GRID = 'rgba(148, 163, 184, 0.18)'
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
      <figcaption className="mb-1 h-4 text-[11px] text-slate-300 tabular-nums">
        {show(linhas[h][rotulo])}: <span className="text-cyan-50">{show(linhas[h][valor])}</span>
      </figcaption>
      <ul role="img" aria-label={`${titulo(r)}, ${linhas.length} barras`} className="flex flex-col gap-[2px]">
        {linhas.map((l, i) => (
          <li
            key={i}
            onPointerEnter={() => setHover(i)}
            onPointerLeave={() => setHover(null)}
            title={`${show(l[rotulo])}: ${show(l[valor])}`}
            className="grid grid-cols-[minmax(0,7.5rem)_1fr] items-center gap-2 py-[3px]"
          >
            <span className={`truncate text-[11px] ${hover === i ? 'text-cyan-50' : 'text-slate-300'}`}>{show(l[rotulo])}</span>
            <span className="h-3 border-l" style={{ borderColor: GRID }}>
              <span
                className="block h-full rounded-r-[4px]"
                style={{ width: `${Math.max(((l[valor] as number) / max) * 100, 0.5)}%`, background: MARK,
                         opacity: hover === null || hover === i ? 1 : 0.55 }}
              />
            </span>
          </li>
        ))}
      </ul>
      {r.linhas.length > 12 && <p className="mt-1 text-[10px] text-slate-400">Mostrando 12 de {r.linhas.length}; todos na tabela.</p>}
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
      <figcaption className="mb-1 h-4 text-[11px] text-slate-300 tabular-nums">
        {show(pts[h][rotulo])}: <span className="text-cyan-50">{show(pts[h][valor])}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={`${titulo(r)}, ${pts.length} pontos`}>
        <line x1={P.l} x2={W - P.r} y1={y(0)} y2={y(0)} stroke={GRID} strokeWidth={1} />
        <line x1={P.l} x2={W - P.r} y1={y(max)} y2={y(max)} stroke={GRID} strokeWidth={1} />
        <polygon points={`${x(0)},${y(0)} ${linha} ${x(pts.length - 1)},${y(0)}`} fill={MARK} opacity={0.1} />
        <polyline points={linha} fill="none" stroke={MARK} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {hover !== null && <line x1={x(h)} x2={x(h)} y1={P.t} y2={y(0)} stroke={GRID} strokeWidth={1} />}
        <circle cx={x(h)} cy={y(pts[h][valor] as number)} r={4} fill={MARK} stroke={SURFACE} strokeWidth={2} />
        <text x={P.l} y={H - 4} fontSize={10} fill="#94a3b8">{show(pts[0][rotulo])}</text>
        <text x={W - P.r} y={H - 4} fontSize={10} fill="#94a3b8" textAnchor="end">{show(pts[pts.length - 1][rotulo])}</text>
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
      <h3 className="text-[12px] font-semibold text-cyan-50">{titulo(r)}</h3>
      {e && (e.tempo ? <Linha r={r} rotulo={e.rotulo} valor={e.valor} /> : <Barras r={r} rotulo={e.rotulo} valor={e.valor} />)}
      <div className="scroll-thin max-h-40 overflow-auto rounded border border-cyan-400/10">
        <table className="w-full text-[11px] tabular-nums">
          <thead className="sticky top-0 bg-[#0a1626] text-slate-400">
            <tr>{r.colunas.map((c) => <th key={c} className="px-2 py-1 text-left font-medium">{c}</th>)}</tr>
          </thead>
          <tbody className="text-slate-200">
            {r.linhas.map((l, i) => (
              <tr key={i} className="border-t border-cyan-400/5">
                {l.map((v, j) => <td key={j} className={`px-2 py-0.5 ${typeof v === 'number' ? 'text-right' : ''}`}>{show(v)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {r.grupos_omitidos_por_terem_menos_de_k_linhas > 0 && (
        <p className="text-[10.5px] text-slate-400">
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
    // o posicionamento fica num invólucro: o .glass (fora das camadas do Tailwind) força position: relative
    <div className="absolute top-[64px] right-3 z-30 w-[min(520px,calc(100vw-24px))]">
      <section
        id="dados"
        aria-label="Dados"
        tabIndex={-1}
        onKeyDown={(e) => e.key === 'Escape' && close()}
        // com a Conversa aberta (presa ao rodapé, até min(46vh, 420px)), o cartão termina acima dela
        className={`glass glass-solid flex flex-col gap-2 p-3 focus:outline-none ${
          chatOpen ? 'max-h-[max(220px,calc(100vh-min(46vh,420px)-170px))]' : 'max-h-[min(70vh,620px)]'
        }`}
      >
        <header className="flex shrink-0 items-center justify-between gap-2">
          <h2 className="card-title flex min-w-0 items-center gap-1.5">
            <Table2 size={12} /> Dados
            {data?.arquivo && <span className="truncate font-normal tracking-normal text-slate-300 normal-case">· {data.arquivo}</span>}
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

        {status && <p className="shrink-0 text-[11.5px] text-cyan-200" role="status">{status}</p>}

        <div className="scroll-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pr-1">
          {!data?.arquivo ? (
            <p className="py-4 text-center text-[11.5px] text-slate-400">
              Nenhum arquivo aberto. Diga “Jarvis, abre o arquivo vendas” ou solte um CSV no painel.
            </p>
          ) : (
            <>
              <p className="text-[11px] text-slate-400 tabular-nums">
                {fmt.format(data.linhas ?? 0)} linhas · {data.total_colunas} colunas · {data.codificacao}, separador “{data.separador}”
                {data.colunas.some((c) => c.dado_pessoal) &&
                  ` · dado pessoal protegido: ${data.colunas.filter((c) => c.dado_pessoal).map((c) => c.coluna).join(', ')}`}
              </p>
              {data.alertas.length > 0 && (
                <ul className="flex flex-col gap-0.5">
                  {data.alertas.slice(0, 5).map((a) => (
                    <li key={a} className="flex items-start gap-1.5 text-[11px] text-amber-200">
                      <AlertTriangle size={11} className="mt-[2px] shrink-0" aria-label="Alerta" /> {a}
                    </li>
                  ))}
                </ul>
              )}
              {(data.graficos?.length ?? 0) > 0 && (
                <div className="flex flex-col gap-1.5">
                  {data.graficos!.slice(0, 2).map((g) => (
                    <figure key={g.url} className="m-0">
                      {/* PNG do Python isolado, fundo claro como foi desenhado */}
                      <img src={`.${g.url}`} alt={g.titulo ?? 'Gráfico gerado pelo Python isolado'}
                           className="w-full rounded border border-cyan-400/10 bg-white" />
                    </figure>
                  ))}
                </div>
              )}
              {resultados.length > 1 && (
                <div role="tablist" aria-label="Últimos resultados" className="flex flex-wrap gap-1">
                  {resultados.map((r, i) => (
                    <button key={i} role="tab" tabIndex={0} aria-selected={atual === r} onClick={() => setSel(i)}
                            className={`max-w-[11rem] truncate rounded px-2 py-0.5 text-[10.5px] ${
                              atual === r ? 'bg-cyan-400/15 text-cyan-50' : 'text-slate-400 hover:text-slate-200'}`}>
                      {titulo(r)}
                    </button>
                  ))}
                </div>
              )}
              {atual ? <Resultado r={atual} /> : (
                <p className="text-[11.5px] text-slate-400">Pergunte algo sobre o arquivo: os totais aparecem aqui.</p>
              )}
            </>
          )}
          {kpis.length > 0 && (
            <section aria-label="Monitores de KPI" className="flex flex-col gap-1 border-t border-cyan-400/10 pt-2">
              <h3 className="card-title">Monitores</h3>
              <ul className="flex flex-col gap-1">
                {kpis.map((k) => (
                  <li key={k.nome} className="flex items-start gap-1.5 text-[11px]">
                    {k.ultimo?.disparou ? (
                      <AlertTriangle size={11} className="mt-[2px] shrink-0 text-amber-300" aria-label="Alerta" />
                    ) : (
                      <span className="mt-[5px] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" aria-label="Normal" />
                    )}
                    <span className={k.ultimo?.disparou ? 'text-amber-100' : 'text-slate-300'}>
                      {k.ultimo?.texto ?? `${k.nome}: aguardando a primeira conferência`}
                      <span className="text-slate-500"> · {k.arquivo}</span>
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
