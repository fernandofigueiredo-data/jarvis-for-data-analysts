"""Monitor de KPIs: uma métrica de um arquivo, uma regra e um alerta falado quando ela dispara.

A conferência roda num laço do daemon, sem o Claude: o arquivo é lido localmente (a versão mais recente com aquele
nome nas pastas permitidas), a métrica sai do mesmo montador de SQL do `agregar` (grupos < K omitidos) e o texto do
alerta é montado aqui. O Claude só participa ao criar o monitor, a pedido do usuário.

Regras:
- queda_pct / alta_pct: o último período contra a média dos `janela` anteriores (exige 'por' com período de data).
- abaixo / acima: o último valor contra um limite fixo.
Por padrão o período em curso (o mês ou o dia de hoje, ainda aberto) fica de fora, para não alarmar à toa.
"""
import json
import time

from jarvis import config, dados
from jarvis.memory import memory

TIPOS = {"queda_pct", "alta_pct", "abaixo", "acima"}
PERIODO_ATUAL = {"dia": "%Y-%m-%d", "mes": "%Y-%m", "ano": "%Y"}


def br(v: float) -> str:
    s = f"{v:,.2f}" if abs(v) < 1e6 else f"{v:,.0f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",00")


def falar_periodo(rotulo: str) -> str:
    """2026-11-01 -> 01/11/2026; 2026-11 -> 11/2026; o resto como veio."""
    if len(rotulo) == 10 and rotulo[4] == rotulo[7] == "-":
        return f"{rotulo[8:]}/{rotulo[5:7]}/{rotulo[:4]}"
    if len(rotulo) == 7 and rotulo[4] == "-":
        return f"{rotulo[5:]}/{rotulo[:4]}"
    return "no total" if rotulo == "total" else rotulo


def validar_kpi(kpi: dict) -> None:
    regra, por = kpi.get("regra") or {}, kpi.get("por") or []
    if regra.get("tipo") not in TIPOS:
        raise dados.Recusa(f"regra precisa de tipo: {', '.join(sorted(TIPOS))}")
    if not isinstance(regra.get("valor"), (int, float)):
        raise dados.Recusa("regra precisa de um valor numérico (percentual ou limite)")
    if len(por) > 1 or (por and ":" not in por[0]):
        raise dados.Recusa("'por' aceita no máximo um período de data, como 'data_venda:mes'")
    if regra["tipo"] in ("queda_pct", "alta_pct") and not por:
        raise dados.Recusa("queda_pct e alta_pct comparam períodos: informe 'por' com um período de data")
    if not (kpi.get("metrica") or {}).get("funcao"):
        raise dados.Recusa("informe a métrica (funcao e coluna)")


def avaliar(kpi: dict) -> dict:
    """Lê o arquivo, calcula a série e aplica a regra. Não fala nem grava: quem chama decide."""
    candidatos = dados.localizar(kpi["arquivo"])
    if not candidatos:
        raise dados.Recusa(f"arquivo {kpi['arquivo']!r} não está mais nas pastas permitidas")
    con, _ = dados.carregar(candidatos[0])
    try:
        sql = dados.montar_sql({"metricas": [kpi["metrica"]], "por": kpi.get("por") or [],
                                "filtros": kpi.get("filtros") or []}, dados.colunas(con), dados.colunas_pessoais(con))
        linhas = [r for r in con.execute(sql).fetchall() if r[-1] >= config.K_ANONIMATO]
    finally:
        con.close()
    regra, por = kpi["regra"], kpi.get("por") or []
    serie = sorted((str(r[0]), r[1]) for r in linhas) if por else [("total", linhas[0][0])] if linhas else []
    periodo = por[0].partition(":")[2] if por else ""
    if por and regra.get("ignorar_periodo_aberto", True) and periodo in PERIODO_ATUAL:
        aberto = time.strftime(PERIODO_ATUAL[periodo])
        serie = [p for p in serie if p[0] != aberto]
    serie = [p for p in serie if p[1] is not None]
    if not serie:
        return {"valor": None, "disparou": False, "texto": f"{kpi['nome']}: sem dados para conferir"}
    rotulo, valor = serie[-1]
    out = {"periodo": rotulo, "valor": valor, "arquivo": candidatos[0].name}
    falado = falar_periodo(rotulo)
    tipo, limite = regra["tipo"], float(regra["valor"])
    if tipo in ("queda_pct", "alta_pct"):
        janela = max(1, int(regra.get("janela") or 4))
        anteriores = [v for _, v in serie[-janela - 1:-1]]
        if not anteriores:
            return {**out, "disparou": False, "texto": f"{kpi['nome']}: só há um período, nada a comparar"}
        base = sum(anteriores) / len(anteriores)
        var = (valor / base - 1) * 100 if base else 0.0
        disparou = var <= -limite if tipo == "queda_pct" else var >= limite
        sentido = "abaixo" if var < 0 else "acima"
        texto = (f"{kpi['nome']}: {br(valor)} em {falado}, {br(abs(var))}% {sentido} da média dos "
                 f"{len(anteriores)} períodos anteriores ({br(base)})")
        out |= {"base": base, "variacao_pct": round(var, 2)}
    else:
        disparou = valor < limite if tipo == "abaixo" else valor > limite
        quando = falado if rotulo == "total" else f"em {falado}"
        sentido = "abaixo" if valor < limite else "acima"
        texto = f"{kpi['nome']}: {br(valor)} {quando}, {sentido} do limite de {br(limite)}"
    return {**out, "disparou": disparou, "texto": texto}


def criar(kpi: dict) -> dict:
    validar_kpi(kpi)
    atual = avaliar(kpi)  # falha cedo: coluna errada, arquivo fora das pastas
    memory.kpi_salvar(kpi["nome"], json.dumps(kpi, ensure_ascii=False))
    # o usuário ouve o estado de agora na resposta: o laço só fala de novo num período seguinte
    chave = f"{atual.get('arquivo')}|{atual.get('periodo')}" if atual["disparou"] else None
    memory.kpi_resultado(kpi["nome"], json.dumps({**atual, "conferido": time.time()}, ensure_ascii=False, default=str), chave)
    return atual


def listar() -> list[dict]:
    return [{**json.loads(k), "ultimo": json.loads(u) if u else None} for _, k, u, _ in memory.kpis()]


def conferir_todos() -> list[dict]:
    """Avalia cada monitor; devolve os alertas novos (um por período, para não repetir a cada hora)."""
    novos = []
    for nome, k, _, ultimo_alerta in memory.kpis():
        kpi = json.loads(k)
        try:
            r = avaliar(kpi)
        except Exception as exc:  # arquivo sumiu, coluna mudou: vira aviso, não derruba o laço
            r = {"erro": str(exc)[:160], "disparou": False, "texto": f"{nome}: não consegui conferir"}
        chave = f"{r.get('arquivo')}|{r.get('periodo')}"
        memory.kpi_resultado(nome, json.dumps({**r, "conferido": time.time()}, ensure_ascii=False, default=str),
                             chave if r["disparou"] else ultimo_alerta)
        if r["disparou"] and chave != ultimo_alerta:
            novos.append({"nome": nome, **r})
    return novos
