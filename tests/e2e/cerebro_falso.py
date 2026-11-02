"""Cérebro falso dos testes de ponta a ponta: mesma interface do `jarvis.brain.agent.Brain`, sem chamar o Claude.

O Claude é um serviço pago, então os testes não o usam. Cada pergunta escolhe uma cena pelo texto; as cenas que
precisam de dados chamam as ferramentas de verdade do Jarvis (`jarvis.brain.tools`), e o painel recebe os mesmos
eventos de um turno real (arquivo aberto, agregados, gráficos, monitores, itens do feed).
"""
import asyncio
import json
import re
from collections.abc import Callable

from jarvis.brain import tools
from jarvis.brain.agent import BrainError
from jarvis.memory import memory

SERVIDOR = {t.name: srv for srv, lista in (("mac", tools.MAC_TOOLS), ("jarvis", tools.JARVIS_TOOLS),
                                             ("dados", tools.DADOS_TOOLS)) for t in lista}

GRAFICO = """import matplotlib.pyplot as plt
plt.hist(df["valor"].dropna(), bins=12)
plt.xlabel("valor")
grafico("valor")
resultado("media_valor", round(float(df["valor"].mean()), 2))
"""

MONITOR = {"nome": "Faturamento mensal", "arquivo": "vendas_teste",
           "metrica": {"funcao": "soma", "coluna": "valor"}, "por": ["data_venda:mes"],
           "regra": {"tipo": "queda_pct", "valor": 10, "janela": 3}}


def br(v: float) -> str:
    """12345.6 -> '12.345,60' (como o Claude escreveria em português)."""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class CerebroFalso:
    fora_do_ar = False  # o daemon_teste liga com --cerebro-fora: start() e ask() falham como sem login

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.cancelled = False
        self.client: object | None = None
        self._partes: list[str] = []
        self._on_text: Callable[[str], None] = lambda d: None
        self._on_tool: Callable[[str], None] = lambda n: None

    async def start(self) -> None:
        if self.fora_do_ar:
            raise BrainError("Claude Code sem login (simulado pelo teste)")
        self.client = object()

    async def stop(self) -> None:
        self.client = None

    async def reset(self) -> None:
        await self.stop()
        await self.start()

    async def cancel(self) -> None:
        if self.lock.locked():
            self.cancelled = True

    async def ask(self, text: str, on_text: Callable[[str], None] = lambda d: None,
                  on_tool: Callable[[str], None] = lambda n: None) -> str:
        async with self.lock:  # um turno por vez, como o Brain
            if self.client is None:
                await self.start()
            self.cancelled = False
            self._partes, self._on_text, self._on_tool = [], on_text, on_tool
            await asyncio.sleep(0.3)  # o Claude nunca responde na hora: dá para ver a fase "pensando"
            for padrao, cena in CENAS:
                if m := re.search(padrao, text, re.I):
                    await cena(self, text, m)
                    break
            return "".join(self._partes).strip()

    # ------------------------------------------------------------------ peças das cenas
    async def falar(self, texto: str, pausa: float = 0.04) -> None:
        """Texto em pedaços (palavra a palavra), como o streaming do Claude; para no barge-in."""
        for pedaco in re.findall(r"\S+\s*", texto):
            if self.cancelled:
                return
            self._partes.append(pedaco)
            self._on_text(pedaco)
            await asyncio.sleep(pausa)

    async def usar(self, nome: str, args: dict) -> tuple[dict | str, bool]:
        """Chama a ferramenta de verdade; devolve o resultado (JSON já lido, quando for JSON) e se deu erro."""
        memory.bump("tool_calls")
        self._on_tool(f"mcp__{SERVIDOR[nome]}__{nome}")
        out = await getattr(tools, nome).handler(args)
        texto = out["content"][0]["text"]
        try:
            return json.loads(texto), bool(out.get("is_error"))
        except ValueError:
            return texto, bool(out.get("is_error"))


# ------------------------------------------------------------------ cenas
async def erro(c: CerebroFalso, _t, _m) -> None:
    raise BrainError("API Error: 529 Overloaded (erro simulado pelo teste)")


async def longa(c: CerebroFalso, _t, _m) -> None:
    frases = [f"Esta é a frase número {n} de uma resposta longa." for n in
              ("um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze")]
    await c.falar(" ".join(frases), pausa=0.12)


async def abrir(c: CerebroFalso, _t, m) -> None:
    r, falhou = await c.usar("abrir_arquivo", {"nome": m[1].strip()})
    if falhou:
        await c.falar(f"Não consegui abrir esse arquivo, senhor: {r}.")
        return
    await c.falar(f"Abri o {r['arquivo']}: {r['linhas']} linhas e {r['total_colunas']} colunas, senhor. "
                  "Os alertas de qualidade estão no painel.")


async def briefing(c: CerebroFalso, _t, _m) -> None:
    agenda, _ = await c.usar("agenda_today", {})
    await c.usar("timer_list", {})
    noticias, _ = await c.usar("news_digest", {})
    await c.usar("arquivos_recentes", {})
    proximo = next((e["title"] for e in agenda if e["status"].startswith("Em")), None) if isinstance(agenda, list) else None
    texto = "Bom dia, senhor. " + (f"O próximo compromisso é {proximo}. " if proximo else "Agenda livre. ")
    if isinstance(noticias, list) and noticias:
        texto += f"Destaque do dia: {noticias[0]['titulo']}. Os links estão no feed."
    await c.falar(texto)


async def resumo_noticias(c: CerebroFalso, _t, _m) -> None:
    itens, _ = await c.usar("news_digest", {})
    if not isinstance(itens, list):
        await c.falar("Nenhuma notícia nova, senhor.")
        return
    titulos = [i["titulo"] for i in itens[:3]]
    await c.falar("Três destaques de dados: " + "; ".join(titulos) + ". Os links estão no feed.")


async def noticias(c: CerebroFalso, _t, _m) -> None:
    grupos, _ = await c.usar("news_latest", {})
    if not isinstance(grupos, dict):
        await c.falar(f"{grupos}")
        return
    fonte, itens = next(iter(grupos.items()))
    await c.falar(f"Na {fonte}, a manchete mais recente é: {itens[0]['title']}.")


async def agenda(c: CerebroFalso, _t, _m) -> None:
    eventos, _ = await c.usar("agenda_today", {})
    if isinstance(eventos, str) and "sendo lida" in eventos:  # o Calendário ainda não respondeu
        await c.falar("A agenda ainda está sendo lida do Calendário, senhor. Pergunte de novo em um minuto.")
        return
    if not isinstance(eventos, list) or not eventos:
        await c.falar("Nenhum compromisso hoje, senhor.")
        return
    await c.falar("Hoje o senhor tem: " + "; ".join(f"{e['title']} ({e['status']})" for e in eventos) + ".")


async def tarefa(c: CerebroFalso, _t, _m) -> None:
    await c.falar("Qual é a tarefa, senhor?")


async def timers(c: CerebroFalso, _t, _m) -> None:
    r, _ = await c.usar("timer_list", {})
    await c.falar(f"{r}")


async def por_uf(c: CerebroFalso, _t, _m) -> None:
    r, falhou = await c.usar("agregar", {"metricas": [{"funcao": "soma", "coluna": "valor"}], "por": ["uf"],
                                         "ordenar": "-soma_valor"})
    if falhou:
        await c.falar(f"Não consegui calcular, senhor: {r}.")
        return
    uf, valor = r["linhas"][0][0], r["linhas"][0][1]
    await c.falar(f"{uf} lidera o faturamento com R$ {br(valor)}, senhor.")


async def por_mes(c: CerebroFalso, _t, _m) -> None:
    r, falhou = await c.usar("agregar", {"metricas": [{"funcao": "soma", "coluna": "valor"}],
                                         "por": ["data_venda:mes"]})
    if falhou:
        await c.falar(f"Não consegui calcular, senhor: {r}.")
        return
    melhor = max(r["linhas"], key=lambda linha: linha[1])
    await c.falar(f"O melhor mês teve R$ {br(melhor[1])}. A série completa está no painel.")


async def inventado(c: CerebroFalso, _t, _m) -> None:
    await c.usar("agregar", {"metricas": [{"funcao": "contagem"}], "por": ["canal"]})
    await c.falar("Somando tudo, o faturamento chegou a 987.654,32 reais, senhor.")


async def grafico(c: CerebroFalso, _t, _m) -> None:
    r, falhou = await c.usar("executar_python", {"codigo": GRAFICO})
    if falhou or r.get("erro"):
        await c.falar(f"O Python isolado falhou, senhor: {r if falhou else r['erro']}.")
        return
    await c.falar(f"O gráfico da distribuição está no painel. A média é R$ {br(r['resultados']['media_valor'])}.")


async def monitor(c: CerebroFalso, _t, _m) -> None:
    r, falhou = await c.usar("kpi_criar", MONITOR)
    await c.falar(f"Não consegui criar o monitor, senhor: {r}." if falhou else
                  "Monitor criado, senhor. Confiro de hora em hora e aviso se cair.")


async def comparar(c: CerebroFalso, _t, _m) -> None:
    r, falhou = await c.usar("comparar_arquivo", {"nome": "vendas_teste_v2"})
    await c.falar(f"Não consegui comparar, senhor: {r}." if falhou else
                  f"A versão nova tem {r['linhas_so_em_b']} linhas novas e {r['linhas_so_em_a']} removidas.")


async def capital(c: CerebroFalso, _t, _m) -> None:
    await c.falar("A capital da Austrália é Camberra, senhor.")


async def padrao(c: CerebroFalso, t, _m) -> None:
    await c.falar(f"Certo, senhor. Anotei: {t.strip().rstrip('.?!')}.")


CENAS: list[tuple[str, Callable]] = [
    (r"simul\w* (?:um )?erro", erro),
    (r"resposta longa", longa),
    (r"abr[aei]\w* o arquivo (.+?)(?: com abrir_arquivo|[.?!]*$)", abrir),
    (r"briefing", briefing),
    (r"resumo de not[ií]cias", resumo_noticias),
    (r"not[ií]cias|manchetes", noticias),
    (r"agenda", agenda),
    (r"criar uma tarefa", tarefa),
    (r"lista de timers", timers),
    (r"\buf\b", por_uf),
    (r"por m[eê]s", por_mes),
    (r"inventad", inventado),
    (r"gr[aá]fico|distribui", grafico),
    (r"monitor|me avisa", monitor),
    (r"compar", comparar),
    (r"capital da austr", capital),
    (r".", padrao),
]
