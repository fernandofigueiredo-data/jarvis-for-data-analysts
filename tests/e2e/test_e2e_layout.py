"""Tamanhos de tela, teclado, nomes acessíveis, contraste, movimento reduzido e o WebKit da janela nativa."""
import json
import re
import time

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import CONTRASTE_JS, esperar_resposta, falas_na_conversa, item_do_feed, painel_dados, perguntar  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

TAMANHOS = [(1440, 900), (1280, 760), (900, 600), (768, 1024), (375, 812)]  # 1280×760 e 900×600: janela nativa


@pytest.mark.parametrize("largura, altura", TAMANHOS, ids=[f"{w}x{h}" for w, h in TAMANHOS])
def test_sem_rolagem_horizontal_e_controles_principais_visiveis(abrir, largura, altura):
    pagina = abrir(largura, altura)
    assert pagina.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 0
    expect(pagina.get_by_role("button", name="Segure para falar").locator("visible=true")).to_have_count(1)
    expect(pagina.get_by_role("button", name="Layout: Modo Foco")).to_be_visible()
    expect(pagina.get_by_role("button", name=re.compile("Fale com o Jarvis"))).to_be_visible()
    expect(pagina.get_by_role("button", name="Briefing Executivo")).to_be_visible()
    if largura >= 768:
        expect(pagina.get_by_role("navigation", name="Seções")).to_be_visible()
    else:
        expect(pagina.get_by_role("button", name="Menu de seções")).to_be_visible()


def test_menu_de_secoes_no_celular_leva_ao_cartao(abrir):
    pagina = abrir(375, 812)
    pagina.get_by_role("button", name="Menu de seções").click()
    menu = pagina.get_by_role("dialog", name="Seções")
    expect(menu).to_be_visible()
    menu.get_by_role("button", name="Notícias").click()
    expect(menu).to_have_count(0)
    expect(pagina.locator("#noticias")).to_be_focused()


def test_microfone_do_rodape_no_celular(abrir):
    pagina = abrir(375, 812)
    desde = time.time()
    pagina.locator("footer").get_by_role("button", name="Segure para falar").click()
    assert item_do_feed(pagina, desde, "Voz desligada")


def test_paineis_flutuantes_cabem_no_celular(abrir):
    pagina = abrir(375, 812)
    pagina.get_by_role("button", name="Menu de seções").click()
    pagina.get_by_role("dialog", name="Seções").get_by_role("button", name="Dados").click()
    caixa = painel_dados(pagina).bounding_box()
    assert caixa["x"] >= 0 and caixa["x"] + caixa["width"] <= 375
    assert pagina.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 0


def test_teclado_alcanca_os_controles_com_foco_visivel(pagina):
    paradas, vistos = [], set()
    for _ in range(80):
        pagina.keyboard.press("Tab")
        el = pagina.evaluate("""() => {
          const e = document.activeElement; if (!e || e === document.body) return null;
          const look = () => [e, e.parentElement, e.parentElement?.parentElement].filter(Boolean).map(x => {
            const c = getComputedStyle(x); const o = c.outlineStyle === 'none' || parseFloat(c.outlineWidth) === 0 ? 'none'
              : [c.outlineStyle, c.outlineWidth, c.outlineColor].join(' ');
            return [o, c.boxShadow, c.borderColor, c.backgroundColor].join('/') }).join('|');
          const comFoco = look(); e.blur(); const semFoco = look(); e.focus();
          const nome = (e.getAttribute('aria-label') || e.getAttribute('placeholder') || e.innerText || e.tagName).trim()
            .split('\\n')[0].slice(0, 60);
          return {nome, anel: comFoco !== semFoco}
        }""")
        if not el:
            continue
        if el["nome"] in vistos:
            if paradas and el["nome"] == paradas[0]["nome"]:
                break  # deu a volta
            continue
        vistos.add(el["nome"])
        paradas.append(el)
    nomes = [p["nome"] for p in paradas]
    for alvo in ("Command Center", "Dados", "Segure para falar", "Modo Foco", "Pergunte ou dê um comando ao Jarvis",
                 "Layout: Modo Foco", "Notificações", "Configurações", "Ver toda a inteligência", "Iniciar tarefa",
                 "Fale com o Jarvis — digitar um comando", "Briefing Executivo"):
        assert any(n.startswith(alvo) for n in nomes), f"{alvo!r} fora do alcance do Tab: {nomes}"
    assert [p["nome"] for p in paradas if not p["anel"]] == []


NOMES_JS = """() => [...document.querySelectorAll('button, a[href], input, select, textarea, [role=button], [role=tab]')]
  .filter(e => e.offsetWidth || e.offsetHeight || e.getClientRects().length)
  .filter(e => !(e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.innerText.trim() || e.title ||
                 (e.labels && e.labels.length)))
  .map(e => e.outerHTML.slice(0, 120))"""


def test_todo_controle_tem_nome_acessivel(pagina):
    pagina.get_by_role("navigation", name="Seções").get_by_role("button", name="Dados", exact=True).click()
    pagina.get_by_role("button", name=re.compile("^Notificações")).click()
    perguntar(pagina, "que horas são?")
    expect(painel_dados(pagina)).to_be_visible()
    assert pagina.evaluate(NOMES_JS) == []


def contraste(pagina) -> list:
    """Textos abaixo de AA, medidos depois das animações de entrada (um item do feed surgindo tem opacidade parcial)."""
    pagina.wait_for_timeout(600)
    pagina.wait_for_function("""() => !document.getAnimations().some(a => a.playState === 'running'
                                 && a.effect?.getTiming().iterations !== Infinity)""", timeout=5000)
    return pagina.evaluate(CONTRASTE_JS)


def test_contraste_minimo_aa_no_painel_e_nos_paineis_flutuantes(pagina):
    assert contraste(pagina) == []
    desde = perguntar(pagina, "abre o arquivo vendas teste")
    esperar_resposta(pagina, desde)
    desde = perguntar(pagina, "qual uf mais fatura?")
    esperar_resposta(pagina, desde)
    expect(painel_dados(pagina).locator("tbody tr").first).to_be_visible()
    expect(falas_na_conversa(pagina)).to_be_visible()
    assert contraste(pagina) == []
    pagina.get_by_role("button", name="Configurações").click()
    assert contraste(pagina) == []


def test_movimento_reduzido_desliga_as_animacoes_continuas(abrir):
    pagina = abrir(movimento="reduce")
    pagina.wait_for_timeout(800)
    animacoes = pagina.evaluate("""() => ({
      css: document.getAnimations().filter(a => a.playState === 'running' && a.effect?.getTiming().iterations === Infinity).length,
      svg: [...document.querySelectorAll('svg')].filter(s => s.querySelector('animate, animateTransform') && !s.animationsPaused()).length })""")
    assert animacoes == {"css": 0, "svg": 0}


def test_webkit_da_janela_nativa_conecta_conversa_e_mostra_dados(abrir, webkit):
    pagina = abrir(1280, 760, navegador=webkit)
    desde = perguntar(pagina, "qual a capital da Austrália?")
    assert esperar_resposta(pagina, desde) == "A capital da Austrália é Camberra, senhor."
    expect(falas_na_conversa(pagina).get_by_text("A capital da Austrália é Camberra, senhor.")).to_be_visible()
    desde = perguntar(pagina, "abre o arquivo vendas teste")
    esperar_resposta(pagina, desde)
    expect(painel_dados(pagina)).to_contain_text("· vendas_teste.csv")
    assert pagina.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 0


SOBREPOSTOS_JS = """() => { const r = [...document.querySelectorAll('#noticias li')].map(li => li.getBoundingClientRect());
  let n = 0; for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++)
    if (Math.min(r[i].bottom, r[j].bottom) - Math.max(r[i].top, r[j].top) > 4) n++;
  return {itens: r.length, sobrepostos: n} }"""


def test_rajada_de_manchetes_assenta_sem_sobrepor_no_webkit(abrir, webkit):
    """Na partida, a primeira coleta manda umas 24 manchetes seguidas (3 por fonte) com o painel já aberto. No WebKit
    da janela nativa a animação do feed assenta em menos de 0,5 s. (No Chromium headless, com o globo desenhado por
    software a ~12 quadros/s, a mesma animação se estica e um print no meio dela mostra o feed embaralhado.)"""
    rotas = []

    def proxy(ws):
        ws.connect_to_server()  # o resto da conversa vai e volta do daemon de verdade
        rotas.append(ws)

    pagina = abrir(navegador=webkit, rota_ws=proxy)
    for fonte in range(8):
        for k in range(3):
            item = {"id": f"rajada-{fonte}-{k}", "title": f"Manchete {k} da fonte {fonte} com título bem comprido",
                    "subtitle": f"Fonte {fonte}", "kind": "news", "ts": time.time(), "url": "http://127.0.0.1:1/x"}
            rotas[0].send(json.dumps({"type": "feed", "item": item}))
        pagina.wait_for_timeout(40)
    fim, estado = time.time() + 1.5, {}
    while time.time() < fim:
        estado = pagina.evaluate(SOBREPOSTOS_JS)
        if estado == {"itens": 5, "sobrepostos": 0}:
            break
        pagina.wait_for_timeout(50)
    assert estado == {"itens": 5, "sobrepostos": 0}
    expect(pagina.locator("#noticias li").first).to_contain_text("Manchete 2 da fonte 7")
