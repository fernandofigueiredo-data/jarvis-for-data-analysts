"""Estados vazios e de carregamento, com um daemon sem notícias, sem compromissos e com o Calendário lento.

Os testes seguem a ordem do arquivo: os primeiros precisam do feed vazio (nenhuma ferramenta usada ainda) e o último
espera o Calendário responder (40 s depois de o daemon subir).
"""
import re
import time

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import cartao, conversa, esperar_resposta, painel_dados  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

DAEMON_ARGS = ["--sem-noticias", "--agenda-vazia", "--agenda-atraso", "40"]


def test_feed_comeca_vazio(pagina):
    expect(pagina.locator("#noticias")).to_contain_text("Sem eventos ainda")


def test_notificacoes_sem_alertas(pagina):
    pagina.get_by_role("button", name="Notificações", exact=True).click()  # sem "(N novas)": nada a ver
    expect(pagina.get_by_role("dialog", name="Notificações")).to_contain_text("Nenhum alerta por enquanto.")


def test_conversa_sem_historico_explica_como_perguntar(pagina):
    pagina.get_by_role("navigation", name="Seções").get_by_role("button", name="Conversas", exact=True).click()
    expect(conversa(pagina)).to_contain_text("Pergunte pelo campo abaixo, pelo ⌘K ou dizendo “Ei Jarvis”.")


def test_dados_sem_arquivo_e_sem_monitores(pagina):
    pagina.get_by_role("navigation", name="Seções").get_by_role("button", name="Dados", exact=True).click()
    expect(painel_dados(pagina)).to_contain_text("Nenhum arquivo aberto. Diga “Jarvis, abre o arquivo vendas” ou solte "
                                                 "um CSV no painel.")
    expect(painel_dados(pagina).get_by_role("region", name="Monitores de KPI")).to_have_count(0)


def test_memoria_e_agentes_zerados(pagina):
    memoria = cartao(pagina, "Insights de memória").inner_text()
    assert re.findall(r"(\d+)\s*\n\s*(?:Memórias|Turnos de sessão|Chamadas de ferramenta)", memoria) == ["0", "0", "0"]
    expect(cartao(pagina, "Agentes ativos")).to_contain_text("0 em execução")


@pytest.mark.lento
def test_calendario_lento_mostra_que_esta_lendo_e_depois_que_nao_ha_nada(pagina):
    linha = cartao(pagina, "Linha do tempo da missão")
    expect(linha).to_contain_text("Lendo a agenda do Calendário…")
    desde = time.time()
    cartao(pagina, "Comandos rápidos").get_by_role("button", name=re.compile("^Abrir calendário")).click()
    # a ferramenta espera até 15 s pela primeira leitura e, sem ela, diz que ainda está lendo
    assert esperar_resposta(pagina, desde, timeout=25) == ("A agenda ainda está sendo lida do Calendário, senhor. "
                                                           "Pergunte de novo em um minuto.")
    expect(linha).to_contain_text("Nada agendado para hoje", timeout=45000)
    expect(linha).to_contain_text("0/0")
