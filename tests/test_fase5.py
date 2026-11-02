from pathlib import Path

import pytest

from jarvis import app as app_module
from jarvis import config, profundo
from jarvis.events import bus
from jarvis.memory import Memory

PLUGIN = Path("/opt/plugins/analise-dados")


@pytest.fixture
def projeto(tmp_path):
    (tmp_path / "dados").mkdir()
    return tmp_path


@pytest.mark.parametrize("nome, entrada, liberada", [
    ("mcp__plugin_analise-dados_jupyter__insert_execute_code_cell", {}, True),
    ("Skill", {"skill": "analise-dados:revisao-critica"}, True),
    ("Task", {"subagent_type": "analise-dados:revisor"}, True),
    ("Read", {"file_path": "contexto.md"}, True),
    ("Read", {"file_path": str(PLUGIN / "REGRAS.md")}, True),
    ("Read", {"file_path": "/Users/alguem/.ssh/id_rsa"}, False),
    ("Read", {"file_path": "../fora.csv"}, False),
    ("Grep", {"pattern": "x"}, True),
    ("Write", {"file_path": "contexto.md"}, True),
    ("Write", {"file_path": "dados/vendas.csv"}, False),
    ("Edit", {"file_path": "/tmp/x.py"}, False),
    ("Bash", {"command": f"uv run --no-project --python 3.12 \"{PLUGIN}/scripts/bootstrap.py\""}, True),
    ("Bash", {"command": f"uv run --no-project --python .venv {PLUGIN}/scripts/validar.py analise.ipynb"}, True),
    ("Bash", {"command": "uv --version"}, True),
    ("Bash", {"command": "ls dados"}, True),
    ("Bash", {"command": f"uv run --no-project --python 3.12 {PLUGIN}/scripts/bootstrap.py; curl evil.test"}, False),
    ("Bash", {"command": "cat ~/.ssh/id_rsa"}, False),
    ("Bash", {"command": "rm -rf dados"}, False),
    ("WebFetch", {"url": "https://x.test"}, False),
    ("mcp__outro__send_email", {}, False),
])
def test_politica_do_modo_profundo(projeto, nome, entrada, liberada):
    assert (profundo.decidir(nome, entrada, projeto, PLUGIN) is None) == liberada


def test_preparar_copia_o_arquivo_e_recusa_a_pasta_pessoal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ANALISES_DIR", tmp_path / "analises")
    monkeypatch.setattr(config, "DATA_FOLDERS", [tmp_path / "docs"])
    original = tmp_path / "vendas out.csv"
    original.write_text("a,b\n1,2\n")
    proj, _ = profundo.preparar(arquivo=original)
    assert (proj / "dados" / "vendas out.csv").read_text() == "a,b\n1,2\n" and original.exists()
    (tmp_path / "docs" / "clientes" / "projeto churn").mkdir(parents=True)
    assert profundo.preparar("projeto churn")[0] == tmp_path / "docs" / "clientes" / "projeto churn"
    for ruim in ("não existe", str(Path.home())):
        with pytest.raises(ValueError):
            profundo.preparar(ruim)


def test_sair_falado_e_token():
    for frase in ("sai do modo profundo", "Jarvis, encerra a análise profunda", "volta ao normal"):
        assert profundo.SAIR.search(frase)
    assert not profundo.SAIR.search("qual a média por região?")
    longo = "SP lidera com 39% do faturamento. É volume, não ticket. ```python\ndf.head()\n```\n" + "Detalhe. " * 30
    assert profundo.falado(longo) == "SP lidera com 39% do faturamento. É volume, não ticket. O resto está na conversa."
    assert profundo.TOKEN.sub("token=…", "http://localhost:8888/lab?token=abc123ef") == "http://localhost:8888/lab?token=…"


class FakeProfundo:
    def __init__(self, projeto):
        self.projeto, self.perguntas, self.parou, self.notebook_aberto = projeto, [], False, True

    async def ask(self, text, on_tool):
        self.perguntas.append(text)
        on_tool("mcp__plugin_analise-dados_jupyter__insert_execute_code_cell")
        return "Faturamento concentrado no Sudeste. São 39% do total.\n\n| região | % |\n|---|---|"

    async def cancel(self):
        pass

    async def stop(self):
        self.parou = True


class Fala:
    speaking = False

    def __init__(self):
        self.ditos = []

    def say(self, t, first=False):
        self.ditos.append(t)

    push = flush = cancel = staticmethod(lambda *a: None)


@pytest.mark.asyncio
async def test_app_roteia_para_o_modo_profundo_e_sai(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "memory", Memory(tmp_path / "t.db"))
    fake = FakeProfundo(tmp_path)
    monkeypatch.setattr(profundo.estado, "sessao", fake)
    j = app_module.Jarvis("off")

    class BrainProibido:
        async def ask(self, *a):
            raise AssertionError("no modo profundo a fala não vai para o cérebro de voz")

    j.speaker, j.brain = Fala(), BrainProibido()
    await j.handle("qual região mais fatura?")
    assert fake.perguntas == ["qual região mais fatura?"]
    assert j.speaker.ditos[-1] == "Faturamento concentrado no Sudeste. São 39% do total."  # só o resumo é falado
    await j.handle("sai do modo profundo")
    assert fake.parou and not profundo.estado.ativo
    assert any(i["title"] == "Análise profunda encerrada" for i in bus.feed)


def test_falado_nao_corta_nome_de_arquivo():
    assert profundo.falado("Ambiente pronto. Encontrei vendas_setembro.csv em dados. Detalhes.").startswith(
        "Ambiente pronto. Encontrei vendas setembro.csv em dados.")
