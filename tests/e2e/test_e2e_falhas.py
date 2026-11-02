"""Jarvis aberto com o Claude fora do ar (login vencido, sem rede): o painel diz o que houve e o resto funciona."""
import re

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import cartao, esperar_resposta, item_do_feed, perguntar  # noqa: E402
from playwright.sync_api import expect  # noqa: E402

DAEMON_ARGS = ["--cerebro-fora"]


def test_status_avisa_e_a_notificacao_diz_o_motivo(pagina):
    expect(pagina.get_by_text("STATUS DO SISTEMA", exact=True).locator("xpath=..")).to_contain_text("ATENÇÃO")
    expect(cartao(pagina, "Visão geral do AI Core")).to_contain_text("Conectando")
    expect(cartao(pagina, "Status dos LLMs").locator("div.tile").filter(has_text="Claude Code")).to_contain_text(
        "Não vinculado")
    pagina.get_by_role("button", name=re.compile(r"^Notificações")).click()
    expect(pagina.get_by_role("dialog", name="Notificações")).to_contain_text("Claude Code não conectou")
    expect(pagina.get_by_role("dialog", name="Notificações")).to_contain_text("sem login")


def test_pergunta_ao_claude_vira_mensagem_de_falha(pagina):
    desde = perguntar(pagina, "qual a capital da Austrália?")
    assert esperar_resposta(pagina, desde) == "Infelizmente o cérebro não respondeu, senhor."
    assert item_do_feed(pagina, desde, "O Claude não respondeu")


def test_rota_rapida_continua_funcionando(pagina):
    desde = perguntar(pagina, "que horas são?")
    assert re.fullmatch(r"São \d+ (e \d\d|horas)\.", esperar_resposta(pagina, desde, timeout=5))
