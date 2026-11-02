import json
import sys
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from jarvis import config, dados, executor, kpis
from jarvis.memory import Memory
from jarvis.server import create_app

macos = pytest.mark.skipif(sys.platform != "darwin", reason="o isolamento usa o Seatbelt do macOS")


@pytest.fixture
def sessao(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_FOLDERS", [tmp_path])
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    monkeypatch.setattr(dados, "memory", Memory(tmp_path / "m.db"))
    linhas = ["nome_cliente,uf,canal,valor"] + [
        f"Pessoa {i},{'SP' if i % 3 else 'RJ'},{'Loja' if i % 2 else 'Web'},{100 + (i * 37) % 500}" for i in range(60)]
    linhas.append("Pessoa X,AC,Loja,999")  # AC: 1 linha
    (tmp_path / "vendas.csv").write_text("\n".join(linhas))
    (tmp_path / "segredo.txt").write_text("CANARIO")
    s = dados.Sessao()
    s.abrir("vendas")
    return s


def rodar(s, codigo, **kw):
    return executor.executar(codigo, s.pasta / "dados.parquet", s.rotulos, **kw)


@macos
def test_python_isolado_devolve_agregados_e_grafico(sessao):
    r = rodar(sessao, """
from scipy import stats
a, b = df[df.canal == "Loja"].valor, df[df.canal == "Web"].valor
t = stats.ttest_ind(a, b, equal_var=False)
resultado("teste", {"p_valor": t.pvalue, "n_loja": len(a)})
resultado("por_uf", df.groupby("uf").agg(media=("valor", "mean"), n=("valor", "size")))
df.groupby("uf").valor.sum().plot.bar()
grafico("Soma por UF")
print("fica no Mac")
""")
    assert 0 <= r["resultados"]["teste"]["p_valor"] <= 1 and r["resultados"]["teste"]["n_loja"] == 31
    assert [x["uf"] for x in r["resultados"]["por_uf"]] == ["RJ", "SP"]  # AC (n = 1) ficou de fora
    assert r["graficos"][0]["url"].startswith("/api/graficos/") and r["graficos"][0]["titulo"] == "Soma por UF"
    png = config.CACHE_DIR / "graficos" / r["graficos"][0]["url"].rsplit("/", 1)[1]
    assert png.read_bytes()[:4] == b"\x89PNG"
    assert "fica no Mac" not in json.dumps(r)


@macos
def test_linhas_cruas_e_nomes_nao_voltam(sessao):
    r = rodar(sessao, """
resultado("crua", df.head(3))
resultado("serie", df.valor.head(80))
resultado("nomes", df.groupby("nome_cliente").valor.sum())
resultado("um_nome", df.nome_cliente.iloc[0])
""")
    out = json.dumps(r, ensure_ascii=False)
    assert "Pessoa" not in out
    assert r["resultados"]["crua"] == executor.OMITIDO and r["recusas"]  # tabela sem coluna n
    assert len(r["resultados"]["serie"]) == executor.MAX_ITENS


@macos
def test_sandbox_bloqueia_arquivo_rede_shell_e_cita_sem_vazar(sessao, tmp_path):
    for codigo, tipo in ((f"open({str(tmp_path / 'segredo.txt')!r}).read()", "PermissionError"),
                         ("import socket; socket.create_connection(('example.com', 80), timeout=3)", "gaierror"),
                         ("import subprocess; subprocess.run(['/bin/ls'])", "PermissionError"),
                         ("float(df.nome_cliente.iloc[0])", "ValueError")):
        r = rodar(sessao, codigo)
        assert r["erro"]["tipo"] == tipo, (codigo, r)
        assert "Pessoa" not in r["erro"]["mensagem"] and "CANARIO" not in json.dumps(r)


@macos
def test_vigia_mata_memoria_e_tempo(sessao):
    assert "memória" in rodar(sessao, "x = [bytearray(100 * 2**20) for _ in range(30)]", mem_mb=600)["erro"]
    t = time.monotonic()
    assert "passou de 3 s" in rodar(sessao, "while True: pass", prazo_s=3)["erro"]
    assert time.monotonic() - t < 10


def test_sanear():
    lim = executor.Limites()
    out = executor.sanear({"media_geral": 1.5, "SP": 2, "Fábio Nunes": 3, "lista": list(range(30)),
                           "tabela": [{"uf": "SP", "n": 10}, {"uf": "AC", "n": 1}], "data": "2025-03-01",
                           "texto": "Fábio"}, {"SP", "uf"}, lim)
    assert out["media_geral"] == 1.5 and out["SP"] == 2 and out["data"] == "2025-03-01"
    assert out["texto"] == executor.OMITIDO and executor.OMITIDO + "2" in out
    assert len(out["lista"]) == executor.MAX_ITENS
    assert out["tabela"] == [{"uf": "SP", "n": 10}]


def test_rota_de_graficos(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    (tmp_path / "graficos").mkdir()
    (tmp_path / "graficos" / ("a" * 32 + ".png")).write_bytes(b"\x89PNG")
    c = TestClient(create_app(object()))
    assert c.get(f"/api/graficos/{'a' * 32}.png").content == b"\x89PNG"
    assert c.get("/api/graficos/..%2F..%2Fsegredo.png").status_code == 404
    assert c.get(f"/api/graficos/{'b' * 32}.png").status_code == 404


@pytest.fixture
def diario(tmp_path, monkeypatch):
    """Faturamento diário estável e queda de 40% no último dia fechado; o dia de hoje (aberto) despenca."""
    monkeypatch.setattr(config, "DATA_FOLDERS", [tmp_path])
    m = Memory(tmp_path / "k.db")
    monkeypatch.setattr(kpis, "memory", m)
    hoje = date.today()
    linhas = ["data,uf,valor"]
    for d in range(10, 0, -1):
        dia = hoje - timedelta(days=d)
        valor = 60 if d == 1 else 100
        linhas += [f"{dia},SP,{valor / 5}"] * 5
    linhas += [f"{hoje},SP,1"] * 5
    (tmp_path / "diario.csv").write_text("\n".join(linhas))
    return m


def kpi(**regra):
    return {"nome": "Faturamento diário de SP", "arquivo": "diario", "metrica": {"funcao": "soma", "coluna": "valor"},
            "por": ["data:dia"], "filtros": [{"coluna": "uf", "op": "=", "valor": "SP"}], "regra": regra}


def test_kpi_dispara_uma_vez_por_periodo_e_ignora_o_dia_aberto(diario):
    atual = kpis.criar(kpi(tipo="queda_pct", valor=10, janela=4))
    ontem = date.today() - timedelta(days=1)
    assert atual["disparou"] and atual["periodo"] == str(ontem) and f"em {ontem:%d/%m/%Y}," in atual["texto"]
    assert atual["variacao_pct"] == -40.0 and "40% abaixo da média dos 4 períodos anteriores (100)" in atual["texto"]
    assert kpis.conferir_todos() == []  # quem criou já ouviu este alerta: o laço não repete no mesmo período
    diario.kpi_resultado("Faturamento diário de SP", "{}", None)  # como se o alerta ainda não tivesse sido dado
    assert [a["nome"] for a in kpis.conferir_todos()] == ["Faturamento diário de SP"]
    assert kpis.conferir_todos() == []
    assert kpis.listar()[0]["ultimo"]["disparou"]


def test_kpi_limite_e_validacao(diario):
    assert not kpis.criar(kpi(tipo="queda_pct", valor=50, janela=4))["disparou"]
    # sem 'por' não há período a ignorar: o total inclui hoje (9 × 100 + 60 + 5 = 965)
    assert kpis.criar({**kpi(tipo="abaixo", valor=1000), "por": []})["valor"] == 965
    assert kpis.criar({**kpi(tipo="abaixo", valor=1000), "por": []})["disparou"]
    assert not kpis.criar({**kpi(tipo="acima", valor=1000), "por": []})["disparou"]
    for ruim in ({**kpi(tipo="queda_pct", valor=10), "por": []}, kpi(tipo="sobe", valor=1),
                 {**kpi(tipo="acima", valor=1), "por": ["data:dia", "uf"]}):
        with pytest.raises(dados.Recusa):
            kpis.criar(ruim)
