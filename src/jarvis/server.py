"""HTTP + WebSocket local (127.0.0.1) que alimenta o painel e recebe comandos dele."""
import asyncio
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from jarvis import config, dados, news
from jarvis.events import bus
from jarvis.memory import memory

if TYPE_CHECKING:
    from jarvis.app import Jarvis

# cores e fontes do design system (o painel compilado as tem em ui/src/index.css)
PLACEHOLDER = """<!doctype html><meta charset=utf-8><title>Jarvis</title>
<body style="background:#101522;color:#f2f7ff;font:16px Inter,-apple-system,system-ui,sans-serif;padding:48px">
<h1 style="font-weight:600">J.A.R.V.I.S.</h1><p>O painel ainda não foi compilado. Rode
<code style="font-family:'JetBrains Mono',ui-monospace,monospace;color:#39ff88">cd ui && npm run build</code>.</p>
<pre id=log style="color:#aab8cc;font-family:'JetBrains Mono',ui-monospace,monospace"></pre><script>
const ws=new WebSocket(`ws://${location.host}/ws`);ws.onmessage=e=>{const m=JSON.parse(e.data);
if(m.type!=='telemetry')log.textContent=JSON.stringify(m).slice(0,300)+'\\n'+log.textContent.slice(0,5000)}
</script>"""

# o próprio daemon, o `npm run dev` (5173) e o `npm run preview` (4173)
ALLOWED_ORIGINS = {f"http://{config.HOST}:{config.PORT}", f"http://localhost:{config.PORT}",
                   "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173",
                   None}


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

    @app.post("/api/upload")
    async def upload(request: Request, nome: str):
        """Arquivo arrastado para o painel: corpo cru (sem multipart), gravado em data/arquivos e aberto num turno."""
        # mesma regra do WebSocket: uma página qualquer aberta no navegador não pode mandar arquivos ao Jarvis
        if request.headers.get("origin") not in ALLOWED_ORIGINS:
            return JSONResponse({"erro": "origem não permitida"}, status_code=403)
        base = re.sub(r"[^\w.\- ]", "_", Path(nome).name).strip(" .") or "arquivo.csv"
        if Path(base).suffix.lower() not in dados.EXTENSOES:
            return JSONResponse({"erro": f"só {', '.join(sorted(dados.EXTENSOES))}"}, status_code=415)
        destino = config.UPLOAD_DIR / base
        n = 2
        while destino.exists():
            destino = config.UPLOAD_DIR / f"{Path(base).stem}-{n}{Path(base).suffix}"
            n += 1
        tamanho = 0
        try:
            with destino.open("wb") as f:
                async for chunk in request.stream():
                    tamanho += len(chunk)
                    if tamanho > config.UPLOAD_MAX_BYTES:
                        raise ValueError("grande demais")
                    f.write(chunk)
        except ValueError:
            destino.unlink(missing_ok=True)
            return JSONResponse({"erro": f"arquivo acima de {config.UPLOAD_MAX_BYTES // 2**20} MB"}, status_code=413)
        if not tamanho:
            destino.unlink(missing_ok=True)
            return JSONResponse({"erro": "arquivo vazio"}, status_code=400)
        jarvis.submit(f"Abra o arquivo {destino} com abrir_arquivo e me dê o panorama em até duas frases.",
                      shown=f"Arquivo enviado: {destino.name}")
        return {"ok": True, "arquivo": destino.name, "bytes": tamanho}

    @app.get("/api/graficos/{nome}")
    async def grafico(nome: str):
        """PNG do Python isolado. Nome aleatório (uuid), só arquivos .png da pasta de gráficos."""
        if not re.fullmatch(r"[0-9a-f]{32}\.png", nome):
            return JSONResponse({"erro": "nome inválido"}, status_code=404)
        path = config.CACHE_DIR / "graficos" / nome
        if not path.exists():
            return JSONResponse({"erro": "não encontrado"}, status_code=404)
        return FileResponse(path, media_type="image/png")

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
                try:
                    msg = json.loads(await socket.receive_text())
                except ValueError:
                    continue  # mensagem malformada não derruba a conexão do painel
                if isinstance(msg, dict):
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
