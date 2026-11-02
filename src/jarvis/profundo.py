"""Modo análise profunda: uma sessão separada do Claude com o plugin analise-dados (Jupyter, revisão crítica, relatório).

Exceção explícita à regra "só agregados" (decisão do usuário, 02/11/2026): aqui o resultado de cada célula, inclusive
linhas cruas, vai para o Claude. Por isso o modo só abre a pasta (ou o arquivo) que o usuário escolheu, e a sessão de
voz normal continua com a regra de agregados.

A sessão tem política própria: Jupyter, skills e subagentes do plugin liberados; shell só para os scripts do plugin;
escrita só dentro do projeto e nunca em dados/; nada de rede. As regras do projeto (.claude/settings.json, que negam
ler o .env e editar dados/) valem porque esta sessão carrega setting_sources=["project"] — na P5, sem isso, o .env foi
lido. O Jupyter roda com as permissões do usuário (não é sandbox): quem isola é a política de ferramentas.
"""
import asyncio
import atexit
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    ToolPermissionContext,
)

from jarvis import config

JUPYTER = "mcp__plugin_analise-dados_jupyter__"
SEMPRE = {"Skill", "Task", "Agent", "TodoWrite", "ToolSearch", "BashOutput", "TaskOutput"}
LEITURA = {"Read", "Glob", "Grep"}
ESCRITA = {"Write", "Edit", "MultiEdit"}
# Só os comandos do fluxo do plugin (os mesmos que o .claude/settings.json do projeto libera)
BASH_OK = [re.compile(p) for p in (
    r"^uv --version$",
    r"^uv run --no-project --python (3\.12|\.venv) \"?[^\"]*analise-dados[^\"]*/scripts/"
    r"(bootstrap|stop|validar|relatorio|banco)\.py\"?( [^;&|`$<>]*)?$",
    r"^ls( -[a-zA-Z]+)?( [^;&|`$<>]*)?$",
)]
SAIR = re.compile(r"\b(sai|sair|saia|encerra|encerrar|termina|terminar|fecha|fechar|desliga|desligar|volta|voltar)\b"
                  r".*\b(modo profundo|an[aá]lise profunda|modo normal|ao normal)\b", re.I)
TOKEN = re.compile(r"token=[0-9a-fA-F]+")

APPEND = """
Você está no modo análise profunda do JARVIS, o assistente de voz do usuário. O "aluno" dos comandos do plugin é o
próprio usuário, um analista de dados. Ele fala com você por voz:
- Comece TODA resposta com um resumo de até duas frases, em texto corrido, sem markdown nem links: só essas duas frases
  são faladas. O resto aparece no painel.
- O Jarvis já abre o notebook no navegador sozinho: não repita o link nem o token do Jupyter.
- Os dados já estão em dados/. Não baixe nada da internet.
- Para sair deste modo, o usuário diz "sair do modo profundo".
"""


def plugin_path() -> Path | None:
    """Instalação do plugin analise-dados (JARVIS_PLUGIN_ANALISE ou a registrada pelo Claude Code)."""
    if config.PLUGIN_ANALISE:
        p = Path(config.PLUGIN_ANALISE).expanduser()
        return p if p.is_dir() else None
    try:
        reg = json.loads((Path.home() / ".claude/plugins/installed_plugins.json").read_text(encoding="utf-8"))
        info = (reg.get("plugins") or reg).get("analise-dados@analise-dados") or []
        p = Path(info[0]["installPath"]) if info else None
        return p if p and p.is_dir() else None
    except (OSError, ValueError, KeyError, IndexError):
        return None


def _dentro(path: str | None, raiz: Path, projeto: Path) -> bool:
    """Caminho relativo é relativo ao projeto (o cwd da sessão), qualquer que seja a raiz testada."""
    if not path:
        return raiz.resolve() == projeto.resolve()  # Glob/Grep sem caminho = a pasta da sessão
    p = Path(path).expanduser()
    p = (projeto / p if not p.is_absolute() else p).resolve()
    return p.is_relative_to(raiz.resolve())


def decidir(nome: str, entrada: dict[str, Any], projeto: Path, plugin: Path) -> str | None:
    """None = libera; texto = motivo da recusa."""
    if nome.startswith(JUPYTER) or nome in SEMPRE:
        return None
    if nome in LEITURA:
        alvo = entrada.get("file_path") or entrada.get("path")
        if _dentro(alvo, projeto, projeto) or _dentro(alvo, plugin, projeto):
            return None
        return "No modo profundo, a leitura fica restrita à pasta do projeto."
    if nome in ESCRITA:
        alvo = entrada.get("file_path")
        if alvo and _dentro(alvo, projeto, projeto) and not _dentro(alvo, projeto / "dados", projeto):
            return None
        return "No modo profundo, só se escreve dentro do projeto, e nunca em dados/."
    if nome == "Bash":
        cmd = (entrada.get("command") or "").strip()
        if any(p.match(cmd) for p in BASH_OK):
            return None
        return "No modo profundo, o terminal só roda os scripts do plugin (bootstrap, validar, relatorio, stop)."
    return f"{nome} não faz parte do modo análise profunda."


def preparar(pasta: str | None = None, arquivo: Path | None = None) -> tuple[Path, str]:
    """Projeto da análise: a pasta escolhida, ou uma nova em JARVIS_PASTA_ANALISES com o arquivo copiado para dados/."""
    if arquivo:
        projeto = config.ANALISES_DIR / re.sub(r"[^\w\- ]", "_", arquivo.stem)
        (projeto / "dados").mkdir(parents=True, exist_ok=True)
        destino = projeto / "dados" / arquivo.name
        if not destino.exists():
            shutil.copy2(arquivo, destino)  # cópia: o original não é tocado
        return projeto, f"{arquivo.name} copiado para {projeto}/dados"
    p = Path(pasta or "").expanduser()
    if not p.is_absolute():
        p = next((d for base in config.DATA_FOLDERS if base.is_dir()
                  for d in [base / pasta, *base.glob(f"*/{pasta}"), *base.glob(f"*/*/{pasta}")] if d.is_dir()), Path("/não-existe"))
    if not p.is_dir():
        raise ValueError("não achei essa pasta; diga o caminho completo ou o nome de uma pasta em Downloads, Documentos ou Mesa")
    if p.resolve() in {Path.home().resolve(), Path("/")}:
        raise ValueError("escolha a pasta do projeto de análise, não a pasta pessoal inteira")
    return p, f"pasta {p}"


class Profundo:
    def __init__(self, projeto: Path, plugin: Path) -> None:
        self.projeto, self.plugin = projeto, plugin
        self.client: ClaudeSDKClient | None = None
        self.lock = asyncio.Lock()
        self.notebook_aberto = False

    async def _pode(self, nome: str, entrada: dict[str, Any], _ctx: ToolPermissionContext):
        motivo = decidir(nome, entrada, self.projeto, self.plugin)
        print(f"  [profundo] {nome} -> {'liberada' if motivo is None else 'negada'}")
        return PermissionResultAllow() if motivo is None else PermissionResultDeny(message=motivo)

    def options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt={"type": "preset", "preset": "claude_code", "append": APPEND},
            plugins=[{"type": "local", "path": str(self.plugin)}],
            setting_sources=["project"],  # as regras do projeto do plugin (deny .env, deny editar dados/)
            cwd=str(self.projeto), model=config.MODEL, effort=config.EFFORT_PROFUNDO, max_turns=80,
            permission_mode="default", include_partial_messages=True, can_use_tool=self._pode,
            disallowed_tools=["WebFetch", "WebSearch", "NotebookEdit", "KillShell"],
        )

    async def start(self) -> None:
        self.client = ClaudeSDKClient(self.options())
        await self.client.connect()

    async def ask(self, text: str, on_tool: Callable[[str], None] = lambda n: None) -> str:
        async with self.lock:
            if self.client is None:
                await self.start()
            assert self.client
            partes: list[str] = []
            await self.client.query(text)
            async for msg in self.client.receive_response():
                if isinstance(msg, StreamEvent) and msg.parent_tool_use_id is None:
                    ev = msg.event
                    if ev.get("type") == "content_block_start":
                        block = ev.get("content_block", {})
                        if block.get("type") in ("tool_use", "server_tool_use", "mcp_tool_use"):
                            on_tool(block.get("name", ""))
                elif isinstance(msg, AssistantMessage) and msg.parent_tool_use_id is None:
                    partes = [getattr(b, "text", "") for b in msg.content if getattr(b, "text", "")] or partes
                elif isinstance(msg, ResultMessage):
                    if msg.is_error:
                        print(f"  [profundo] erro: {msg.subtype} {msg.api_error_status or ''} {msg.result or ''} "
                              f"{'; '.join(msg.errors or [])}"[:400])
                    if msg.is_error and not partes:
                        raise RuntimeError(msg.result or "; ".join(msg.errors or []) or msg.subtype)
                    break
            return TOKEN.sub("token=…", "\n\n".join(partes).strip())

    def jupyter_url(self) -> str | None:
        """Endereço do notebook, quando o bootstrap do plugin já subiu o Jupyter (lido dos arquivos dele)."""
        rt = self.projeto / ".runtime"
        try:
            porta, token = (rt / "jupyter.port").read_text().strip(), (rt / "jupyter.token").read_text().strip()
        except OSError:
            return None
        nb = "analise.ipynb" if (self.projeto / "analise.ipynb").exists() else ""
        return f"http://localhost:{porta}/lab/tree/{nb}?token={token}"

    async def cancel(self) -> None:
        if self.client and self.lock.locked():
            await self.client.interrupt()

    async def stop(self) -> None:
        """Fecha a sessão (o hook SessionEnd do plugin desliga o Jupyter) e, por garantia, roda o stop.py."""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception as exc:
                print(f"  [profundo] erro ao fechar a sessão: {exc}")
            self.client = None
        stop = self.plugin / "scripts" / "stop.py"
        if stop.exists() and (self.projeto / ".runtime").exists():
            await asyncio.to_thread(subprocess.run, ["uv", "run", "--no-project", "--python", "3.12", str(stop)],
                                    cwd=self.projeto, env={**os.environ, "CLAUDE_PROJECT_DIR": str(self.projeto)},
                                    capture_output=True, timeout=60)


def falado(resposta: str, limite: int = 320) -> str:
    """As duas primeiras frases, sem markdown; o resto fica na conversa."""
    texto = re.sub(r"```.*?```", " ", resposta, flags=re.S)
    texto = re.sub(r"https?://\S+|[*_`#>|]", " ", texto)
    # fim de frase só com espaço depois: "vendas_setembro.csv" não corta a frase no ponto
    frases = re.findall(r".+?[.!?](?=\s|$)", re.sub(r"\s+", " ", texto).strip())
    curto = " ".join(f.strip() for f in frases[:2])[:limite]
    if not curto:
        curto = re.sub(r"\s+", " ", texto).strip()[:limite]
    return curto + (" O resto está na conversa." if len(resposta) > len(curto) + 40 else "")


class Estado:
    """O modo profundo ativo (ou pedido), compartilhado entre a ferramenta que o inicia e o app que roteia a fala."""

    def __init__(self) -> None:
        self.sessao: Profundo | None = None
        self.pendente: str | None = None  # primeiro pedido para a sessão nova, enviado pelo app depois do turno atual

    @property
    def ativo(self) -> bool:
        return self.sessao is not None


estado = Estado()


@atexit.register
def _desligar_jupyter() -> None:
    """Jarvis fechado com o modo profundo aberto: o hook SessionEnd não roda, então o stop.py do plugin desliga o Jupyter."""
    sessao = estado.sessao
    if sessao and (sessao.projeto / ".runtime").exists():
        subprocess.run(["uv", "run", "--no-project", "--python", "3.12", str(sessao.plugin / "scripts" / "stop.py")],
                       cwd=sessao.projeto, env={**os.environ, "CLAUDE_PROJECT_DIR": str(sessao.projeto)},
                       capture_output=True, timeout=60)
