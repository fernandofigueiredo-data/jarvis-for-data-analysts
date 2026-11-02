"""Utilitários dos testes de ponta a ponta: o daemon de teste e a leitura do que o painel trocou com ele."""
import json
import os
import re
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import Page

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
# o mesmo Python do `uv run jarvis`: o sandbox do Python isolado só libera a leitura do venv do projeto
PYTHON = RAIZ / ".venv" / "bin" / "python"
# avisos do WebGL por software no Chromium headless, sem relação com o painel
RUIDO_GL = ("GL Driver Message", "GPU stall", "WebGL: INVALID", "Automatic fallback to software WebGL")


def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Daemon:
    """`tests/e2e/daemon_teste.py` num processo próprio, com pasta e porta próprias."""

    def __init__(self, base: Path, args: list[str] | None = None) -> None:
        self.base, self.args = base, args or []
        self.porta = porta_livre()
        self.url = f"http://127.0.0.1:{self.porta}/"
        self.proc: subprocess.Popen | None = None

    def start(self, timeout: float = 60) -> "Daemon":
        log = (self.base / "daemon.log").open("ab")
        cmd = [str(PYTHON), str(AQUI / "daemon_teste.py"), "--dir", str(self.base), "--port", str(self.porta), *self.args]
        self.proc = subprocess.Popen(cmd, cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                     env={**os.environ, "PYTHONUNBUFFERED": "1"})
        fim = time.time() + timeout
        while time.time() < fim:
            if self.proc.poll() is not None:
                raise RuntimeError(f"o daemon de teste saiu com código {self.proc.returncode}:\n{self.log()[-2000:]}")
            if self.no_ar():
                return self
            time.sleep(0.2)
        raise RuntimeError(f"o daemon de teste não respondeu em {timeout:.0f} s:\n{self.log()[-2000:]}")

    def stop(self) -> None:
        if not self.proc or self.proc.poll() is not None:
            return
        os.killpg(self.proc.pid, signal.SIGINT)
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()

    def no_ar(self) -> bool:
        try:
            return urllib.request.urlopen(self.url + "api/health", timeout=1).status == 200
        except OSError:
            return False

    def log(self) -> str:
        p = self.base / "daemon.log"
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    def falas(self) -> list[str]:
        """O que o Jarvis falou (o `say` falso registra cada frase; o `afplay`, o som)."""
        p = self.base / "fala.log"
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []

    def http(self, metodo: str, caminho: str, corpo: bytes | None = None, headers: dict | None = None):
        """(status, tipo, corpo) sem lançar exceção em 4xx/5xx."""
        req = urllib.request.Request(self.url + caminho.lstrip("/"), data=corpo, method=metodo, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.headers.get_content_type(), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get_content_type(), e.read()

    def json(self, caminho: str):
        status, _, corpo = self.http("GET", caminho)
        assert status == 200, f"GET {caminho} -> {status}"
        return json.loads(corpo)


# ------------------------------------------------------------------ o que passou pelo WebSocket da página
def eventos(page: Page, desde: float = 0) -> list[dict]:
    out = []
    for ts, bruto in page.registro.ws_in:
        if ts >= desde:
            try:
                out.append(json.loads(bruto))
            except (TypeError, ValueError):
                pass
    return out


def enviados(page: Page, desde: float = 0) -> list[dict]:
    return [json.loads(b) for ts, b in page.registro.ws_out if ts >= desde]


def esperar_evento(page: Page, cond, desde: float, timeout: float = 20) -> dict | None:
    fim = time.time() + timeout
    while time.time() < fim:
        for ev in eventos(page, desde):
            if cond(ev):
                return ev
        page.wait_for_timeout(100)
    return None


def esperar_resposta(page: Page, desde: float, timeout: float = 30, contendo: str = "") -> str:
    """Texto final do assistente depois de `desde` (o primeiro que contém `contendo`)."""
    ev = esperar_evento(page, lambda e: e.get("type") == "transcript" and e.get("role") == "assistant"
                        and e.get("final") and contendo in e.get("text", ""), desde, timeout)
    assert ev, f"o Jarvis não respondeu em {timeout:.0f} s" + (f" (esperava {contendo!r})" if contendo else "")
    return ev["text"]


def esperar_ocioso(page: Page, desde: float, timeout: float = 30) -> list[str]:
    """Espera a fase voltar a 'idle' depois de ter saído dela; devolve as fases vistas."""
    fim = time.time() + timeout
    while time.time() < fim:
        fases = [e["phase"] for e in eventos(page, desde) if e.get("type") == "state"]
        if fases and fases[-1] == "idle" and any(f != "idle" for f in fases):
            return fases
        page.wait_for_timeout(150)
    raise AssertionError(f"a fase não voltou a 'em espera' em {timeout:.0f} s: {fases}")


def item_do_feed(page: Page, desde: float, titulo: str, timeout: float = 15) -> dict | None:
    ev = esperar_evento(page, lambda e: e.get("type") == "feed" and titulo in e["item"]["title"], desde, timeout)
    return ev["item"] if ev else None


def perguntar(page: Page, texto: str, via: str = "cabecalho") -> float:
    """Faz a pergunta pelo campo do cabeçalho ou pelo "Fale com o Jarvis" do rodapé; devolve o instante do envio."""
    desde = time.time()
    if via == "cabecalho":
        campo = page.get_by_placeholder("Pesquisar ou comandar…")
    else:
        page.get_by_role("button", name=re.compile("Fale com o Jarvis")).click()
        campo = page.get_by_placeholder("Digite um comando para o Jarvis…")
    campo.fill(texto)
    campo.press("Enter")
    return desde


def status(page: Page) -> str:
    return page.get_by_text("STATUS DO SISTEMA", exact=True).locator("xpath=..").inner_text().replace("\n", " ")


def cartao(page: Page, titulo: str):
    return page.locator("section").filter(has=page.get_by_role("heading", name=titulo, exact=True)).first


def conversa(page: Page):
    return page.get_by_role("region", name="Conversa")


def falas_na_conversa(page: Page):
    """A lista de falas da Conversa (o parágrafo aria-live, só para leitor de tela, repete a última resposta)."""
    return conversa(page).locator("ol")


def painel_dados(page: Page):
    return page.get_by_role("region", name="Dados", exact=True)


# Contraste de cada texto visível contra o fundo efetivo (cores e gradientes dos ancestrais compostos sobre o fundo
# da página). Devolve [texto, razão, "cor tamanho"] dos que ficam abaixo de 4,5:1 (3:1 para texto grande).
CONTRASTE_JS = """() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true}); const memo = new Map();
  const parse = s => { if (!s || s === 'transparent') return [0, 0, 0, 0]; if (memo.has(s)) return memo.get(s);
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data; const c = [d[0], d[1], d[2], d[3] / 255]; memo.set(s, c); return c };
  const COLOR = /(?:rgba?|oklch|oklab|lab|lch|hsla?|color)\\([^()]*\\)|#[0-9a-f]{3,8}\\b/gi;
  const over = (top, base) => [0, 1, 2].map(i => top[i] * top[3] + base[i] * (1 - top[3]));
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]) };
  const bgOf = el => { const layers = [];
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const cs = getComputedStyle(e); const c = parse(cs.backgroundColor); if (c && c[3] > 0) layers.push(c);
      if (cs.backgroundImage.includes('gradient') && e !== document.body) {
        const stops = [...cs.backgroundImage.matchAll(COLOR)].map(m => parse(m[0])).filter(Boolean);
        if (stops.length) layers.push([0, 1, 2, 3].map(i => stops.reduce((a, s) => a + s[i], 0) / stops.length));
      }
    }
    let base = parse(getComputedStyle(document.body).backgroundColor);
    if (!base[3]) base = [5, 11, 22, 1];
    for (const l of layers.reverse()) base = over(l, [...base, 1]);
    return base };
  const out = []; const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement; const t = n.textContent.trim();
    if (!t || !el || seen.has(el) || el.closest('[aria-hidden=true], .sr-only, canvas, svg')) continue;
    seen.add(el); const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
    if (!r.width || !r.height || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    let op = 1; for (let e = el; e; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
    const bg = bgOf(el); const fg0 = parse(cs.color); const fg = over([fg0[0], fg0[1], fg0[2], fg0[3] * op], bg);
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize); const large = size >= 24 || (size >= 18.66 && +cs.fontWeight >= 700);
    if (ratio < (large ? 3 : 4.5)) out.push([t.slice(0, 40), Math.round(ratio * 100) / 100, `${cs.color} ${size}px`]);
  }
  return out.sort((a, b) => a[1] - b[1]);
}"""
