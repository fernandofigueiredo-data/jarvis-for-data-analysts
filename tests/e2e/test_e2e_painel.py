"""Painel com o daemon de teste no ar: cabeçalho, barra lateral, cartões centrais e rodapé (sem conversa longa)."""
import re
import time

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import cartao, enviados, eventos, item_do_feed, status  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

NAV = ["Command Center", "AI Core", "Agentes", "Calendário", "Memória", "Conversas", "Notícias", "Dados"]


# ------------------------------------------------------------------ cabeçalho
def test_status_do_sistema_reflete_o_daemon(pagina):
    assert status(pagina) == "STATUS DO SISTEMA ÓTIMO"


def test_relogio_avanca(pagina):
    relogio = pagina.locator("header .font-mono").first
    antes = relogio.inner_text()
    assert re.fullmatch(r"\d\d:\d\d:\d\d", antes)
    expect(relogio).not_to_have_text(antes, timeout=2500)


def test_atalho_cmd_k_e_ctrl_k_focam_o_campo(pagina):
    campo = pagina.get_by_placeholder("Pesquisar ou comandar…")
    for tecla in ("Meta+k", "Control+k"):
        pagina.locator("body").click(position={"x": 5, "y": 5})
        pagina.keyboard.press(tecla)
        expect(campo).to_be_focused()


def test_campo_vazio_ou_so_espacos_nao_envia(pagina):
    campo = pagina.get_by_placeholder("Pesquisar ou comandar…")
    desde = time.time()
    for texto in ("", "    "):
        campo.fill(texto)
        campo.press("Enter")
    pagina.wait_for_timeout(500)
    assert enviados(pagina, desde) == []
    expect(pagina.get_by_role("region", name="Conversa")).to_have_count(0)


def test_botao_layout_alterna_o_modo_foco(pagina):
    botao = pagina.get_by_role("button", name="Layout: Modo Foco")
    expect(botao).to_have_attribute("aria-pressed", "false")
    botao.click()
    expect(botao).to_have_attribute("aria-pressed", "true")
    expect(pagina.get_by_role("heading", name="Agentes ativos")).to_have_count(0)
    expect(pagina.get_by_role("heading", name="Feed de inteligência")).to_be_visible()
    botao.click()
    expect(botao).to_have_attribute("aria-pressed", "false")
    expect(pagina.get_by_role("heading", name="Agentes ativos")).to_be_visible()


def test_notificacoes_listam_o_alerta_da_fonte_quebrada_e_marcam_como_visto(pagina):
    botao = pagina.get_by_role("button", name=re.compile(r"^Notificações"))
    expect(botao).to_have_accessible_name(re.compile(r"Notificações \(\d+ novas\)"))
    botao.click()
    dialogo = pagina.get_by_role("dialog", name="Notificações")
    expect(dialogo).to_contain_text("Fonte Quebrada: não consegui ler as notícias")
    expect(botao).to_have_accessible_name("Notificações")  # o ponto some depois de aberto
    pagina.keyboard.press("Escape")
    expect(dialogo).to_have_count(0)
    botao.click()
    expect(dialogo).to_be_visible()
    pagina.get_by_role("heading", name="Monitor do sistema").click()  # clique fora fecha
    expect(dialogo).to_have_count(0)


def test_configuracoes_mostram_o_que_esta_em_uso(pagina, daemon):
    pagina.get_by_role("button", name="Configurações").click()
    dialogo = pagina.get_by_role("dialog", name="Configurações")
    expect(dialogo).to_contain_text("Conectado ao daemon")
    expect(dialogo).to_contain_text(f"ws://127.0.0.1:{daemon.porta}/ws")
    expect(dialogo).to_contain_text("Ativo")
    expect(dialogo).to_contain_text("Desligada")
    expect(dialogo).to_contain_text(re.compile(r"\d de 7 conectados"))
    pagina.keyboard.press("Escape")
    expect(dialogo).to_have_count(0)


def test_selo_do_operador_e_estatico(pagina):
    selo = pagina.get_by_text("Operador", exact=True)
    expect(selo).to_be_visible()
    assert selo.evaluate("e => !e.closest('button, a, [role=button]')")


# ------------------------------------------------------------------ barra lateral
@pytest.mark.parametrize("item, destino", [("AI Core", "ai-core"), ("Agentes", "agentes"), ("Calendário", "calendario"),
                                           ("Memória", "memoria"), ("Notícias", "noticias")])
def test_navegacao_leva_ao_cartao(pagina, item, destino):
    nav = pagina.get_by_role("navigation", name="Seções")
    botao = nav.get_by_role("button", name=item, exact=True)
    botao.click()
    expect(botao).to_have_attribute("aria-current", "page")
    expect(pagina.locator(f"#{destino}")).to_be_focused()
    expect(pagina.locator(f"#{destino}")).to_be_in_viewport()


def test_navegacao_conversas_e_dados_abrem_os_paineis(pagina):
    nav = pagina.get_by_role("navigation", name="Seções")
    nav.get_by_role("button", name="Conversas", exact=True).click()
    expect(pagina.get_by_role("region", name="Conversa")).to_be_visible()
    nav.get_by_role("button", name="Dados", exact=True).click()
    expect(pagina.get_by_role("region", name="Dados", exact=True)).to_be_visible()


def test_navegacao_command_center_sai_do_modo_foco(pagina):
    pagina.get_by_role("button", name=re.compile("^Modo Foco")).click()
    expect(pagina.get_by_role("heading", name="Agentes ativos")).to_have_count(0)
    pagina.get_by_role("navigation", name="Seções").get_by_role("button", name="Command Center").click()
    expect(pagina.get_by_role("heading", name="Agentes ativos")).to_be_visible()


def test_modo_foco_da_barra_lateral_esconde_e_mostra_os_cartoes(pagina):
    botao = pagina.get_by_role("button", name=re.compile("^Modo Foco"))
    titulos = pagina.get_by_role("heading", level=2)
    antes = titulos.count()
    botao.click()
    expect(botao).to_have_text(re.compile("Modo Foco ativo"))
    assert titulos.count() < antes
    botao.click()
    expect(titulos).to_have_count(antes)


def test_microfone_avisa_que_a_voz_esta_desligada(pagina):
    lateral = pagina.locator("aside")
    expect(lateral).to_contain_text("Voz desligada (--mode off)")
    microfone = lateral.get_by_role("button", name="Segure para falar")
    desde = time.time()
    microfone.click()
    assert item_do_feed(pagina, desde, "Voz desligada"), "o clique no microfone não teve retorno"
    assert [m["type"] for m in enviados(pagina, desde)] == ["ptt", "ptt"]


def test_microfone_segurado_e_pelo_teclado(pagina):
    microfone = pagina.locator("aside").get_by_role("button", name="Segure para falar")
    caixa = microfone.bounding_box()
    desde = time.time()
    pagina.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
    pagina.mouse.down()
    expect(pagina.locator("aside")).to_contain_text("Ouvindo…")
    pagina.wait_for_timeout(800)
    pagina.mouse.up()
    microfone.focus()
    pagina.keyboard.down("Space")
    pagina.wait_for_timeout(400)
    pagina.keyboard.up("Space")
    pagina.wait_for_timeout(300)
    assert [m.get("down") for m in enviados(pagina, desde)] == [True, False, True, False]
    expect(pagina.locator("aside")).to_contain_text("Em espera")


# ------------------------------------------------------------------ cartões
def test_visao_geral_do_ai_core_vem_do_daemon(pagina):
    texto = cartao(pagina, "Visão geral do AI Core").inner_text()
    for esperado in ("AI Core\nAtivo", "Memória\n0 memórias", "Voz\nDesligada", "Agentes\n0 ativos", "Sistema\nÓtimo"):
        assert esperado in texto, texto
    assert "3.380" not in texto  # nada da demonstração


def test_globo_3d_renderiza(pagina):
    globo = pagina.locator("section").filter(has=pagina.locator("canvas")).first
    expect(globo.locator("canvas")).to_be_visible()
    expect(globo).to_contain_text("JARVIS")
    expect(globo).to_contain_text("Em espera")


def test_feed_mostra_noticias_e_abre_o_artigo_em_outra_aba(pagina):
    feed = pagina.locator("#noticias")
    noticia = feed.get_by_role("link").filter(has_text="Notícia").first
    expect(noticia).to_be_visible()
    with pagina.context.expect_page() as aba:
        noticia.click()
    nova = aba.value
    nova.wait_for_load_state()
    assert re.match(r"http://127\.0\.0\.1:\d+/(artigos|blog)/", nova.url)
    assert nova.title() and nova.title() in noticia.inner_text()


def test_feed_expande_e_recolhe(pagina):
    feed = pagina.locator("#noticias")
    itens = feed.locator("li")
    expect(itens).to_have_count(5)
    total = len([e for e in eventos(pagina) if e.get("type") == "snapshot"][0]["feed"])
    assert total > 5
    feed.get_by_role("button", name="Ver toda a inteligência").click()
    expect(itens).to_have_count(total)
    feed.get_by_role("button", name="Mostrar menos").click()
    expect(itens).to_have_count(5)


def test_agentes_listam_os_seis_em_espera(pagina):
    agentes = cartao(pagina, "Agentes ativos")
    expect(agentes).to_contain_text("0 em execução")
    for nome in ("Código", "Pesquisa", "Memória", "Navegação", "Tarefas", "Sistema"):
        expect(agentes).to_contain_text(nome)
    expect(agentes.get_by_text("Em espera")).to_have_count(6)


def test_linha_do_tempo_mostra_a_agenda_de_hoje(pagina):
    linha = cartao(pagina, "Linha do tempo da missão")
    expect(linha).to_contain_text("1/3")
    texto = linha.inner_text()
    assert texto.index("Daily do time") < texto.index("Revisão do painel") < texto.index("Entrega do relatório")
    expect(linha).to_contain_text("Concluído")
    expect(linha).to_contain_text("Agora")
    expect(linha).to_contain_text(re.compile(r"Em [12]h\d\d"))


def test_monitor_do_sistema_mostra_percentuais_reais(pagina):
    monitor = cartao(pagina, "Monitor do sistema")
    expect(monitor).to_contain_text("CPU")
    numeros = [int(n) for n in re.findall(r"(\d+)%", monitor.inner_text())]
    assert len(numeros) == 3 and all(0 <= n <= 100 for n in numeros)
    assert numeros[2] > 0  # disco nunca está vazio: o valor veio do daemon


def test_insights_de_memoria_e_status_dos_llms(pagina):
    memoria = cartao(pagina, "Insights de memória").inner_text()
    assert re.search(r"0\s+Memórias", memoria), memoria
    llms = cartao(pagina, "Status dos LLMs")
    expect(llms).to_contain_text("Claude Code")
    expect(llms.get_by_text("Conectado", exact=True).first).to_be_visible()
    for nome in ("OpenAI", "Gemini", "Groq", "OpenRouter", "ElevenLabs"):
        expect(llms).to_contain_text(nome)


# ------------------------------------------------------------------ rodapé
def test_rodape_mostra_local_clima_e_rede(pagina):
    rodape = pagina.locator("footer")
    expect(rodape).to_contain_text("Cidade Teste")
    expect(rodape).to_contain_text("24°C · Parcialmente nublado")
    rede = rodape.locator("[title^='Rede:']")
    expect(rede).to_have_attribute("title", re.compile(r"Rede: (Excelente|Boa|Fraca|Offline)"))


def test_fale_com_o_jarvis_abre_campo_e_esc_cancela(pagina):
    rodape = pagina.locator("footer")
    expect(rodape).to_contain_text("Clique para digitar")  # a voz está desligada: não diz "Estou ouvindo"
    abrir = rodape.get_by_role("button", name=re.compile("Fale com o Jarvis"))
    abrir.click()
    campo = rodape.get_by_placeholder("Digite um comando para o Jarvis…")
    expect(campo).to_be_focused()
    desde = time.time()
    campo.fill("texto que vou cancelar")
    campo.press("Escape")
    expect(campo).to_have_count(0)
    expect(abrir).to_be_focused()
    abrir.click()
    campo.press("Enter")  # vazio: não envia
    pagina.locator("body").click(position={"x": 5, "y": 5})  # sair do campo vazio fecha
    expect(campo).to_have_count(0)
    assert enviados(pagina, desde) == []


def test_comando_de_voz_sem_escuta_avisa_e_volta_a_espera(pagina):
    desde = time.time()
    cartao(pagina, "Comandos rápidos").get_by_role("button", name=re.compile("Iniciar conversa por voz")).click()
    assert item_do_feed(pagina, desde, "Voz desligada")
    pagina.wait_for_timeout(600)
    fases = [e["phase"] for e in eventos(pagina, desde) if e.get("type") == "state"]
    assert "listening" not in fases
    expect(pagina.get_by_role("region", name="Conversa")).to_have_count(0)
