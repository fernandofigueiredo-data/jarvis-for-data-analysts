"""Cenários do inventário que exigem ligar e desligar o daemon: CON-01, CON-02 e JAR-05.

    uv run --with playwright python tests/e2e/cenarios_daemon.py conexao --cmd "uv run jarvis --no-window --mode off"
    JARVIS_MODEL=modelo-inexistente uv run jarvis --no-window --mode off   # noutro terminal, para o JAR-05
    uv run --with playwright python tests/e2e/cenarios_daemon.py erro

No cenário "conexao" a porta 8787 precisa estar livre: o roteiro liga o daemon com --cmd, derruba e religa.
"""
import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8787/"
# Valores que só existem nos dados de demonstração (ui/src/mock.ts)
MOCK_MARKS = ["3.380", "São Paulo, BR", "Briefing matinal", "Revisão de código", "Treino", "Cursor", "Copilot",
              "Bateria em 18%", "Jarvis, abra o Spotify", "Wi-Fi · 5 GHz"]


def daemon_up() -> bool:
    try:
        return urllib.request.urlopen(URL + "api/health", timeout=1).status == 200
    except OSError:
        return False


def browser_page(p, url: str):
    b = p.chromium.launch(headless=True, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.log = {"console": [], "ws_in": []}
    page.on("console", lambda m: page.log["console"].append(m.text) if m.type == "error" and "GL" not in m.text else None)
    page.on("websocket", lambda ws: ws.on("framereceived", lambda f: page.log["ws_in"].append((time.time(), f))))
    page.goto(url)
    return b, page


def status_text(page) -> str:
    return page.get_by_text("STATUS DO SISTEMA").locator("xpath=..").inner_text().replace("\n", " ")


def start(cmd: str) -> subprocess.Popen:
    proc = subprocess.Popen(shlex.split(cmd), env=dict(os.environ, PYTHONUNBUFFERED="1"), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    t0 = time.time()
    while not daemon_up() and time.time() - t0 < 60:
        time.sleep(0.2)
    return proc


def stop(proc: subprocess.Popen) -> None:
    os.killpg(proc.pid, signal.SIGINT)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)


def conexao(cmd: str, out: dict) -> None:
    """Painel aberto com o daemon no ar; o daemon cai (CON-01) e volta (CON-02), como num reinício do Jarvis."""
    assert not daemon_up(), "desligue o daemon antes do cenário de conexão"
    proc = start(cmd)
    with sync_playwright() as p:
        b, page = browser_page(p, URL)
        try:
            page.wait_for_timeout(3000)
            stop(proc)
            t0 = time.time()
            while "OFFLINE" not in status_text(page) and time.time() - t0 < 15:
                page.wait_for_timeout(250)
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text()
            demo = [m for m in MOCK_MARKS if m in body]
            st = status_text(page)
            banner = bool(re.search(r"demonstra", body, re.I))
            out["CON-01"] = {"status": "PASSOU" if "OFFLINE" in st and banner else "FALHOU",
                             "observado": f"status={st!r} após {time.time() - t0:.1f}s; aviso de demonstração visível={banner}; "
                                          f"dados de demonstração na tela={demo}"}
            print("CON-01", out["CON-01"])
            page.screenshot(path=out["_shot"].replace(".png", "_offline.png"))

            t0 = time.time()
            proc = start(cmd)
            up = time.time() - t0
            connected = None
            while time.time() - t0 < 40:
                if "OFFLINE" not in status_text(page):
                    connected = time.time() - t0
                    break
                page.wait_for_timeout(250)
            leftovers = []
            if connected:
                page.wait_for_timeout(1500)
                body = page.locator("body").inner_text()
                leftovers = [m for m in MOCK_MARKS if m in body]
            ok = connected is not None and not leftovers
            out["CON-02"] = {"status": "PASSOU" if ok else "FALHOU",
                             "observado": f"daemon no ar em {up:.1f}s; painel reconectou em {(connected or 0):.1f}s; "
                                          f"dados de demonstração ainda na tela 1,5 s depois={leftovers}"}
            print("CON-02", out["CON-02"])
            page.screenshot(path=out["_shot"])
        finally:
            stop(proc)
            b.close()


def erro(out: dict) -> None:
    """Com o daemon rodando com um modelo inválido: a pergunta precisa render alguma mensagem ao usuário."""
    with sync_playwright() as p:
        b, page = browser_page(p, URL)
        page.wait_for_timeout(2500)
        since = time.time()
        field = page.get_by_placeholder(re.compile("Pesquisar ou comandar"))
        field.fill("qual a capital da Austrália?")
        field.press("Enter")
        page.wait_for_timeout(12000)
        evs = []
        for ts, raw in page.log["ws_in"]:
            if ts >= since:
                ev = json.loads(raw)
                if ev["type"] in ("transcript", "feed") or (ev["type"] == "state"):
                    evs.append(ev)
        answers = [e["text"] for e in evs if e["type"] == "transcript" and e["role"] == "assistant" and e["final"]]
        feeds = [f"{e['item']['title']} — {e['item'].get('subtitle', '')[:90]}" for e in evs if e["type"] == "feed"]
        phases = [e["phase"] for e in evs if e["type"] == "state"]
        visible = any(page.get_by_text(a[:25]).count() for a in answers)
        ok = bool(answers) and visible
        out["JAR-05"] = {"status": "PASSOU" if ok else "FALHOU",
                         "observado": f"fases={sorted(set(phases), key=phases.index)}; resposta={answers or 'nenhuma'}; "
                                      f"aviso no feed={feeds or 'nenhum'}; mensagem visível na tela={visible}"}
        print("JAR-05", out["JAR-05"])
        page.screenshot(path=out["_shot"])
        b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cenario", choices=["conexao", "erro"])
    ap.add_argument("--cmd", default="uv run jarvis --no-window --mode off")
    ap.add_argument("--out", default="cenarios_resultado.json")
    ap.add_argument("--shot", default="cenario.png")
    a = ap.parse_args()
    res: dict = {"_shot": a.shot}
    conexao(a.cmd, res) if a.cenario == "conexao" else erro(res)
    res.pop("_shot")
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
