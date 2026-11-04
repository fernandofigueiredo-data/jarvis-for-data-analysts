import re
from pathlib import Path

import pytest

from jarvis import config, fillers
from jarvis.brain.persona import pronome, system_prompt

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture
def pessoa(monkeypatch):
    def definir(nome: str, tratamento: str) -> None:
        monkeypatch.setattr(config, "NOME", nome)
        monkeypatch.setattr(config, "TRATAMENTO", tratamento)
    return definir


def test_senhor_com_nome(pessoa):
    pessoa("Fernando", "senhor")
    p = system_prompt()
    assert "assistente pessoal de voz do Fernando, rodando no Mac dele" in p
    assert '"Senhor" TEM POSIÇÃO' in p and "A renderização terminou, senhor" in p
    assert pronome() == ("ele", "dele")


def test_senhora_troca_pronomes(pessoa):
    pessoa("Ana", "senhora")
    p = system_prompt()
    assert "assistente pessoal de voz da Ana, rodando no Mac dela" in p
    assert '"Senhora" TEM POSIÇÃO' in p
    assert not re.search(r"\b(ele|dele)\b", p)
    assert pronome() == ("ela", "dela")


def test_sem_tratamento(pessoa):
    pessoa("", "nenhum")
    p = system_prompt()
    assert "assistente pessoal de voz do usuário" in p
    assert "TEM POSIÇÃO" not in p and "Não use senhor, senhora" in p


@pytest.mark.parametrize("tratamento, esperado", [
    ("senhor", ["O tempo acabou, senhor.", "Senhor, lembrete: pão."]),
    ("senhora", ["O tempo acabou, senhora.", "Senhora, lembrete: pão."]),
    ("nenhum", ["O tempo acabou.", "Lembrete: pão."]),
])
def test_falas_fixas(pessoa, tratamento, esperado):
    pessoa("", tratamento)
    assert [fillers.trat("O tempo acabou, senhor."), fillers.trat("Senhor, lembrete: pão.")] == esperado


def test_nenhum_nao_fala_senhor_nos_fillers(pessoa):
    pessoa("", "nenhum")
    for _ in range(40):
        assert "enhor" not in fillers.attention() + fillers.working("agregar")
        assert fillers.attention()


def test_nenhum_nome_pessoal_no_codigo():
    assert not [p for p in SRC.rglob("*.py") if "Fernando" in p.read_text(encoding="utf-8")]
