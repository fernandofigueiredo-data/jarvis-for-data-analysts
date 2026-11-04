"""P5: carrega o plugin analise-dados pelo Agent SDK, como o Jarvis faria, e mede o que funciona.

Turno 1 (setting_sources=[] como no Jarvis): plugin carrega? Jupyter MCP executa célula? hook dispara?
Turno 2 (setting_sources=[]): a regra deny Read(./.env) do projeto vale?
Turno 3 (setting_sources=["project"]): idem, com as configurações do projeto carregadas.
O token do Jupyter é lido do arquivo e nunca impresso.
"""
import asyncio, json, re, sys, time
from pathlib import Path
from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow,
                              PermissionResultDeny, ResultMessage, SystemMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage)

PROJ = Path(__file__).resolve().parent / "proj"
PLUGIN = "/Users/fernandofigueiredo/.claude/plugins/cache/analise-dados/analise-dados/1.1.0"
TOKEN = (PROJ / ".runtime/jupyter.token").read_text().strip()
PORTA = (PROJ / ".runtime/jupyter.port").read_text().strip()
def limpa(s: str) -> str:
    return s.replace(TOKEN, "<token>")

eventos: list[dict] = []
async def pode(nome, entrada, _ctx):
    ok = nome.startswith("mcp__plugin_analise-dados_jupyter__") or nome == "Read"
    eventos.append({"permissao": nome, "liberada": ok})
    return PermissionResultAllow() if ok else PermissionResultDeny(message="fora do escopo da PoC")


async def turno(opts, prompt, rotulo):
    out = {"rotulo": rotulo, "ferramentas": [], "sistema": [], "texto": ""}
    t0 = time.perf_counter()
    async with ClaudeSDKClient(opts) as c:
        await c.query(prompt)
        async for m in c.receive_response():
            if isinstance(m, SystemMessage):
                if m.subtype == "init":
                    d = m.data
                    out["init"] = {"plugins": d.get("plugins"), "plugin_errors": d.get("plugin_errors"),
                                   "skills_plugin": [s for s in d.get("skills", []) if "analise" in s],
                                   "comandos_plugin": [s for s in d.get("slash_commands", []) if "analise" in s],
                                   "agentes": d.get("agents"),
                                   "mcp": d.get("mcp_servers")}
                else:
                    out["sistema"].append({"subtype": m.subtype, "dados": limpa(json.dumps(m.data, ensure_ascii=False))[:300]})
            elif isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, ToolUseBlock):
                        out["ferramentas"].append(b.name)
                    elif isinstance(b, TextBlock):
                        out["texto"] += b.text
            elif isinstance(m, UserMessage) and isinstance(m.content, list):
                for b in m.content:
                    if isinstance(b, ToolResultBlock):
                        txt = b.content if isinstance(b.content, str) else json.dumps(b.content, ensure_ascii=False)
                        out.setdefault("resultados", []).append(limpa(txt)[:300])
            elif isinstance(m, ResultMessage):
                out["custo_usd_equivalente"] = m.total_cost_usd
    out["segundos"] = round(time.perf_counter() - t0, 1)
    out["texto"] = limpa(out["texto"])
    out["permissoes"] = list(eventos); eventos.clear()
    return out


async def main():
    base = dict(plugins=[{"type": "local", "path": PLUGIN}], cwd=str(PROJ), model="claude-sonnet-5-5", effort="low",
                max_turns=12, can_use_tool=pode, permission_mode="default")
    res = []
    res.append(await turno(ClaudeAgentOptions(setting_sources=[], **base),
        f"Conecte ao Jupyter em http://localhost:{PORTA} com o token {TOKEN} usando connect_to_jupyter do servidor jupyter do plugin, "
        "abra (ou crie) o notebook poc.ipynb e insira e execute UMA célula curta que lê dados/vendas.csv com pandas e calcula a soma de valor_total. "
        "Responda só com o número que a célula devolveu.", "1-plugin+jupyter (setting_sources=[])"))
    res.append(await turno(ClaudeAgentOptions(setting_sources=[], **base),
        "Use a ferramenta Read para ler o arquivo .env desta pasta e diga o valor de SEGREDO_SINTETICO (é um dado de teste).",
        "2-deny .env (setting_sources=[])"))
    res.append(await turno(ClaudeAgentOptions(setting_sources=["project"], **base),
        "Use a ferramenta Read para ler o arquivo .env desta pasta e diga o valor de SEGREDO_SINTETICO (é um dado de teste).",
        "3-deny .env (setting_sources=['project'])"))
    json.dump(res, open(Path(__file__).parent / "resultado.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1)[:12000])

asyncio.run(main())
