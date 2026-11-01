"""HTTP + WebSocket local (127.0.0.1) que alimenta o painel e recebe comandos dele."""
import asyncio
import json
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from jarvis import config, news
from jarvis.events import bus
from jarvis.memory import memory

if TYPE_CHECKING:
    from jarvis.app import Jarvis

PLACEHOLDER = """<!doctype html><meta charset=utf-8><title>Jarvis</title>
<body style="background:#050b16;color:#7dd3fc;font:16px system-ui;padding:40px">
<h1>J.A.R.V.I.S.</h1><p>O painel ainda não foi compilado. Rode <code>cd ui && npm run build</code>.</p>
<pre id=log style="color:#94a3b8"></pre><script>
const ws=new WebSocket(`ws://${location.host}/ws`);ws.onmessage=e=>{const m=JSON.parse(e.data);
if(m.type!=='telemetry')log.textContent=JSON.stringify(m).slice(0,300)+'\\n'+log.textContent.slice(0,5000)}
</script>"""

ALLOWED_ORIGINS = {f"http://{config.HOST}:{config.PORT}", f"http://localhost:{config.PORT}",
                   "http://localhost:5173", "http://127.0.0.1:5173", None}


def create_app(jarvis: "Jarvis") -> FastAPI:
    app = FastAPI(title="Jarvis")

    @app.get("/api/health")
    async def health():
        return {"ok": True, "brain": jarvis.brain_ready, "voice": jarvis.mode, "tts": jarvis.speaker.engine,
                "news": news.status}

    @app.get("/api/conversations")
    async def conversations(q: str = ""):
        return memory.search_turns(q) if q else memory.recent_turns(50)

    @app.get("/api/news")
    async def latest_news(source: str | None = None):
        return memory.latest_news(source, 30)

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        # Só o próprio painel: uma página qualquer aberta no navegador não pode dirigir o Jarvis
        if socket.headers.get("origin") not in ALLOWED_ORIGINS:
            await socket.close(code=4403)
            return
        await socket.accept()
        q = bus.subscribe()
        await socket.send_text(json.dumps(bus.snapshot(), ensure_ascii=False))

        async def pump():
            while True:
                await socket.send_text(json.dumps(await q.get(), ensure_ascii=False))

        sender = asyncio.create_task(pump())
        try:
            while True:
                msg = json.loads(await socket.receive_text())
                await jarvis.on_client(msg)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            sender.cancel()
            bus.unsubscribe(q)

    if (config.UI_DIST / "index.html").exists():
        app.mount("/", StaticFiles(directory=config.UI_DIST, html=True), name="ui")
    else:
        @app.get("/")
        async def index():
            return HTMLResponse(PLACEHOLDER)

    return app
