"""Quem decide se uma ferramenta roda. Voz é péssima para pedir confirmação, então a regra é decidida antes.

Inspirado no decideTool() de adewaskar/jarvis (MIT): bloqueia por padrão o que muda o mundo,
libera o que só lê ou gera, e um veto por verbo pega ações escondidas no nome da ferramenta.
"""
import re

READ_ONLY_BUILTINS = {
    "Read", "Glob", "Grep", "WebFetch", "WebSearch", "TodoWrite", "Task", "Agent", "ToolSearch",
    "ListMcpResources", "ListMcpResourcesTool", "ReadMcpResource", "ReadMcpResourceTool",
    "BashOutput", "TaskOutput",
}
WRITE_BUILTINS = {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "KillShell", "TaskStop"}

# Servidores in-process do próprio Jarvis: mexem no Mac local de forma reversível, sempre liberados
OWN_SERVERS = {"mac", "jarvis"}
# Servidores cuja superfície inteira é busca ou geração
READ_ONLY_MCP = {"exa", "serper", "serpapi", "mcp-registry"}

READ_VERB = re.compile(r"^(get|list|read|search|find|query|fetch|check|describe|inspect|show|view|explain|screenshot)", re.I)
# Sem âncora de propósito: "make_outbound_call" esconde o verbo no meio
EFFECTFUL_VERB = re.compile(
    r"(send|call|post|create|delete|remove|update|edit|write|install|launch|tap|swipe|press|type|buy|pay|charge|"
    r"publish|deploy|outbound|download|trash|move|complete|archive|forward|reply)", re.I)

DENY_MESSAGE = ("Bloqueado: o Jarvis está em modo somente leitura e não pode executar ações que mudam algo. "
                "Diga ao usuário, em uma frase, que essa ação fica disponível quando ele ligar o modo de escrita.")


def split_mcp(name: str) -> tuple[str, str] | None:
    """mcp__servidor__ferramenta -> (servidor, ferramenta); a ferramenta pode conter "__"."""
    if not name.startswith("mcp__"):
        return None
    parts = name.split("__")
    return parts[1], "__".join(parts[2:])


def decide_tool(name: str, allow_writes: bool) -> bool:
    if name in READ_ONLY_BUILTINS:
        return True
    if name in WRITE_BUILTINS:
        return allow_writes
    mcp = split_mcp(name)
    if mcp is None:
        return allow_writes
    server, tool = mcp
    if server in OWN_SERVERS:
        return True
    if EFFECTFUL_VERB.search(tool):
        return allow_writes
    if server in READ_ONLY_MCP:
        return True
    return bool(READ_VERB.match(tool)) or allow_writes
