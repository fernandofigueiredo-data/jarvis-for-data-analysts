"""Conversa de ponta a ponta: perguntas pelo painel, rota rápida, ferramentas, comandos rápidos, interrupção e erro.

O cérebro é o falso (cerebro_falso.py); rota rápida, timers, fala, feed, agentes e histórico são os de verdade.
"""
import re
import time

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import (  # noqa: E402
    cartao,
    conversa,
    esperar_evento,
    esperar_ocioso,
    esperar_resposta,
    eventos,
    falas_na_conversa,
    item_do_feed,
    perguntar,
    status,
)
from playwright.sync_api import expect  # noqa: E402

CAPITAL = "A capital da Austrália é Camberra, senhor."


def test_pergunta_pelo_cabecalho_abre_a_conversa_e_a_resposta_fica_na_tela(pagina):
    expect(pagina.locator("canvas")).to_be_visible()  # o globo é carregado sob demanda
    pagina.evaluate("""() => { const globo = document.querySelector('canvas').closest('section'); window.__legenda = [];
        new MutationObserver(() => { for (const t of globo.innerText.split('\\n'))
          if (/^(Você|Jarvis):/.test(t) && !window.__legenda.includes(t)) window.__legenda.push(t) })
          .observe(globo, {subtree: true, childList: true, characterData: true}) }""")
    desde = perguntar(pagina, "qual a capital da Austrália?")
    expect(conversa(pagina)).to_be_visible()
    assert esperar_resposta(pagina, desde) == CAPITAL
    fases = esperar_ocioso(pagina, desde)
    assert fases[0] == "thinking" and "speaking" in fases
    pagina.wait_for_timeout(3000)
    expect(falas_na_conversa(pagina).get_by_text(CAPITAL)).to_be_visible()  # continua legível depois da fala
    expect(falas_na_conversa(pagina).get_by_text("qual a capital da Austrália?")).to_be_visible()
    legenda = pagina.evaluate("() => window.__legenda")
    assert "Você: qual a capital da Austrália?" in legenda and any(t.startswith("Jarvis: A capital") for t in legenda)


@pytest.mark.parametrize("enviar", ["Enter", "seta"])
def test_pergunta_pelo_fale_com_o_jarvis(pagina, enviar):
    rodape = pagina.locator("footer")
    rodape.get_by_role("button", name=re.compile("Fale com o Jarvis")).click()
    campo = rodape.get_by_placeholder("Digite um comando para o Jarvis…")
    campo.fill(f"anote o teste pelo rodapé com {enviar}")
    desde = time.time()
    if enviar == "Enter":
        campo.press("Enter")
    else:
        rodape.get_by_role("button", name="Enviar").click()
    resposta = esperar_resposta(pagina, desde)
    assert resposta == f"Certo, senhor. Anotei: anote o teste pelo rodapé com {enviar}."
    expect(falas_na_conversa(pagina).get_by_text(resposta)).to_be_visible()
    expect(rodape.get_by_role("button", name=re.compile("Fale com o Jarvis"))).to_be_visible()  # o campo fechou


def test_rota_rapida_responde_sem_o_cerebro(pagina, daemon):
    desde = perguntar(pagina, "que horas são?")
    resposta = esperar_resposta(pagina, desde, timeout=5)
    assert re.fullmatch(r"São \d+ (e \d\d|horas)\.", resposta)
    assert time.time() - desde < 2.5
    assert "[rota rápida: time]" in daemon.log()


@pytest.mark.lento
def test_timer_da_rota_rapida_dispara_avisa_e_fala(pagina, daemon):
    desde = perguntar(pagina, "timer de 2 segundos")
    assert esperar_resposta(pagina, desde, timeout=5) == "Timer de 2 segundos iniciado."
    assert item_do_feed(pagina, desde, "Timer finalizado", timeout=10)
    pagina.wait_for_timeout(1500)
    falas = daemon.falas()
    assert "afplay /System/Library/Sounds/Glass.aiff" in falas and "O tempo acabou, senhor." in falas


def test_timer_quanto_falta_e_cancelar(pagina):
    for pergunta, resposta in [("timer de 5 minutos", r"Timer de 5 minutos iniciado\."),
                               ("quanto falta?", r"Faltam (4 minutos e \d+ segundos|5 minutos)\."),
                               ("cancela o timer", r"Timer cancelado\."),
                               ("cancela o timer", r"Não há timer rodando\.")]:
        desde = perguntar(pagina, pergunta)
        assert re.fullmatch(resposta, esperar_resposta(pagina, desde, timeout=5)), pergunta
        esperar_ocioso(pagina, desde)


def test_pergunta_com_ferramenta_mostra_o_uso_e_acende_o_agente(pagina):
    agentes = cartao(pagina, "Agentes ativos")
    desde = perguntar(pagina, "quais as notícias mais recentes?")
    resposta = esperar_resposta(pagina, desde)
    assert resposta.startswith("Na ") and "a manchete mais recente é:" in resposta
    assert item_do_feed(pagina, desde, "Usando jarvis · news_latest")
    fases = [e["phase"] for e in eventos(pagina, desde) if e.get("type") == "state"]
    assert "tooling" in fases
    # o agente acende enquanto o Jarvis trabalha, não só no próximo ciclo de 10 s do painel
    expect(agentes.locator("div.tile").filter(has_text="Pesquisa")).to_contain_text("Ativo", timeout=3000)


def test_iniciar_tarefa_pergunta_e_segue_a_conversa(pagina):
    desde = time.time()
    cartao(pagina, "Comandos rápidos").get_by_role("button", name=re.compile("^Iniciar tarefa")).click()
    assert esperar_resposta(pagina, desde) == "Qual é a tarefa, senhor?"
    janela = conversa(pagina)
    expect(janela.get_by_text("Iniciar tarefa", exact=True)).to_be_visible()  # o rótulo, não o prompt interno
    expect(janela).not_to_contain_text("Pergunte o que é")
    esperar_ocioso(pagina, desde)
    desde = perguntar(pagina, "comprar pão amanhã")
    assert esperar_resposta(pagina, desde) == "Certo, senhor. Anotei: comprar pão amanhã."


def test_abrir_calendario_le_a_agenda_de_hoje(pagina):
    desde = time.time()
    cartao(pagina, "Comandos rápidos").get_by_role("button", name=re.compile("^Abrir calendário")).click()
    resposta = esperar_resposta(pagina, desde)
    assert re.fullmatch(r"Hoje o senhor tem: Daily do time \(Concluído\); Revisão do painel \(Agora\); "
                        r"Entrega do relatório \(Em [12]h\d\d\)\.", resposta), resposta
    assert time.time() - desde < 5
    expect(conversa(pagina).get_by_text("O que tenho na agenda hoje?")).to_be_visible()


def test_resumo_de_noticias_resume_e_poe_os_links_no_feed(pagina):
    desde = time.time()
    cartao(pagina, "Comandos rápidos").get_by_role("button", name=re.compile("^Resumo de notícias")).click()
    resposta = esperar_resposta(pagina, desde)
    assert resposta.startswith("Três destaques de dados: ") and resposta.endswith("Os links estão no feed.")
    noticia = esperar_evento(pagina, lambda e: e.get("type") == "feed" and e["item"]["kind"] == "news", desde)
    assert noticia and noticia["item"]["url"].startswith("http://127.0.0.1:")
    expect(conversa(pagina).get_by_text("Resumo de notícias", exact=True)).to_be_visible()
    esperar_ocioso(pagina, desde)
    avisos = [e["item"]["title"] for e in eventos(pagina, desde) if e.get("type") == "feed" and e["item"]["kind"] == "warn"]
    assert avisos == []  # nada copiado da fonte


def test_briefing_executivo(pagina):
    desde = time.time()
    pagina.get_by_role("button", name="Briefing Executivo").click()
    resposta = esperar_resposta(pagina, desde)
    assert resposta.startswith("Bom dia, senhor. O próximo compromisso é Entrega do relatório. Destaque do dia: ")
    expect(conversa(pagina).get_by_text("Briefing executivo", exact=True)).to_be_visible()
    usos = {e["item"]["title"] for e in eventos(pagina, desde) if e.get("type") == "feed" and e["item"]["kind"] == "live"}
    assert {"Usando jarvis · agenda_today", "Usando jarvis · news_digest", "Usando dados · arquivos_recentes"} <= usos


def test_interrupcao_responde_a_segunda_pergunta_na_ordem(pagina, daemon):
    desde = perguntar(pagina, "me dê uma resposta longa")
    assert esperar_evento(pagina, lambda e: e.get("type") == "transcript" and e.get("role") == "assistant"
                          and not e.get("final"), desde)
    pagina.wait_for_timeout(700)
    desde2 = perguntar(pagina, "qual a capital da Austrália?")
    assert esperar_resposta(pagina, desde2, contendo="Camberra") == CAPITAL
    textos = [e["text"] for e in eventos(pagina, desde) if e.get("type") == "transcript" and e.get("final")]
    assert textos[0] == "me dê uma resposta longa" and textos[1].startswith("Esta é a frase número um")
    assert textos[2:] == ["qual a capital da Austrália?", CAPITAL]
    assert "Esta é a frase número doze de uma resposta longa." not in daemon.falas()  # a fala foi cortada


@pytest.mark.lento
def test_erro_do_cerebro_vira_mensagem_e_o_status_se_recupera(pagina):
    desde = perguntar(pagina, "simule um erro da API")
    assert esperar_resposta(pagina, desde) == "Infelizmente o cérebro não respondeu, senhor."
    aviso = item_do_feed(pagina, desde, "O Claude não respondeu")
    assert aviso and aviso["kind"] == "warn" and "Overloaded" in aviso["subtitle"]
    expect(falas_na_conversa(pagina).get_by_text("Infelizmente o cérebro não respondeu, senhor.")).to_be_visible()
    expect(pagina.get_by_role("button", name=re.compile(r"Notificações \(\d+ novas\)"))).to_be_visible()
    expect(pagina.get_by_text("STATUS DO SISTEMA", exact=True).locator("xpath=..")).to_contain_text("ATENÇÃO",
                                                                                                    timeout=13000)
    esperar_ocioso(pagina, desde)
    desde = perguntar(pagina, "qual a capital da Austrália?")
    esperar_resposta(pagina, desde)
    expect(pagina.get_by_text("STATUS DO SISTEMA", exact=True).locator("xpath=..")).to_contain_text("ÓTIMO",
                                                                                                    timeout=13000)
    assert status(pagina) == "STATUS DO SISTEMA ÓTIMO"


def test_fechar_a_conversa_enquanto_responde_nao_a_reabre(pagina):
    desde = perguntar(pagina, "me dê uma resposta longa outra vez")
    expect(conversa(pagina)).to_be_visible()
    pagina.get_by_role("button", name="Fechar conversa").click()
    esperar_resposta(pagina, desde, timeout=40)
    expect(conversa(pagina)).to_have_count(0)


def test_conversa_fecha_no_x_e_no_esc(pagina):
    nav = pagina.get_by_role("navigation", name="Seções")
    nav.get_by_role("button", name="Conversas", exact=True).click()
    expect(conversa(pagina)).to_be_visible()
    pagina.get_by_role("button", name="Fechar conversa").click()
    expect(conversa(pagina)).to_have_count(0)
    nav.get_by_role("button", name="Conversas", exact=True).click()
    conversa(pagina).press("Escape")
    expect(conversa(pagina)).to_have_count(0)


def test_historico_volta_depois_de_recarregar(pagina):
    pagina.reload()
    pagina.wait_for_function("() => /ÓTIMO|ATENÇÃO/.test(document.body.innerText)")
    pagina.get_by_role("navigation", name="Seções").get_by_role("button", name="Conversas", exact=True).click()
    janela = conversa(pagina)
    expect(janela.get_by_text("qual a capital da Austrália?").first).to_be_visible()
    expect(janela.get_by_text("Qual é a tarefa, senhor?")).to_be_visible()
    expect(janela.get_by_role("separator")).to_have_count(0)
    desde = perguntar(pagina, "que horas são?")
    esperar_resposta(pagina, desde)
    expect(janela.get_by_role("separator")).to_have_text(re.compile("Agora"))


def test_insights_de_memoria_contam_turnos_e_ferramentas(pagina, daemon):
    perguntas = sum(1 for t in daemon.json("api/conversations") if t["role"] == "user")
    memoria = cartao(pagina, "Insights de memória")
    fim, numeros = time.time() + 13, {}
    while time.time() < fim:  # o daemon publica os contadores a cada 10 s
        texto = memoria.inner_text()
        numeros = {rotulo: int(n) for n, rotulo in re.findall(r"(\d+)\s*\n\s*(Memórias|Turnos de sessão|Chamadas de ferramenta)", texto)}
        if numeros.get("Turnos de sessão") == perguntas:
            break
        pagina.wait_for_timeout(500)
    assert numeros.get("Turnos de sessão") == perguntas >= 10, numeros
    assert numeros.get("Chamadas de ferramenta", 0) >= 5 and numeros.get("Memórias") == 0, numeros
