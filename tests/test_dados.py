import json

import duckdb
import pytest

from jarvis import app as app_module
from jarvis import config, dados
from jarvis.events import bus
from jarvis.memory import Memory

LINHAS = [  # uf, canal, valor, data
    ("SP", "Loja", 1234.56, "2025-01-10"), ("SP", "Loja", 10.0, "2025-01-11"), ("SP", "Web", 99.9, "2025-02-01"),
    ("SP", "Web", 5000.0, "2025-02-02"), ("SP", "Loja", 0.5, "2025-03-03"), ("SP", "Web", 70.0, "2025-03-04"),
    ("RJ", "Loja", 300.0, "2025-01-05"), ("RJ", "Web", 1.0, "2025-01-06"), ("RJ", "Loja", 2.0, "2025-02-07"),
    ("RJ", "Web", 3.0, "2025-02-08"), ("RJ", "Loja", 4.0, "2025-03-09"), ("AC", "Web", 777.0, "2025-03-10"),
]


def br(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """Mesmos dados em dois formatos: o do Excel brasileiro e o internacional."""
    monkeypatch.setattr(config, "DATA_FOLDERS", [tmp_path])
    linhas_br = ["uf;canal;valor;data;obs"] + [
        f"{u};{c};{br(v)};{d[8:]}/{d[5:7]}/{d[:4]};Promoção – “leve 3” 10€" for u, c, v, d in LINHAS]
    (tmp_path / "vendas_excel.csv").write_bytes("\n".join(linhas_br).encode("cp1252"))
    linhas_int = ["uf,canal,valor,data"] + [f"{u},{c},{v},{d}" for u, c, v, d in LINHAS]
    (tmp_path / "vendas_utf8.csv").write_text("\n".join(linhas_int), encoding="utf-8")
    pessoas = ["cpf;nome_cliente;contato;uf;valor"] + [
        f"{i:03d}.456.789-{i % 100:02d};Pessoa {i % 7};p{i}@exemplo.test;{'SP' if i % 10 else 'AC'};{i},5"
        for i in range(60)]
    (tmp_path / "clientes.csv").write_bytes("\n".join(pessoas).encode("cp1252"))
    (tmp_path / "canario.txt").write_text("SEGREDO-DE-TESTE")
    return tmp_path


def test_excel_brasileiro_le_igual_ao_utf8(pasta):
    assert dados.detectar_codificacao(pasta / "vendas_excel.csv") == "cp1252"
    con_br, meta = dados.carregar(pasta / "vendas_excel.csv")
    con_int, _ = dados.carregar(pasta / "vendas_utf8.csv")
    assert meta["separador"] == ";" and meta["convertidas_de_texto_pt_br"] == ["valor"]
    soma = "select round(sum(valor), 2), min(data), max(data) from dados"
    assert con_br.execute(soma).fetchone() == con_int.execute(soma).fetchone()
    # cp1252 lido como iso8859_10/cp1250 viraria "Promoçăo"
    assert con_br.execute("select any_value(obs) from dados").fetchone()[0] == "Promoção – “leve 3” 10€"


def test_conexao_travada_nao_alcanca_arquivo_nem_rede(pasta):
    con, _ = dados.carregar(pasta / "vendas_utf8.csv")
    for sql in (f"select * from read_text('{pasta / 'canario.txt'}')", f"copy dados to '{pasta / 'vazou.csv'}'",
                "select * from read_csv('https://example.com/a.csv')", "install httpfs",
                "set enable_external_access=true"):
        with pytest.raises(duckdb.Error):
            con.execute(sql).fetchall()
    assert not (pasta / "vazou.csv").exists()


def test_agregar_omite_grupos_pequenos_e_agrupa_por_mes(pasta, monkeypatch):
    s = dados.Sessao()
    s.abrir("vendas excel")
    r = json.loads(s.agregar({"metricas": [{"funcao": "soma", "coluna": "valor"}], "por": ["uf"], "ordenar": "-soma_valor"}))
    assert [linha[0] for linha in r["linhas"]] == ["SP", "RJ"]  # AC tem 1 linha: omitido
    assert r["grupos_omitidos_por_terem_menos_de_k_linhas"] == 1
    por_mes = {"metricas": [{"funcao": "contagem"}], "por": ["data:mes"]}
    r = json.loads(s.agregar(por_mes))  # 4 vendas por mês, menos que K = 5
    assert r["linhas"] == [] and r["grupos_omitidos_por_terem_menos_de_k_linhas"] == 3
    monkeypatch.setattr(config, "K_ANONIMATO", 4)
    r = json.loads(s.agregar(por_mes))
    assert sorted(linha[0] for linha in r["linhas"]) == ["2025-01", "2025-02", "2025-03"]


def test_dado_pessoal_nao_sai(pasta):
    s = dados.Sessao()
    resumo = json.loads(s.abrir("clientes"))
    assert s.pessoais == {"cpf", "nome_cliente", "contato"}  # contato: pelo formato de e-mail
    por_coluna = {c["coluna"]: c for c in resumo["colunas"]}
    assert por_coluna["cpf"]["dado_pessoal"] and "mais_frequentes" not in por_coluna["nome_cliente"]
    assert "Pessoa" not in json.dumps(resumo) and "exemplo.test" not in json.dumps(resumo)
    for pedido in ({"metricas": [{"funcao": "soma", "coluna": "valor"}], "por": ["cpf"]},
                   {"metricas": [{"funcao": "soma", "coluna": "valor"}],
                    "filtros": [{"coluna": "contato", "op": "=", "valor": "p1@exemplo.test"}]},
                   {"metricas": [{"funcao": "maximo", "coluna": "uf"}]},
                   {"metricas": [{"funcao": "string_agg", "coluna": "uf"}]}):
        with pytest.raises(dados.Recusa):
            s.agregar(pedido)
    assert json.loads(s.agregar({"metricas": [{"funcao": "distintos", "coluna": "cpf"}]}))["linhas"][0][0] == 60


def test_filtro_nao_injeta_e_erro_nao_cita_celula(pasta):
    s = dados.Sessao()
    s.abrir("vendas utf8")
    r = json.loads(s.agregar({"metricas": [{"funcao": "contagem"}],
                              "filtros": [{"coluna": "uf", "op": "=", "valor": "SP' or 1=1 --"}]}))
    assert r["linhas"] == []
    with pytest.raises(dados.Recusa) as exc:  # o DuckDB diria "Could not convert string 'SP' ..."
        s.agregar({"metricas": [{"funcao": "contagem"}], "filtros": [{"coluna": "valor", "op": ">", "valor": "SP"}]})
    assert "SP" not in str(exc.value)


def test_localizar_so_nas_pastas_permitidas(pasta, tmp_path_factory):
    fora = tmp_path_factory.mktemp("fora") / "vendas_secretas.csv"
    fora.write_text("a,b\n1,2")
    assert dados.localizar("vendas excel")[0].name == "vendas_excel.csv"
    assert dados.localizar(str(fora)) == []
    assert dados.localizar("vendas secretas") == []


def test_calculadora_so_aritmetica():
    assert dados.calcular("1765072.7 * 1.125") == pytest.approx(1985706.7875)
    assert dados.calcular("round(100 * (1183.10 / 1201.76 - 1), 2)") == -1.55
    for ruim in ("__import__('os').system('ls')", "(1).__class__", "1,125", "9 ** 999"):
        with pytest.raises(dados.Recusa):
            dados.calcular(ruim)


@pytest.mark.parametrize("resposta, sem_origem", [
    ("SP lidera com R$ 1.765.072,70, o dobro do RJ (872.492,67).", []),
    ("SP iria a uns R$ 1,99 milhão.", []),  # arredondamento que a escrita indica
    ("SP iria a R$ 1.975.000.", ["1.975.000"]),  # conta de cabeça errada
    ("O e-commerce fica 1,55% abaixo, de 01/01/2025 a 31/12/2025.", []),  # sinal e data
    ("SP fatura 2,1 milhões.", ["2,1 milhões"]),
])
def test_validador(resposta, sem_origem):
    resultados = ['[["SP", 1765072.7], ["RJ", 872492.67]]', '{"resultado": 1985706.79, "dif": -1.55}',
                  '{"min": "2025-01-01", "max": "2025-12-31"}']
    assert dados.validar(resposta, resultados) == sem_origem


class BrainQueInventa:
    """Usa a ferramenta de dados e responde com um número que não veio dela."""

    async def ask(self, _text, on_text, on_tool):
        dados.sessao.agregar({"metricas": [{"funcao": "soma", "coluna": "valor"}], "por": ["uf"]})
        on_tool("mcp__dados__agregar")
        on_text("SP fatura 9.999,99.")
        return "SP fatura 9.999,99."


@pytest.mark.asyncio
async def test_turno_com_numero_inventado_vira_aviso(pasta, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "memory", Memory(tmp_path / "t.db"))
    monkeypatch.setattr(dados, "sessao", dados.Sessao())
    dados.sessao.abrir("vendas utf8")
    j = app_module.Jarvis("off")

    class Quieto:
        speaking = False
        say = push = flush = cancel = staticmethod(lambda *a: None)

    j.speaker, j.brain = Quieto(), BrainQueInventa()
    await j._ask("quanto SP fatura?")
    aviso = next(i for i in bus.feed if i["title"] == "Número sem origem nos dados")
    assert "9.999,99" in aviso["subtitle"]
    assert dados.sessao.conferir_turno("SP fatura 9.999,99.", "") == []  # a marca do turno foi zerada
