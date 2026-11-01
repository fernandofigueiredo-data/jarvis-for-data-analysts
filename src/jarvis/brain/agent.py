"""O cérebro: uma sessão viva do Claude Code (Agent SDK), usando o login da assinatura, sem chave de API."""
import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    ToolPermissionContext,
)

from jarvis import config
from jarvis.brain import tools
from jarvis.brain.gate import DENY_MESSAGE, WRITE_BUILTINS, decide_tool
from jarvis.brain.persona import system_prompt
from jarvis.memory import memory


def configured_mcp_servers() -> dict[str, Any]:
    """MCPs do Claude Code (~/.claude.json). Com setting_sources=[] o SDK não os descobre sozinho."""
    try:
        cfg = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    home = str(Path.home())
    return {**(cfg.get("mcpServers") or {}), **((cfg.get("projects") or {}).get(home, {}).get("mcpServers") or {})}


async def _can_use_tool(name: str, _input: dict[str, Any], _ctx: ToolPermissionContext):
    ok = decide_tool(name, config.ALLOW_WRITES)
    print(f"  ferramenta {name} -> {'liberada' if ok else 'negada'}")
    return PermissionResultAllow() if ok else PermissionResultDeny(message=DENY_MESSAGE)


class Brain:
    def __init__(self) -> None:
        self.client: ClaudeSDKClient | None = None
        self.lock = asyncio.Lock()
        self.cancelled = False
        self.external_servers = configured_mcp_servers()

    def options(self) -> ClaudeAgentOptions:
        facts = memory.memories(30)
        prompt = system_prompt()
        if facts:
            prompt += "\n\nO que você já sabe sobre ele:\n" + "\n".join(f"- {f}" for f in facts)
        return ClaudeAgentOptions(
            system_prompt=prompt,  # prompt próprio, não o preset de agente de código
            mcp_servers={**self.external_servers, **tools.servers()},
            # Nada de settings.json/CLAUDE.md do usuário: regras de "allow" de lá passariam por cima do gate
            setting_sources=[],
            cwd=str(Path.home()),
            model=config.MODEL,
            effort=config.EFFORT,
            max_turns=config.MAX_TURNS,
            permission_mode="default",
            include_partial_messages=True,  # texto chega em pedaços, a fala começa na primeira frase
            can_use_tool=_can_use_tool,
            # O CLI libera sozinho Bash "inofensivo" (ls, cat) sem passar pelo can_use_tool, então no modo
            # leitura as ferramentas de escrita nem existem na sessão
            disallowed_tools=[] if config.ALLOW_WRITES else sorted(WRITE_BUILTINS),
        )

    async def start(self) -> None:
        self.client = ClaudeSDKClient(self.options())
        await self.client.connect()

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def reset(self) -> None:
        """Nova conversa (esquece o contexto da sessão, mas não a memória do SQLite)."""
        await self.stop()
        await self.start()

    async def ask(self, text: str, on_text: Callable[[str], None] = lambda d: None,
                  on_tool: Callable[[str], None] = lambda n: None) -> str:
        async with self.lock:  # um turno por vez; a interrupção abaixo libera o próximo
            if self.client is None:
                await self.start()
            assert self.client
            self.cancelled = False
            answer: list[str] = []
            await self.client.query(text)
            async for msg in self.client.receive_response():
                if isinstance(msg, StreamEvent) and msg.parent_tool_use_id is None:
                    ev = msg.event
                    if ev.get("type") == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                        if not self.cancelled:
                            answer.append(ev["delta"]["text"])
                            on_text(ev["delta"]["text"])
                    elif ev.get("type") == "content_block_start":
                        block = ev.get("content_block", {})
                        if block.get("type") in ("tool_use", "server_tool_use", "mcp_tool_use"):
                            memory.bump("tool_calls")
                            on_tool(block.get("name", ""))
                elif isinstance(msg, ResultMessage):
                    if msg.is_error and not self.cancelled:
                        print(f"  erro no turno: {msg.subtype} {msg.errors or ''}")
                    break  # exatamente um result por turno: é a fronteira segura entre perguntas
            return "".join(answer).strip()

    async def cancel(self) -> None:
        """Barge-in: para a geração (e o consumo), não só a voz. O ask() em andamento termina sozinho."""
        if self.client and self.lock.locked():
            self.cancelled = True
            await self.client.interrupt()
