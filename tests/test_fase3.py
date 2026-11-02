import json
import sqlite3
import time

import pytest

from jarvis import app as app_module
from jarvis import config, dados, news
from jarvis.events import bus
from jarvis.memory import Memory


def test_resumo_diario_sai_uma_vez_por_dia_depois_do_horario():
    manha = time.strptime("2026-11-02 07:59", "%Y-%m-%d %H:%M")
    depois = time.strptime("2026-11-02 08:00", "%Y-%m-%d %H:%M")
    assert not app_module.digest_due(manha, "08:00", 0)
    assert app_module.digest_due(depois, "08:00", 20261101)
    assert not app_module.digest_due(depois, "08:00", 20261102)  # já saiu hoje
    assert not app_module.digest_due(depois, "oito", 0)


def test_banco_antigo_ganha_a_coluna_de_descricao(tmp_path):
    db = tmp_path / "antigo.db"
    with sqlite3.connect(db) as c:
        c.execute("create table news (url text primary key, source text, title text, ts real)")
        c.execute("insert into news values ('u', 'Fonte', 'Título', 1)")
    m = Memory(db)
    m.add_news("u2", "Fonte", "Outro", "descrição do feed")
    assert {i["title"]: i["resumo"] for i in m.news_since(0)} == {"Título": "", "Outro": "descrição do feed"}


def test_rss_traz_descricao_sem_html():
    xml = """<rss version="2.0"><channel><title>t</title><item><title>DuckDB 2.0</title><link>https://x.test/a</link>
    <description>&lt;p&gt;Nova versão &lt;b&gt;acelera&lt;/b&gt; consultas.&lt;/p&gt;</description></item></channel></rss>"""
    assert news.fetch_rss({"rss": xml}) == [("https://x.test/a", "DuckDB 2.0", "Nova versão acelera consultas.")]


def test_digest_tira_repetidas_e_ordena_pelos_temas(tmp_path, monkeypatch):
    m = Memory(tmp_path / "n.db")
    monkeypatch.setattr(news, "memory", m)
    monkeypatch.setattr(news, "TEMAS", ["DuckDB", "dbt"])
    m.add_news("https://a.test/1", "A", "Receita de bolo de cenoura", "")
    m.add_news("https://a.test/2", "A", "DuckDB 2.0 acelera consultas em Parquet grandes", "e integra com dbt")
    m.add_news("https://b.test/2", "Agregador", "DuckDB 2.0 acelera consultas em Parquet grandes - Site", "")
    m.glossario_salvar("NPS", "x")
    m.add_news("https://a.test/3", "A", "Como calcular NPS sem erro", "")
    titulos = [i["title"] for i in news.digest()]
    assert titulos[0].startswith("DuckDB") and len(titulos) == 3  # a republicação do agregador saiu
    assert titulos[1] == "Como calcular NPS sem erro"  # o glossário também conta como tema


def test_copia_longa():
    fonte = ["DuckDB 2.0 brings a new storage format that makes analytical queries over large Parquet files much faster"]
    assert news.copia_longa("Nova versão do DuckDB acelera consultas em arquivos Parquet grandes.", fonte) == []
    assert news.copia_longa("DuckDB 2.0 brings a new storage format that makes queries faster", fonte)


def test_fonte_nova_anuncia_so_as_tres_primeiras(tmp_path, monkeypatch):
    m = Memory(tmp_path / "n.db")
    m.add_news("https://velha.test/1", "Velha", "Antiga", "")  # não é a primeira coleta do Jarvis
    monkeypatch.setattr(news, "memory", m)
    monkeypatch.setattr(news, "load_sources", lambda: [{"nome": "Nova", "modo": "rss", "rss": "x"}])
    monkeypatch.setattr(news, "fetch_rss", lambda src: [(f"https://nova.test/{i}", f"N{i}", "") for i in range(10)])
    monkeypatch.setattr(news, "seed_feed", lambda: None)
    vistos = []
    monkeypatch.setattr(news.bus, "feed_item", lambda t, *a, **k: vistos.append(t))
    assert news.refresh() == 10
    assert sorted(vistos) == ["N0", "N1", "N2"]


@pytest.fixture
def versoes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_FOLDERS", [tmp_path])
    monkeypatch.setattr(dados, "memory", Memory(tmp_path / "d.db"))
    base = [(f"{i:03d}.111.222-33", "SP" if i % 2 else "RJ", 10.0 * i, f"2025-0{1 + i % 9}-01") for i in range(40)]
    a = ["cpf,uf,valor,data"] + [f"{c},{u},{v},{d}" for c, u, v, d in base]
    # B: 10 linhas removidas, 15 novas em MG, coluna nova
    b = ["cpf,uf,valor,data,canal"] + [f"{c},{u},{v},{d},Loja" for c, u, v, d in base[10:]] + [
        f"{900 + i}.111.222-33,MG,5.0,2025-10-0{1 + i % 9},Web" for i in range(15)]
    (tmp_path / "vendas_set.csv").write_text("\n".join(a))
    (tmp_path / "vendas_out.csv").write_text("\n".join(b))
    return tmp_path


def test_comparar_versoes_so_com_agregados(versoes):
    s = dados.Sessao()
    s.abrir("vendas set")
    r = json.loads(s.comparar("vendas out"))
    assert (r["linhas_a"], r["linhas_b"]) == (40, 45)
    assert (r["linhas_iguais"], r["linhas_so_em_a"], r["linhas_so_em_b"]) == (30, 10, 15)
    assert r["colunas_so_em_b"] == ["canal"]
    assert r["periodo_das_datas"]["data"]["b"][1] == "2025-10-09"
    assert ["MG", 0, 15] in r["categorias_que_mudaram_valor_linhas_a_linhas_b"]["uf"]
    assert "cpf" not in r["categorias_que_mudaram_valor_linhas_a_linhas_b"]
    assert ".111.222-33" not in json.dumps(r)  # nenhum CPF sai na comparação
    with pytest.raises(dados.Recusa):
        s.comparar("vendas set")  # o próprio arquivo não é outra versão


def test_decisoes_voltam_ao_reabrir_e_recentes_lista_so_nomes(versoes):
    s = dados.Sessao()
    s.abrir("vendas set")
    dados.memory.decisao_anotar("vendas_set.csv", "UF vazia conta como Não informada")
    assert json.loads(s.abrir("vendas set"))["decisoes_anteriores"] == ["UF vazia conta como Não informada"]
    nomes = {r["arquivo"] for r in dados.recentes(1)}
    assert nomes == {"vendas_set.csv", "vendas_out.csv"}
    assert set(dados.recentes(1)[0]) == {"arquivo", "pasta", "mb", "horas_atras"}


class BrainQueCopia:
    """Recebe o resumo diário e repete a descrição do feed em vez de resumir."""

    async def ask(self, _text, on_text, on_tool):
        news.digest_textos = ["DuckDB 2.0 brings a new storage format that makes analytical queries much faster"]
        on_tool("mcp__jarvis__news_digest")
        resp = "DuckDB 2.0 brings a new storage format that makes analytical queries much faster."
        on_text(resp)
        return resp


@pytest.mark.asyncio
async def test_resumo_que_copia_a_fonte_vira_aviso(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "memory", Memory(tmp_path / "t.db"))
    j = app_module.Jarvis("off")

    class Quieto:
        speaking = False
        say = push = flush = cancel = staticmethod(lambda *a: None)

    j.speaker, j.brain = Quieto(), BrainQueCopia()
    await j._ask("resumo de notícias")
    assert any(i["title"] == "O resumo repetiu um trecho da fonte" for i in bus.feed)
