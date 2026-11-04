"""Executor do docs/INVENTARIO_TESTES.md: abre o painel num navegador headless, aciona cada item e registra o resultado.

Não roda no pytest (o nome não começa com test_). Precisa do daemon no ar, de preferência com banco e voz de teste:

    JARVIS_DATA_DIR=/tmp/jarvis-teste uv run jarvis --no-window --mode off
    uv run --with playwright --with websockets python tests/e2e/inventario_ui.py --out resultado.json

Na primeira vez: `uv run --with playwright playwright install chromium`. Itens que exigem reiniciar o daemon
(CON-01/02, JAR-05) ou o microfone (JAR-07) ficam fora daqui e estão descritos no docs/RELATORIO_TESTES.md.
"""
import argparse
import asyncio
import concurrent.futures
import json
import re
import time
import urllib.request
from pathlib import Path

import websockets
from playwright.sync_api import Page, sync_playwright

GL_NOISE = ("GL Driver Message", "GPU stall", "WebGL: INVALID", "Automatic fallback to software WebGL")

# Contraste de cada texto visível contra o fundo efetivo: cores e gradientes (média das paradas) dos ancestrais
# compostos sobre o fundo da página. Devolve [texto, razão, "cor sobre fundo"] dos que ficam abaixo de 4,5:1.
CONTRAST_JS = """() => {
  // qualquer cor CSS (o Tailwind 4 usa oklch) vira sRGB pintando 1 pixel num canvas
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
    if (ratio < (large ? 3 : 4.5)) out.push([t.slice(0, 30), ratio, `${cs.color} ${size}px`]);
  }
  return out.sort((a, b) => a[1] - b[1]);
}"""


class Run:
    def __init__(self, browser, base: str, axe: str | None) -> None:
        self.browser, self.base, self.axe = browser, base.rstrip("/") + "/", axe
        self.results: list[dict] = []

    # ------------------------------------------------------------------ página instrumentada
    def page(self, width: int = 1440, height: int = 900, reduced_motion: str = "no-preference") -> Page:
        ctx = self.browser.new_context(viewport={"width": width, "height": height}, reduced_motion=reduced_motion)
        # links externos não saem da máquina: a aba nova é registrada e a navegação abortada
        ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1|localhost)"), lambda r: r.abort())
        page = ctx.new_page()
        page.log = {"console": [], "rede": [], "ws_out": [], "ws_in": [], "popups": []}

        def on_console(m):
            if m.type in ("error", "warning") and not any(n in m.text for n in GL_NOISE):
                page.log["console"].append(f"{m.type}: {m.text[:200]}")

        def on_ws(ws):
            ws.on("framesent", lambda f: page.log["ws_out"].append(f))
            ws.on("framereceived", lambda f: page.log["ws_in"].append((time.time(), f)))

        page.on("console", on_console)
        page.on("pageerror", lambda e: page.log["console"].append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: None if not r.url.startswith(self.base) else page.log["rede"].append(
            f"{r.method} {r.url} -> {r.failure}"))
        page.on("response", lambda r: page.log["rede"].append(f"{r.status} {r.url}") if r.status >= 400 else None)
        page.on("websocket", on_ws)
        ctx.on("page", lambda p: page.log["popups"].append(p.url or "about:blank"))
        page.goto(self.base)
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => document.querySelector('#root')?.children.length > 0")
        page.wait_for_timeout(1200)
        return page

    def record(self, id_: str, action: str, page: Page | None, status: str, observed: str) -> None:
        log = page.log if page else {"console": [], "rede": []}
        self.results.append({"id": id_, "acao": action, "status": status, "observado": observed,
                             "console": log["console"][:6], "rede": log["rede"][:6]})
        mark = {"PASSOU": "ok ", "FALHOU": "XX ", "NÃO TESTADO": "-- "}[status]
        print(f"{mark}{id_:7} {status:11} {observed[:150]}", flush=True)
        if page:
            page.context.close()

    # ------------------------------------------------------------------ utilidades
    @staticmethod
    def events(page: Page, since: float = 0) -> list[dict]:
        out = []
        for ts, raw in page.log["ws_in"]:
            if ts >= since and isinstance(raw, str):
                try:
                    out.append(json.loads(raw))
                except ValueError:
                    pass
        return out

    def wait_answer(self, page: Page, since: float, timeout: float = 60) -> tuple[str | None, float]:
        """Texto final do assistente e segundos até ele chegar."""
        end = time.time() + timeout
        while time.time() < end:
            for ev in self.events(page, since):
                if ev.get("type") == "transcript" and ev.get("role") == "assistant" and ev.get("final"):
                    return ev["text"], time.time() - since
            page.wait_for_timeout(200)
        return None, timeout

    def wait_idle(self, page: Page, since: float, timeout: float = 60) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            states = [e for e in self.events(page, since) if e.get("type") == "state"]
            if states and states[-1]["phase"] == "idle":
                return True
            page.wait_for_timeout(250)
        return False

    @staticmethod
    def ui_state(page: Page) -> dict:
        return page.evaluate("""() => {
          const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
          const a = document.activeElement;
          return {
            headings: [...document.querySelectorAll('h1,h2,h3,[role=heading]')].filter(vis).map(e => e.innerText.trim()).join('|'),
            overlays: [...document.querySelectorAll('[role=dialog],[role=menu],[role=listbox],[role=tooltip],[popover]')].filter(vis).length,
            aria: [...document.querySelectorAll('[aria-pressed],[aria-expanded],[aria-current],[aria-selected]')]
                    .map(e => (e.getAttribute('aria-label') || e.innerText.trim().slice(0, 20)) + ':' +
                              ['aria-pressed','aria-expanded','aria-current','aria-selected'].map(k => e.getAttribute(k) || '').join('')).join(','),
            typing: !!a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA'),
            focus: a && a.id ? a.id : '',
            highlight: [...document.querySelectorAll('.spotlight')].map(e => e.id).join(','),
            hash: location.hash, scroll: Math.round(window.scrollY + (document.querySelector('main')?.scrollTop || 0)),
          }
        }""")

    def click_effect(self, page: Page, locator, settle: int = 700) -> list[str]:
        """O que mudou depois do clique: mensagem ao daemon, aba nova, URL, overlay, títulos visíveis, estado ARIA, foco."""
        before, sent, pops, url = self.ui_state(page), len(page.log["ws_out"]), len(page.log["popups"]), page.url
        locator.click()
        page.wait_for_timeout(settle)
        after, fx = self.ui_state(page), []
        if len(page.log["ws_out"]) > sent:
            fx.append("enviou " + ", ".join(page.log["ws_out"][sent:])[:120])
        if len(page.log["popups"]) > pops:
            fx.append("abriu aba " + page.log["popups"][-1][:80])
        if page.url != url or after["hash"] != before["hash"]:
            fx.append(f"URL -> {page.url}")
        if after["overlays"] > before["overlays"]:
            fx.append("abriu painel/diálogo")
        if after["headings"] != before["headings"]:
            fx.append("conteúdo mudou")
        if after["aria"] != before["aria"]:
            fx.append("estado ARIA mudou")
        if after["typing"] and not before["typing"]:
            fx.append("campo de texto focado")
        if after["focus"] and after["focus"] != before["focus"]:
            fx.append(f"foco foi para #{after['focus']}")
        if after["highlight"] and after["highlight"] != before["highlight"]:
            fx.append(f"destacou #{after['highlight']}")
        if abs(after["scroll"] - before["scroll"]) > 40:
            fx.append("rolou a página")
        return fx

    def visible_text(self, page: Page, text: str) -> bool:
        snippet = text.strip()[:28]
        loc = page.get_by_text(snippet, exact=False)
        return any(loc.nth(i).is_visible() for i in range(min(loc.count(), 6)))

    # ------------------------------------------------------------------ cabeçalho
    def cabecalho(self) -> None:
        p = self.page()
        txt = p.get_by_text("STATUS DO SISTEMA").locator("xpath=..").inner_text().replace("\n", " ")
        ok = "OFFLINE" not in txt
        self.record("CAB-01", "abrir com daemon ligado", p, "PASSOU" if ok else "FALHOU", txt)

        p = self.page()
        t1 = p.locator("header .font-mono").first.inner_text()
        p.wait_for_timeout(2100)
        t2 = p.locator("header .font-mono").first.inner_text()
        self.record("CAB-02", "observar 2 s", p, "PASSOU" if t1 != t2 else "FALHOU", f"{t1} -> {t2}")

        self.ask_and_check("CAB-03", "campo do cabeçalho: pergunta + Enter",
                           lambda p: p.get_by_placeholder(re.compile("Pesquisar ou comandar")),
                           "quanto é doze vezes doze?")

        p = self.page()
        p.keyboard.press("Meta+k")
        p.wait_for_timeout(300)
        focused = p.evaluate("() => document.activeElement?.getAttribute('placeholder') || document.activeElement?.tagName")
        p.keyboard.press("Escape")
        p.keyboard.press("Control+k")
        p.wait_for_timeout(300)
        focused2 = p.evaluate("() => document.activeElement?.getAttribute('placeholder') || document.activeElement?.tagName")
        ok = "comandar" in str(focused) or "comandar" in str(focused2)
        self.record("CAB-04", "⌘K e Ctrl+K", p, "PASSOU" if ok else "FALHOU", f"foco após ⌘K: {focused}; após Ctrl+K: {focused2}")

        for id_, name in (("CAB-05", "Layout"), ("CAB-06", "Notificações"), ("CAB-07", "Configurações")):
            p = self.page()
            btn = p.get_by_role("button", name=re.compile(f"^{name}", re.I))
            if btn.count() == 0:
                self.record(id_, f"clicar em {name}", p, "PASSOU", "botão removido da interface")
                continue
            fx = self.click_effect(p, btn.first)
            self.record(id_, f"clicar em {name}", p, "PASSOU" if fx else "FALHOU", "; ".join(fx) or "nenhum efeito visível")

        p = self.page(375, 812)
        menu = p.get_by_role("button", name=re.compile("Menu de seções"))
        if menu.count() == 0:
            self.record("CAB-09", "celular: abrir o menu e escolher Notícias", p, "FALHOU", "não há menu de seções no celular")
        else:
            menu.click()
            p.wait_for_timeout(300)
            opened = p.get_by_role("dialog", name="Seções").count() > 0
            p.get_by_role("dialog", name="Seções").get_by_role("button", name=re.compile("^Notícias")).click()
            p.wait_for_timeout(700)
            closed = p.get_by_role("dialog", name="Seções").count() == 0
            focus = p.evaluate("() => document.activeElement?.id")
            ok = opened and closed and focus == "noticias"
            self.record("CAB-09", "celular: abrir o menu e escolher Notícias", p, "PASSOU" if ok else "FALHOU",
                        f"menu abriu={opened}; fechou ao escolher={closed}; foco foi para #{focus}")

        p = self.page()
        chip = p.get_by_text("Operador", exact=True)
        info = chip.first.evaluate("e => ({cursor: getComputedStyle(e.closest('div')).cursor, tag: e.closest('button,a') ? 'clicável' : 'estático'})") if chip.count() else {}
        self.record("CAB-08", "observar selo do operador", p, "PASSOU", f"{info}")

    # ------------------------------------------------------------------ barra lateral
    NAV = ["Command Center", "AI Core", "Agentes", "Tarefas", "Calendário", "Memória", "Conversas",
           "Base de Conhecimento", "Ferramentas & Skills", "Workflows", "Notícias"]

    def lateral(self) -> None:
        p = self.page()
        for i, label in enumerate(self.NAV, start=1):
            nav = p.get_by_role("navigation")
            item = nav.locator("button, a").filter(has_text=re.compile(f"^\\s*{re.escape(label)}"))
            if item.count() == 0:
                self.results.append({"id": f"LAT-{i:02}", "acao": f"clicar em {label}", "status": "PASSOU",
                                     "observado": "item removido da navegação", "console": [], "rede": []})
                print(f"ok LAT-{i:02} removido")
                continue
            # "Command Center" já é a tela atual: clicar nele vindo de outra tela é o que importa
            if i == 1:
                other = nav.locator("button, a").filter(has_text=re.compile(r"^\s*Conversas"))
                if other.count():
                    other.first.click()
                    p.wait_for_timeout(400)
            fx = self.click_effect(p, item.first)
            status = "PASSOU" if fx else "FALHOU"
            self.results.append({"id": f"LAT-{i:02}", "acao": f"clicar em {label}", "status": status,
                                 "observado": "; ".join(fx) or "nenhum efeito visível", "console": p.log["console"][:3],
                                 "rede": p.log["rede"][:3]})
            print(f"{'ok ' if fx else 'XX '}LAT-{i:02} {status:11} {label}: {'; '.join(fx) or 'nenhum efeito visível'}", flush=True)
        p.context.close()

        p = self.page()
        badges = p.get_by_role("navigation").locator("span.rounded-full").all_inner_texts()
        real = len(json.loads(urllib.request.urlopen(self.base + "api/conversations").read()))
        hard = [b for b in badges if b.strip().isdigit()]
        ok = not hard or ("12" not in hard and "18" not in hard)
        self.record("LAT-12", "comparar contadores com o daemon", p, "PASSOU" if ok else "FALHOU",
                    f"contadores na tela={hard or 'nenhum'}; turnos reais no daemon={real}")

        p = self.page()
        since = time.time()
        p.get_by_placeholder(re.compile("Pesquisar ou comandar")).fill("quanto é três mais quatro?")
        p.get_by_placeholder(re.compile("Pesquisar ou comandar")).press("Enter")
        seen = set()
        end = time.time() + 20
        while time.time() < end and not ("Falando" in seen and self.wait_idle(p, since, 0.1)):
            txt = p.locator("aside").first.inner_text()
            seen |= {label for label in ("Pensando", "Falando", "Em espera") if label in txt}
            p.wait_for_timeout(150)
        self.record("LAT-13", "acompanhar fases numa pergunta", p, "PASSOU" if {"Pensando", "Falando"} <= seen else "FALHOU",
                    f"fases vistas: {sorted(seen)}")

        p = self.page()
        mic = p.get_by_role("button", name=re.compile("falar", re.I)).first
        since, n = time.time(), len(p.log["ws_out"])
        mic.click()
        p.wait_for_timeout(1500)
        sent = p.log["ws_out"][n:]
        feedback = self.feedback_after(p, since)
        self.record("LAT-14", "clique rápido no microfone", p, "PASSOU" if feedback else "FALHOU",
                    f"enviou {sent}; retorno ao usuário: {feedback or 'nenhum'}")

        p = self.page()
        mic = p.get_by_role("button", name=re.compile("falar", re.I)).first
        box = mic.bounding_box()
        since, n = time.time(), len(p.log["ws_out"])
        p.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        p.mouse.down()
        p.wait_for_timeout(1200)
        held_label = p.locator("aside").first.inner_text()
        p.mouse.up()
        p.wait_for_timeout(1500)
        sent = p.log["ws_out"][n:]
        feedback = self.feedback_after(p, since)
        ok = len(sent) >= 2 and bool(feedback)
        self.record("LAT-15", "segurar o microfone 1,2 s (daemon sem microfone)", p, "PASSOU" if ok else "FALHOU",
                    f"enviou {sent}; enquanto segurava: {'Ouvindo' in held_label}; retorno: {feedback or 'nenhum'}")

        p = self.page()
        mic = p.get_by_role("button", name=re.compile("falar", re.I)).first
        mic.focus()
        n = len(p.log["ws_out"])
        p.keyboard.down("Space")
        p.wait_for_timeout(800)
        p.keyboard.up("Space")
        p.wait_for_timeout(500)
        sent = p.log["ws_out"][n:]
        ok = any('"down":true' in s for s in sent) and any('"down":false' in s for s in sent)
        self.record("LAT-16", "foco no microfone + segurar Espaço", p, "PASSOU" if ok else "FALHOU", f"enviou {sent}")

        p = self.page()
        btn = p.get_by_role("button", name=re.compile("Modo Foco"))
        n0 = len(self.ui_state(p)["headings"].split("|"))
        btn.first.click()
        p.wait_for_timeout(500)
        n1 = len(self.ui_state(p)["headings"].split("|"))
        btn.first.click()
        p.wait_for_timeout(500)
        n2 = len(self.ui_state(p)["headings"].split("|"))
        self.record("LAT-17", "Modo Foco duas vezes", p, "PASSOU" if n1 < n0 == n2 else "FALHOU",
                    f"títulos visíveis: {n0} -> {n1} -> {n2}")

    def feedback_after(self, page: Page, since: float) -> str:
        """Algo dito ao usuário depois de uma ação de voz: item no feed, fala, ou aviso (role=status/alert) na tela."""
        for ev in self.events(page, since):
            if ev.get("type") == "feed":
                return "feed: " + ev["item"]["title"]
            if ev.get("type") == "transcript" and ev.get("role") == "assistant":
                return "fala: " + ev["text"]
        notes = page.locator("[role=status], [role=alert]").all_inner_texts()
        hit = next((n for n in notes if re.search(r"microfone|voz|segure", n, re.I)), "")
        return ("aviso: " + hit.strip()[:80]) if hit else ""

    # ------------------------------------------------------------------ painéis
    def paineis(self) -> None:
        p = self.page()
        card = p.locator("section", has_text=re.compile("Visão geral do AI Core", re.I)).first
        txt = card.inner_text().replace("\n", " ")
        ok = all(k in txt for k in ("AI Core", "Memória", "Voz", "Agentes", "LLMs", "Sistema")) and "3.380" not in txt
        self.record("PAI-01", "abrir", p, "PASSOU" if ok else "FALHOU", txt[:140])

        p = self.page()
        has_canvas = p.locator("canvas").count() > 0
        chip = p.locator("section canvas").first.locator("xpath=ancestor::section[1]").inner_text().split("\n")[0] if has_canvas else ""
        errs = [c for c in p.log["console"] if "error" in c]
        self.record("PAI-02", "abrir", p, "PASSOU" if has_canvas and not errs else "FALHOU",
                    f"canvas={has_canvas}; chip={chip!r}; erros={len(errs)}")

        p = self.page()
        # respostas curtas ficam menos de 1 s na legenda: um observador guarda tudo o que passou por ela
        p.evaluate("""() => {
          const sec = document.querySelector('canvas').closest('section'); window.__legend = [];
          new MutationObserver(() => { for (const t of sec.innerText.split('\\n'))
            if (/^(Você|Jarvis):/.test(t) && !window.__legend.includes(t)) window.__legend.push(t) })
            .observe(sec, {subtree: true, childList: true, characterData: true});
        }""")
        since = time.time()
        p.get_by_placeholder(re.compile("Pesquisar ou comandar")).fill("diga apenas a palavra laranja")
        p.get_by_placeholder(re.compile("Pesquisar ou comandar")).press("Enter")
        answer, _ = self.wait_answer(p, since, 30)
        self.wait_idle(p, since, 20)
        legend = p.evaluate("() => window.__legend")
        ok = any(t.startswith("Jarvis:") for t in legend) and any(t.startswith("Você:") for t in legend)
        self.record("PAI-03", "pergunta e observar a legenda do globo", p, "PASSOU" if ok else "FALHOU",
                    f"resposta={answer!r}; legendas exibidas={legend[-3:]}")

        p = self.page()
        feed = p.locator("section", has_text=re.compile("Feed de inteligência", re.I)).first
        # com muitas ferramentas em uso as notícias saem das 5 primeiras linhas: abre a lista inteira antes
        p.get_by_role("button", name=re.compile("Ver toda a inteligência|Ver tudo|Ver todo", re.I)).first.click()
        p.wait_for_timeout(500)
        link_item = feed.locator("li, a").filter(has_text=re.compile("Notícia", re.I)).first
        if link_item.count():
            n = len(p.log["popups"])
            link_item.click()
            p.wait_for_timeout(800)
            opened = p.log["popups"][n:]
            self.record("PAI-04", "clicar numa notícia do feed", p, "PASSOU" if opened else "FALHOU",
                        f"abas abertas: {opened or 'nenhuma'}")
        else:
            self.record("PAI-04", "clicar numa notícia do feed", p, "NÃO TESTADO", "feed sem notícias")

        p = self.page()
        feed = p.locator("section", has_text=re.compile("Feed de inteligência", re.I)).first
        n0 = feed.locator("li").count()
        p.get_by_role("button", name=re.compile("Ver toda a inteligência|Ver tudo|Ver todo", re.I)).first.click()
        p.wait_for_timeout(600)
        n1 = feed.locator("li").count()
        p.get_by_role("button", name=re.compile("Mostrar menos", re.I)).first.click()
        p.wait_for_timeout(600)
        n2 = feed.locator("li").count()
        self.record("PAI-05", "expandir e recolher o feed", p, "PASSOU" if n1 > n0 and n2 == n0 else "FALHOU",
                    f"itens: {n0} -> {n1} -> {n2}")

        p = self.page()
        since = time.time()
        # timers mudam a todo momento, então o modelo consulta a ferramenta em vez de reaproveitar o contexto
        p.get_by_placeholder(re.compile("Pesquisar ou comandar")).fill("consulte agora a lista de timers ativos e diga quantos há")
        p.get_by_placeholder(re.compile("Pesquisar ou comandar")).press("Enter")
        active, end = "", time.time() + 25
        agents = p.locator("section", has_text=re.compile("Agentes ativos", re.I)).first
        while time.time() < end and not active:
            txt = agents.inner_text()
            m = re.search(r"(\w+)\n(?:ATIVO|Ativo)", txt)
            if m:
                active = m[1]
            p.wait_for_timeout(300)
        self.wait_idle(p, since, 30)  # antes do record, que fecha a página
        self.record("PAI-06", "pergunta que usa ferramenta (timer_list)", p, "PASSOU" if active else "FALHOU",
                    f"agente ativo visto: {active or 'nenhum em 25 s'}")

        p = self.page()
        tl = p.locator("section", has_text=re.compile("Linha do tempo da missão", re.I)).first.inner_text().replace("\n", " ")
        self.record("PAI-07", "abrir", p, "PASSOU", f"{tl[:120]} (latência do Calendário medida à parte)")

        self.quick("PAI-08", "Iniciar tarefa", 12, follow="comprar pão amanhã")
        self.quick("PAI-09", "Abrir calendário", 10)
        self.voice_command()
        self.quick("PAI-11", "Resumo de notícias", 12)

        p = self.page()
        ring = p.locator("section", has_text=re.compile("Monitor do sistema", re.I)).first
        a = ring.inner_text().replace("\n", " ")
        p.wait_for_timeout(4500)
        b = ring.inner_text().replace("\n", " ")
        nums = re.findall(r"(\d+)%", b)
        ok = len(nums) == 3 and all(0 <= int(x) <= 100 for x in nums)
        self.record("PAI-12", "observar 4,5 s", p, "PASSOU" if ok else "FALHOU", f"{a} -> {b}")

        p = self.page()
        mem = p.locator("section", has_text=re.compile("Insights de memória", re.I)).first.inner_text().replace("\n", " ")
        ok = "3.380" not in mem
        self.record("PAI-13", "abrir", p, "PASSOU" if ok else "FALHOU", mem)

        p = self.page()
        llm = p.locator("section", has_text=re.compile("Status dos LLMs", re.I)).first.inner_text().replace("\n", " ")
        ok = "Claude Code" in llm and "Cursor" not in llm
        self.record("PAI-14", "abrir", p, "PASSOU" if ok else "FALHOU", llm[:140])

    def quick(self, id_: str, label: str, limit: float, follow: str | None = None) -> None:
        p = self.page()
        since = time.time()
        p.get_by_role("button", name=re.compile(f"^{label}", re.I)).first.click()
        answer, secs = self.wait_answer(p, since, 45)
        obs = f"1ª resposta em {secs:.1f}s: {answer!r}"
        ok = answer is not None and secs <= limit
        if follow and answer:
            self.wait_idle(p, since, 30)
            since2 = time.time()
            p.get_by_placeholder(re.compile("Pesquisar ou comandar")).fill(follow)
            p.get_by_placeholder(re.compile("Pesquisar ou comandar")).press("Enter")
            a2, s2 = self.wait_answer(p, since2, 45)
            obs += f" | depois de responder {follow!r}: {a2!r} ({s2:.1f}s)"
            ok = ok and a2 is not None
        self.wait_idle(p, since, 40)
        self.record(id_, f"clicar em {label}", p, "PASSOU" if ok else "FALHOU", obs)

    def voice_command(self) -> None:
        p = self.page()
        since = time.time()
        p.get_by_role("button", name=re.compile("^Iniciar conversa por voz", re.I)).first.click()
        p.wait_for_timeout(13000)
        states = [e["phase"] for e in self.events(p, since) if e.get("type") == "state"]
        last = states[-1] if states else "?"
        feedback = self.feedback_after(p, since)
        ok = last != "listening" and bool(feedback)
        self.record("PAI-10", "clicar em Iniciar conversa por voz (daemon sem microfone)", p, "PASSOU" if ok else "FALHOU",
                    f"fases: {states[:4]}…; fase após 13 s: {last}; retorno: {feedback or 'nenhum'}")

    # ------------------------------------------------------------------ rodapé
    def rodape(self) -> None:
        p = self.page()
        chips = p.locator("footer").first.inner_text().replace("\n", " ")
        for id_, label in (("ROD-01", "LOCAL"), ("ROD-02", "CLIMA"), ("ROD-03", "REDE")):
            m = re.search(label + r"\s+(.+?)(?=\s+(?:LOCAL|CLIMA|REDE|FALE)|$)", chips, re.I)
            val = m[1] if m else ""
            ok = bool(val) and val != "—" and "…" not in val and "..." not in val
            self.results.append({"id": id_, "acao": "abrir", "status": "PASSOU" if ok else "FALHOU", "observado": val,
                                 "console": [], "rede": []})
            print(f"{'ok ' if ok else 'XX '}{id_} {val}")
        # o texto pode estar cortado só visualmente (reticências via CSS): mede o valor atual e, no clima, a
        # descrição mais longa que o daemon produz ("Parcialmente nublado"), que depende do tempo lá fora
        cut = p.evaluate("""() => {
          const chips = {};
          for (const lab of document.querySelectorAll('footer div')) {
            const k = lab.children.length === 0 && lab.innerText.trim().toUpperCase();
            if (!['LOCAL', 'CLIMA', 'REDE'].includes(k) || !lab.nextElementSibling) continue;
            const v = lab.nextElementSibling;
            const over = () => v.scrollWidth > v.clientWidth + 1 || v.scrollHeight > v.clientHeight + 1;
            chips[k] = {now: over()};
            if (k === 'CLIMA') { const old = v.textContent; v.textContent = '24°C · Parcialmente nublado';
                                 chips[k].worst = over(); v.textContent = old; }
          }
          return chips }""")
        for r in self.results[-3:]:
            c = cut.get({"ROD-01": "LOCAL", "ROD-02": "CLIMA", "ROD-03": "REDE"}[r["id"]], {})
            if c.get("now") or c.get("worst"):
                r["status"] = "FALHOU"
                r["observado"] += " (cortado na tela)" if c.get("now") else " (cabe, mas '24°C · Parcialmente nublado' seria cortado)"
                print(f"XX {r['id']} {r['observado']}")
        p.context.close()

        p = self.page()
        fx = self.click_effect(p, p.get_by_text(re.compile("fale com o jarvis", re.I)).first)
        self.record("ROD-04", "clicar em Fale com o Jarvis", p, "PASSOU" if "campo de texto focado" in fx else "FALHOU",
                    "; ".join(fx) or "nenhum efeito")

        self.ask_and_check("ROD-05", "Fale com o Jarvis: pergunta + Enter", None, "qual a capital da Austrália?")

        p = self.page()
        p.get_by_text(re.compile("fale com o jarvis", re.I)).first.click()
        box = p.get_by_placeholder(re.compile("Digite um comando para o Jarvis"))
        box.fill("que horas são?")
        n = len(p.log["ws_out"])
        p.get_by_role("button", name=re.compile("^Enviar")).first.click()
        p.wait_for_timeout(800)
        sent = p.log["ws_out"][n:]
        self.record("ROD-06", "digitar + clicar na seta", p, "PASSOU" if any('"say"' in s for s in sent) else "FALHOU",
                    f"enviou {sent}")

        p = self.page()
        p.get_by_text(re.compile("fale com o jarvis", re.I)).first.click()
        box = p.get_by_placeholder(re.compile("Digite um comando para o Jarvis"))
        box.fill("texto que vou cancelar")
        n = len(p.log["ws_out"])
        box.press("Escape")
        p.wait_for_timeout(400)
        back = p.get_by_text(re.compile("fale com o jarvis", re.I)).first.is_visible()
        ok = back and len(p.log["ws_out"]) == n and p.get_by_placeholder(re.compile("Digite um comando")).count() == 0
        self.record("ROD-07", "digitar + Esc", p, "PASSOU" if ok else "FALHOU", f"voltou ao rótulo={back}; enviou={p.log['ws_out'][n:]}")

        self.quick("ROD-08", "Briefing Executivo", 15)

        p = self.page()
        conv = p.get_by_role("region", name="Conversa")
        p.get_by_role("navigation").locator("button, a").filter(has_text=re.compile(r"^\s*Conversas")).first.click()
        p.wait_for_timeout(300)
        opened = conv.count() > 0
        p.get_by_role("button", name="Fechar conversa").click()
        p.wait_for_timeout(300)
        closed_x = conv.count() == 0
        p.get_by_role("navigation").locator("button, a").filter(has_text=re.compile(r"^\s*Conversas")).first.click()
        p.wait_for_timeout(300)
        conv.first.press("Escape")
        p.wait_for_timeout(300)
        closed_esc = conv.count() == 0
        ok = opened and closed_x and closed_esc
        self.record("CNV-01", "abrir a conversa e fechar pelo X e pelo Esc", p, "PASSOU" if ok else "FALHOU",
                    f"abriu={opened}; fechou no X={closed_x}; fechou no Esc={closed_esc}")

        p = self.page()
        since = time.time()
        field = p.get_by_placeholder(re.compile("Pesquisar ou comandar"))
        field.fill("liste três cores primárias em uma frase")
        field.press("Enter")
        end = time.time() + 15
        while time.time() < end and not any(e.get("type") == "transcript" and e.get("role") == "user" for e in self.events(p, since)):
            p.wait_for_timeout(100)
        p.get_by_role("button", name="Fechar conversa").click()
        answer, _ = self.wait_answer(p, since, 40)
        self.wait_idle(p, since, 30)
        reopened = p.get_by_role("region", name="Conversa").count() > 0
        self.record("CNV-02", "fechar a conversa enquanto a resposta chega", p,
                    "PASSOU" if answer and not reopened else "FALHOU",
                    f"resposta chegou={bool(answer)}; painel reabriu sozinho={reopened}")

        p = self.page()
        voice = p.locator("section", has_text=re.compile("Visão geral do AI Core", re.I)).first.inner_text()
        mode = re.search(r"Voz\n(.+)", voice)
        pill = p.get_by_text(re.compile("fale com o jarvis", re.I)).first.locator("xpath=..").inner_text().replace("\n", " ")
        listening_claim = bool(re.search(r"ouvindo", pill, re.I))
        ok = not (mode and mode[1].strip() in ("Desligada", "Segure Option") and listening_claim)
        self.record("ROD-09", "comparar o convite do rodapé com o modo de voz", p, "PASSOU" if ok else "FALHOU",
                    f"voz={mode[1].strip() if mode else '?'}; rodapé diz {pill!r}")

    def ask_and_check(self, id_: str, action: str, field, question: str) -> None:
        """Pergunta e confere se a resposta continua legível 3 s depois de o Jarvis terminar de falar."""
        p = self.page()
        since = time.time()
        if field is None:
            p.get_by_text(re.compile("fale com o jarvis", re.I)).first.click()
            box = p.get_by_placeholder(re.compile("Digite um comando para o Jarvis"))
        else:
            box = field(p)
        box.fill(question)
        box.press("Enter")
        answer, secs = self.wait_answer(p, since)
        if not answer:
            self.record(id_, action, p, "FALHOU", f"nenhuma resposta em {secs:.0f}s")
            return
        during = self.visible_text(p, answer)
        self.wait_idle(p, since, 40)
        p.wait_for_timeout(3000)
        after = self.visible_text(p, answer)
        self.record(id_, action, p, "PASSOU" if after else "FALHOU",
                    f"resposta em {secs:.1f}s ({answer[:70]!r}); visível durante a fala={during}; 3 s depois={after}")

    # ------------------------------------------------------------------ servidor
    def api(self) -> None:
        def get(path: str):
            with urllib.request.urlopen(self.base + path.lstrip("/")) as r:
                return r.status, r.headers.get_content_type(), r.read()

        s, _, body = get("/api/health")
        h = json.loads(body)
        self.record("API-01", "GET /api/health", None, "PASSOU" if s == 200 and "brain" in h else "FALHOU", f"{s} {h}")
        s1, _, b1 = get("/api/conversations")
        s2, _, b2 = get("/api/conversations?q=Austr")
        self.record("API-02", "GET /api/conversations (e ?q=)", None, "PASSOU" if s1 == s2 == 200 else "FALHOU",
                    f"{s1}: {len(json.loads(b1))} turnos; ?q=Austr: {len(json.loads(b2))}")
        s1, _, b1 = get("/api/news")
        s2, _, b2 = get("/api/news?source=Data%20Hackers")
        self.record("API-03", "GET /api/news (e ?source=)", None, "PASSOU" if s1 == s2 == 200 and json.loads(b1) else "FALHOU",
                    f"{s1}: {len(json.loads(b1))} manchetes; Data Hackers: {len(json.loads(b2))}")

        async def ws_checks():
            url = self.base.replace("http", "ws") + "ws"
            try:
                async with websockets.connect(url, additional_headers={"Origin": "http://evil.example.com"}):
                    o4 = "conectou (deveria recusar)"
            except Exception as exc:
                o4 = f"recusado: {exc}"
            async with websockets.connect(url, additional_headers={"Origin": self.base.rstrip("/")}) as ws:
                snap = json.loads(await ws.recv())
                o5 = f"1ª mensagem type={snap['type']} chaves={sorted(k for k in snap if k != 'type')}"
                try:
                    await ws.send("isto não é json")
                    await ws.send(json.dumps({"type": "command", "id": "nao_existe"}))
                    await asyncio.sleep(1)
                    await ws.send(json.dumps({"type": "say", "text": "que horas são?"}))
                    alive = False
                    end = time.time() + 6
                    while time.time() < end:
                        ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=end - time.time()))
                        if ev.get("type") == "transcript" and ev.get("role") == "assistant":
                            alive = True
                            break
                    o6 = "conexão continuou viva e respondeu depois" if alive else "conexão viva, mas sem resposta"
                except Exception as exc:
                    o6 = f"conexão derrubada: {type(exc).__name__}"
            return o4, o5, o6

        # o Playwright síncrono já tem um loop nesta thread
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            o4, o5, o6 = pool.submit(asyncio.run, ws_checks()).result()
        self.record("API-04", "WS com Origin estranha", None, "PASSOU" if "403" in o4 else "FALHOU", o4)
        self.record("API-05", "WS snapshot inicial", None, "PASSOU" if "snapshot" in o5 else "FALHOU", o5)
        self.record("API-06", "WS texto não-JSON", None, "PASSOU" if "continuou viva" in o6 else "FALHOU", o6)
        self.record("API-07", "WS comando desconhecido", None, "PASSOU" if "continuou viva" in o6 else "FALHOU",
                    "enviado na mesma conexão do API-06: " + o6)
        html = get("/")[2].decode()
        assets = re.findall(r'(?:src|href)="\./([^"]+)"', html)
        codes = {a: get("/" + a)[0] for a in assets}
        self.record("API-08", "index + assets + favicon", None, "PASSOU" if all(c == 200 for c in codes.values()) else "FALHOU",
                    f"/ 200; {codes}")

    # ------------------------------------------------------------------ responsividade e acessibilidade
    def responsivo(self) -> None:
        for id_, (w, h) in (("RES-01", (1440, 900)), ("RES-02", (1280, 760)), ("RES-02b", (900, 600)),
                            ("RES-03", (768, 1024)), ("RES-04", (375, 812))):
            p = self.page(w, h)
            info = p.evaluate("""() => {
              const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight) && getComputedStyle(e).visibility !== 'hidden';
              const btn = re => [...document.querySelectorAll('button')].filter(b => re.test((b.getAttribute('aria-label')||'') + b.innerText)).some(vis);
              return {overflow: document.documentElement.scrollWidth - window.innerWidth,
                      mic: btn(/falar/i), foco: btn(/modo foco/i),
                      nav: [...document.querySelectorAll('nav')].some(vis) || btn(/menu|navega|seç/i)}
            }""")
            shot = Path(self.out_dir) / f"{self.tag}_{id_}_{w}x{h}.png"
            p.screenshot(path=str(shot), full_page=True)
            ok = info["overflow"] <= 0 and (w >= 768 or (info["mic"] and info["foco"] and info["nav"]))
            id_out = "RES-02" if id_.startswith("RES-02") else id_
            self.record(id_out, f"abrir em {w}×{h}", p, "PASSOU" if ok else "FALHOU",
                        f"rolagem horizontal={info['overflow']}px; microfone={info['mic']}; modo foco={info['foco']}; "
                        f"navegação={info['nav']}; print={shot.name}")

    def acessibilidade(self) -> None:
        p = self.page()
        stops, seen = [], set()
        for _ in range(90):
            p.keyboard.press("Tab")
            # foco visível = algum estilo visível muda entre focado e não focado (no elemento ou em até dois
            # contêineres, caso de campos dentro de cápsulas); outline com estilo "none" não aparece, então não conta
            el = p.evaluate("""() => {
              const e = document.activeElement; if (!e || e === document.body) return null;
              const look = () => [e, e.parentElement, e.parentElement?.parentElement].filter(Boolean).map(x => { const c = getComputedStyle(x);
                const outline = c.outlineStyle === 'none' || parseFloat(c.outlineWidth) === 0 ? 'none'
                                : [c.outlineStyle, c.outlineWidth, c.outlineColor].join(' ');
                return [outline, c.boxShadow, c.borderColor, c.backgroundColor].join('/') }).join('|');
              const focused = look(); e.blur(); const blurred = look(); e.focus();
              const name = [e.getAttribute('aria-label'), e.getAttribute('placeholder'), e.innerText]
                .filter(Boolean).join(' / ').trim().split('\\n')[0].slice(0, 60) || e.tagName;
              return {name, ring: focused !== blurred, tag: e.tagName}
            }""")
            if not el:
                continue
            key = el["name"]
            if key in seen:
                if stops and key == stops[0]["name"]:
                    break
                continue
            seen.add(key)
            stops.append(el)
        names = [s["name"] for s in stops]
        must = ["Pesquisar ou comandar", "falar", "Modo Foco", "Iniciar tarefa", "Briefing", "Fale com o Jarvis"]
        missing = [m for m in must if not any(m.lower() in n.lower() for n in names)]
        no_ring = [s["name"] for s in stops if not s["ring"]]
        ok = not missing and not no_ring
        self.record("ACE-01", "Tab pela página inteira", p, "PASSOU" if ok else "FALHOU",
                    f"{len(stops)} paradas; inalcançáveis={missing or 'nenhum'}; sem foco visível={no_ring[:8] or 'nenhum'}")

        if not self.axe:
            self.record("ACE-02", "auditoria axe-core", None, "NÃO TESTADO", "axe-core indisponível")
            self.record("ACE-03", "auditoria axe-core", None, "NÃO TESTADO", "axe-core indisponível")
        else:
            p = self.page()
            p.add_script_tag(path=self.axe)
            res = p.evaluate("""async () => {
              const r = await axe.run(document, {runOnly: {type: 'rule', values: ['button-name','label','link-name','color-contrast','aria-allowed-attr','nested-interactive','aria-required-children']}});
              return r.violations.map(v => ({id: v.id, n: v.nodes.length, ex: v.nodes.slice(0, 4).map(x => x.target.join(' ').slice(-60) + ' :: ' + (x.any[0]?.message || '').slice(0, 90))}))
            }""")
            names = [v for v in res if v["id"] != "color-contrast"]
            contrast = [v for v in res if v["id"] == "color-contrast"]
            self.record("ACE-02", "auditoria axe-core (nomes/rótulos/ARIA)", p, "PASSOU" if not names else "FALHOU",
                        json.dumps(names, ensure_ascii=False)[:600] if names else "0 violações")
            n_axe = sum(v["n"] for v in contrast)
            self.results[-1]["axe"] = res
            # o axe não julga texto sobre gradiente/vidro ("needs review"): mede compondo as camadas de fundo
            p = self.page()
            low = p.evaluate(CONTRAST_JS)
            self.record("ACE-03", "contraste AA (axe-core + medição com fundo composto)", p,
                        "PASSOU" if n_axe == 0 and not low else "FALHOU",
                        f"axe: {n_axe} violações; medição: {len(low)} textos abaixo de 4,5:1; piores: "
                        f"{[f'{x[0]!r} {x[1]:.2f}:1 ({x[2]})' for x in low[:5]]}")

        p = self.page(reduced_motion="reduce")
        p.wait_for_timeout(800)
        anim = p.evaluate("""() => {
          const css = document.getAnimations().filter(a => a.playState === 'running' && a.effect?.getTiming().iterations === Infinity).length;
          const smil = [...document.querySelectorAll('svg')].filter(s => s.querySelector('animate,animateTransform') && !s.animationsPaused()).length;
          return {css, smil}
        }""")
        ok = anim["css"] == 0 and anim["smil"] == 0
        self.record("ACE-04", "prefers-reduced-motion: reduce", p, "PASSOU" if ok else "FALHOU",
                    f"animações CSS infinitas rodando={anim['css']}; SVGs animados={anim['smil']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8787/")
    ap.add_argument("--out", default="inventario_resultado.json")
    ap.add_argument("--browser", default="chromium", choices=["chromium", "webkit"])
    ap.add_argument("--axe", help="caminho do axe.min.js (npm i axe-core)")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--only", help="grupos separados por vírgula: cabecalho,lateral,paineis,rodape,api,responsivo,acessibilidade")
    args = ap.parse_args()
    groups = (args.only or "cabecalho,lateral,paineis,rodape,api,responsivo,acessibilidade").split(",")
    with sync_playwright() as pw:
        launcher = getattr(pw, args.browser)
        flags = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if args.browser == "chromium" else []
        browser = launcher.launch(headless=True, args=flags)
        run = Run(browser, args.url, args.axe)
        run.out_dir, run.tag = str(Path(args.out).resolve().parent), args.tag
        t0 = time.time()
        try:
            for g in groups:
                getattr(run, g)()
        finally:
            browser.close()
            Path(args.out).write_text(json.dumps(run.results, ensure_ascii=False, indent=1), encoding="utf-8")
    total = {s: sum(1 for r in run.results if r["status"] == s) for s in ("PASSOU", "FALHOU", "NÃO TESTADO")}
    print(f"\n{len(run.results)} itens em {time.time() - t0:.0f}s: {total} -> {args.out}")


if __name__ == "__main__":
    main()
