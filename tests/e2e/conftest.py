"""Fixtures dos testes de ponta a ponta do painel: daemon de teste, navegador e página instrumentada.

    uv run --with playwright playwright install chromium webkit   # uma vez
    uv run --with playwright pytest tests/e2e

Cada módulo de teste ganha um daemon de teste próprio (porta e pasta temporária novas; o Claude e a fala são
simulados, ver daemon_teste.py). Cada página registra erros de console, exceções e requisições com falha; um teste
que deixe algum que ele não declarou esperar (`page.registro.esperar(...)`) é reprovado. O registro de todos os
testes vai para tests/e2e/saida/registro.json, e os prints das falhas para tests/e2e/saida/.

Sem o Playwright instalado (o `uv run pytest` dos testes de unidade), os módulos daqui são pulados.
"""
import json
import re
import time
from pathlib import Path

import pytest

SAIDA = Path(__file__).resolve().parent / "saida"
REGISTRO: list[dict] = []


class Registro:
    """Tudo o que a página disse e pediu: console, exceções, rede e as mensagens do WebSocket."""

    def __init__(self, origem: str) -> None:
        self.origem = origem
        self.erros: list[str] = []
        self.avisos: list[str] = []
        self.rede: list[str] = []
        self.ws_in: list[tuple[float, str]] = []
        self.ws_out: list[tuple[float, str]] = []
        self.abas: list[str] = []
        self.permitidos: list[re.Pattern] = []

    def esperar(self, *padroes: str) -> None:
        """Erros que o próprio teste provoca (ex.: um 413 de propósito) e que, por isso, não o reprovam."""
        self.permitidos += [re.compile(p) for p in padroes]

    def ligar(self, page) -> None:
        from apoio import RUIDO_GL

        def console(m):
            if m.type == "error":
                self.erros.append(f"console: {m.text[:300]}")
            elif m.type == "warning" and not any(r in m.text for r in RUIDO_GL):
                self.avisos.append(m.text[:300])

        def falhou(r):
            self.rede.append(f"{r.method} {r.url} -> {r.failure}")

        def resposta(r):
            if r.status >= 400:
                self.rede.append(f"{r.request.method} {r.url} -> {r.status}")

        def websocket(ws):
            ws.on("framereceived", lambda f: self.ws_in.append((time.time(), f)))
            ws.on("framesent", lambda f: self.ws_out.append((time.time(), f)))

        page.on("console", console)
        page.on("pageerror", lambda e: self.erros.append(f"exceção: {e}"))
        page.on("requestfailed", falhou)
        page.on("response", resposta)
        page.on("websocket", websocket)
        page.context.on("page", lambda p: self.abas.append(p.url))

    def problemas(self) -> list[str]:
        return [p for p in self.erros + self.rede if not any(r.search(p) for r in self.permitidos)]


def pytest_configure(config):
    config.addinivalue_line("markers", "lento: cenário que espera mais de 10 s (reinício do daemon, timers)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    rep = (yield).get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture(scope="session")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def chromium(pw):
    # WebGL por software: o globo 3D precisa dele no Chromium headless
    b = pw.chromium.launch(headless=True, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    yield b
    b.close()


@pytest.fixture(scope="session")
def webkit(pw):
    """O motor da janela nativa do Jarvis (pywebview usa o WebKit do macOS)."""
    b = pw.webkit.launch(headless=True)
    yield b
    b.close()


@pytest.fixture(scope="module")
def daemon(request, tmp_path_factory):
    """Um daemon de teste por módulo; o módulo pode pedir opções com DAEMON_ARGS (ex.: ["--sem-noticias"])."""
    from apoio import Daemon
    d = Daemon(tmp_path_factory.mktemp("jarvis"), getattr(request.module, "DAEMON_ARGS", [])).start()
    yield d
    d.stop()
    log = d.log()
    assert "Traceback" not in log, f"exceção não tratada no daemon:\n{log[log.index('Traceback') - 400:][:3000]}"


@pytest.fixture
def abrir(request, chromium, daemon):
    """Abre o painel numa página instrumentada: abrir(largura, altura, navegador=..., movimento=..., conectar=...).
    `rota_ws` intercepta o WebSocket da página (page.route_web_socket) para o teste injetar mensagens do daemon."""
    paginas = []

    def _abrir(largura=1440, altura=900, navegador=None, movimento="no-preference", conectar=True, url=None,
               rota_ws=None):
        ctx = (navegador or chromium).new_context(viewport={"width": largura, "height": altura},
                                                  reduced_motion=movimento, locale="pt-BR")
        # nada sai da máquina: o painel não deve buscar nada fora do 127.0.0.1
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1[:/]|localhost[:/])"), lambda r: r.abort())
        page = ctx.new_page()
        page.registro = Registro(daemon.url)
        page.registro.ligar(page)
        paginas.append(page)
        if rota_ws:
            page.route_web_socket(re.compile(r"/ws$"), rota_ws)
        page.goto(url or daemon.url)
        page.wait_for_function("() => document.querySelector('#root')?.children.length > 0")
        if conectar:
            # conectado e com a saúde do daemon aplicada (antes disso o status é OFFLINE ou DEGRADADO)
            page.wait_for_function("""() => { const e = [...document.querySelectorAll('span')]
                .find(s => s.textContent === 'STATUS DO SISTEMA'); return e && /ÓTIMO|ATENÇÃO/.test(e.parentElement.innerText) }""",
                                   timeout=15000)
        return page

    yield _abrir

    nome = re.sub(r"[^\w.-]+", "_", request.node.nodeid.split("::", 1)[-1])
    falhou = getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed
    problemas = []
    for i, page in enumerate(paginas):
        r = page.registro
        if falhou and not page.is_closed():
            SAIDA.mkdir(exist_ok=True)
            page.screenshot(path=str(SAIDA / f"{nome}_{i}.png"), full_page=True)
        REGISTRO.append({"teste": request.node.nodeid, "pagina": i, "erros_console": r.erros, "rede": r.rede,
                         "esperados": [p.pattern for p in r.permitidos], "avisos": r.avisos})
        problemas += r.problemas()
        page.context.close()
    assert not problemas, "erros de console ou requisições com falha:\n" + "\n".join(problemas)


@pytest.fixture
def pagina(abrir):
    return abrir()


def pytest_sessionfinish(session, exitstatus):
    if REGISTRO:
        SAIDA.mkdir(exist_ok=True)
        (SAIDA / "registro.json").write_text(json.dumps(REGISTRO, ensure_ascii=False, indent=1), encoding="utf-8")


def pytest_terminal_summary(terminalreporter):
    if not REGISTRO:
        return
    erros = sum(len(r["erros_console"]) for r in REGISTRO)
    rede = sum(len(r["rede"]) for r in REGISTRO)
    avisos = sum(len(r["avisos"]) for r in REGISTRO)
    terminalreporter.write_line(f"painel: {len(REGISTRO)} páginas abertas · erros de console: {erros} · requisições com "
                                f"falha: {rede} (os esperados pelo teste incluídos) · avisos de console: {avisos} · "
                                f"detalhes em {SAIDA / 'registro.json'}")
