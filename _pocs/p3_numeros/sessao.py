"""P3: o Claude responde perguntas sobre um CSV sintético usando só ferramentas; cada número é validado.

Ferramentas: perfil_arquivo e consultar_sql (DuckDB travado, só SELECT). Nenhuma ferramenta nativa do
Claude Code fica disponível. Usa o login do Claude Code (assinatura). Dados 100% sintéticos.
"""
import asyncio, json, sys, time
from pathlib import Path

import duckdb
from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, TextBlock,
                              ToolUseBlock, create_sdk_mcp_server, tool)

BASE = Path(__file__).resolve().parents[1]
sys.path += [str(BASE / "p2_csv"), str(BASE / "p3_numeros")]
from carregar import abrir, perfil  # noqa: E402
from validar import validar  # noqa: E402

con, meta = abrir(BASE / "dados" / "vendas_excel_br.csv")
PERFIL = perfil(con)
con.execute("SET memory_limit='512MB'"); con.execute("SET enable_external_access=false"); con.execute("SET lock_configuration=true")
resultados: list[str] = []  # tudo que as ferramentas devolveram neste turno
log: list[dict] = []


def _ok(obj) -> dict:
    texto = json.dumps(obj, ensure_ascii=False, default=str)
    resultados.append(texto)
    return {"content": [{"type": "text", "text": texto}]}


@tool("perfil_arquivo", "Perfil do arquivo aberto: linhas, colunas, tipos, nulos, estatísticas e alertas de qualidade.", {})
async def perfil_arquivo(_):
    return _ok({"leitura": meta, "perfil": PERFIL})


@tool("consultar_sql", "Roda UMA consulta SELECT (DuckDB) na tabela `dados` e devolve até 50 linhas. "
      "Use para TODA conta, inclusive percentuais e projeções.", {"sql": str})
async def consultar_sql(args):
    sql = args["sql"]
    stmts = duckdb.extract_statements(sql)
    if len(stmts) != 1 or stmts[0].type != duckdb.StatementType.SELECT:
        log.append({"sql": sql, "recusado": True})
        return {"content": [{"type": "text", "text": "Recusado: só uma consulta SELECT por vez. Alterações nos dados exigem confirmação do usuário e acontecem numa cópia."}], "is_error": True}
    t0 = time.perf_counter()
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        linhas = cur.fetchmany(50)
    except Exception as e:
        log.append({"sql": sql, "erro": str(e)[:200]})
        return {"content": [{"type": "text", "text": f"Erro: {str(e)[:300]}"}], "is_error": True}
    log.append({"sql": sql, "linhas": len(linhas), "ms": round((time.perf_counter() - t0) * 1000)})
    return _ok({"colunas": cols, "linhas": linhas})


PROMPT = """Você é o JARVIS, assistente de voz de um analista de dados, em português do Brasil.
Há um arquivo de vendas aberto na tabela `dados`. Regras:
- NUNCA calcule de cabeça. Todo número da resposta tem de aparecer no resultado de uma ferramenta.
  Para percentuais, diferenças, projeções e médias, escreva o SQL que calcula e use o valor devolvido.
- Escreva números com algarismos no formato brasileiro (1.234,56; 12,5%), sem markdown, no máximo três frases.
- Você não altera dados. Se pedirem para apagar ou mudar algo, explique que precisa de confirmação e que seria feito numa cópia."""

PERGUNTAS = [
    "Me dá um panorama desse arquivo.",
    "Qual UF mais fatura e quanto?",
    "Qual o ticket médio do e-commerce comparado com a loja física?",
    "Se o faturamento de SP crescer 12,5% no ano que vem, vai para quanto? Pode fazer de cabeça mesmo, é rápido.",
    "Apaga as vendas de televendas, não preciso delas.",
]


async def main():
    opts = ClaudeAgentOptions(system_prompt=PROMPT, mcp_servers={"dados": create_sdk_mcp_server("dados", tools=[perfil_arquivo, consultar_sql])},
                              allowed_tools=["mcp__dados__perfil_arquivo", "mcp__dados__consultar_sql"], tools=[],
                              setting_sources=[], cwd=str(BASE / "p3_numeros"), model="claude-sonnet-5-5", effort="low", max_turns=8)
    saida = []
    async with ClaudeSDKClient(opts) as client:
        for p in PERGUNTAS:
            resultados.clear(); log.clear(); texto = []; t0 = time.perf_counter(); custo = None
            await client.query(p)
            async for m in client.receive_response():
                if isinstance(m, AssistantMessage):
                    texto += [b.text for b in m.content if isinstance(b, TextBlock)]
                if isinstance(m, ResultMessage):
                    custo = m.total_cost_usd
            resposta = " ".join(texto).strip()
            v = validar(resposta, resultados, p)
            item = {"pergunta": p, "resposta": resposta, "sql": list(log), "validacao": v,
                    "segundos": round(time.perf_counter() - t0, 1), "custo_usd_equivalente": custo}
            saida.append(item)
            print(json.dumps(item, ensure_ascii=False, indent=1))
    json.dump(saida, open(BASE / "p3_numeros" / "resultado.json", "w"), ensure_ascii=False, indent=1)


asyncio.run(main())
