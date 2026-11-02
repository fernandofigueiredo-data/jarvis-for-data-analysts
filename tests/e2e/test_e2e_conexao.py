"""O daemon cai e volta com o painel aberto (reinício do Jarvis): demonstração enquanto está fora, reconexão depois."""
import re

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import cartao, conversa, esperar_resposta, falas_na_conversa, perguntar, status  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

# valores que só existem nos dados de demonstração (ui/src/mock.ts)
DEMONSTRACAO = ["3.380", "São Paulo, BR", "Briefing matinal", "Cursor", "Wi-Fi · 5 GHz"]


@pytest.mark.lento
def test_daemon_cai_o_painel_avisa_e_reconecta_quando_ele_volta(pagina, daemon):
    # enquanto o daemon está fora, o navegador registra cada tentativa de reconexão como erro de console
    pagina.registro.esperar(r"WebSocket connection to 'ws://127\.0\.0\.1:\d+/ws' failed")
    daemon.stop()
    expect(pagina.get_by_text("STATUS DO SISTEMA", exact=True).locator("xpath=..")).to_contain_text("OFFLINE",
                                                                                                    timeout=5000)
    rodape = pagina.locator("footer")
    expect(rodape).to_contain_text("Modo demonstração · clique para digitar")
    pagina.get_by_role("button", name="Configurações").click()
    expect(pagina.get_by_role("dialog", name="Configurações")).to_contain_text("Offline · demonstração")
    pagina.keyboard.press("Escape")
    expect(cartao(pagina, "Insights de memória")).to_contain_text("3.380")  # a demonstração assume

    # offline, a pergunta é respondida pela demonstração, que diz que não executa nada
    perguntar(pagina, "abre o arquivo de vendas")
    expect(conversa(pagina)).to_be_visible()
    expect(falas_na_conversa(pagina)).to_contain_text("No modo demonstração eu só finjo executar.", timeout=12000)

    daemon.start()
    expect(pagina.get_by_text("STATUS DO SISTEMA", exact=True).locator("xpath=..")).to_contain_text("ÓTIMO",
                                                                                                    timeout=20000)
    expect(rodape).to_contain_text("Cidade Teste")
    texto = pagina.locator("body").inner_text()
    assert not [m for m in DEMONSTRACAO if m in texto], "dados da demonstração continuam na tela"
    assert status(pagina) == "STATUS DO SISTEMA ÓTIMO"
    # e volta a funcionar de verdade
    desde = perguntar(pagina, "qual a capital da Austrália?")
    assert esperar_resposta(pagina, desde) == "A capital da Austrália é Camberra, senhor."
    pagina.get_by_role("button", name="Configurações").click()
    expect(pagina.get_by_role("dialog", name="Configurações")).to_contain_text("Conectado ao daemon")
    expect(pagina.get_by_role("dialog", name="Configurações")).to_contain_text(re.compile(r"ws://127\.0\.0\.1:\d+/ws"))
