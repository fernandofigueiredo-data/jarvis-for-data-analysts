import json

import pytest
from fastapi.testclient import TestClient

from jarvis import config, dados
from jarvis.audio import stt
from jarvis.audio.tts import Speaker
from jarvis.memory import Memory
from jarvis.server import create_app


@pytest.fixture
def sessao(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_FOLDERS", [tmp_path])
    linhas = ["uf,valor,data_venda"] + [f"{'SP' if i % 3 else 'RJ'},{i * 10.5},2025-0{1 + i % 3}-10" for i in range(30)]
    (tmp_path / "vendas.csv").write_text("\n".join(linhas))
    s = dados.Sessao()
    monkeypatch.setattr(dados, "sessao", s)
    s.abrir("vendas")
    return s


def test_frase_com_numero_sem_origem_nao_e_falada(sessao):
    """O filtro do Speaker troca a frase antes de ela ir para a fila de fala."""
    fala = Speaker.__new__(Speaker)  # sem a thread de áudio
    fala.buffer, fala.queue = "", []
    fala.say = lambda t, first=False: fala.queue.append(t)
    r = json.loads(sessao.agregar({"metricas": [{"funcao": "soma", "coluna": "valor"}], "por": ["uf"], "ordenar": "-soma_valor"}))
    sp = r["linhas"][0][1]
    fala.guard = lambda f: "trocada" if sessao.conferir_frase(f, "") else f
    fala.push(f"SP soma {sp:.2f}".replace(".", ",") + ". RJ soma 123.456,78. Fim")
    fala.flush()
    assert fala.queue == [f"SP soma {sp:.2f}".replace(".", ",") + ".", "trocada", "Fim"]


def test_frase_so_e_conferida_se_o_turno_usou_dados(sessao):
    sessao.conferir_turno("", "")  # zera a marca deixada pelo abrir
    assert sessao.conferir_frase("São 20 e 22.", "") == []


def test_painel_mostra_perfil_e_ultimos_agregados_sem_linhas_cruas(sessao):
    sessao.agregar({"metricas": [{"funcao": "contagem"}], "por": ["data_venda:mes"]})
    p = sessao.painel()
    assert p["arquivo"] == "vendas.csv" and p["linhas"] == 30 and p["total_colunas"] == 3
    assert p["resultados"][0]["pedido"]["por"] == ["data_venda:mes"]
    assert sorted(r[0] for r in p["resultados"][0]["linhas"]) == ["2025-01", "2025-02", "2025-03"]
    assert set(p["colunas"][0]) == {"coluna", "tipo", "nulos_pct", "dado_pessoal"}


def test_prompt_do_whisper_tem_glossario_e_colunas(sessao, tmp_path, monkeypatch):
    m = Memory(tmp_path / "g.db")
    monkeypatch.setattr(stt, "memory", m)
    m.glossario_salvar("NPS", "promotores menos detratores")
    m.glossario_salvar("nps", "corrigido")  # mesma chave, sem diferenciar maiúsculas
    assert m.glossario() == [("NPS", "corrigido")]
    p = stt.build_prompt()
    assert p.startswith(stt.PROMPT) and "NPS" in p and "data venda" in p
    for i in range(200):
        m.glossario_salvar(f"termo_{i}", "x")
    assert len(stt.build_prompt()) <= len(stt.PROMPT) + len(" Termos de dados: .") + stt.VOCAB_MAX


class FakeJarvis:
    brain_ready, mode = True, "off"

    def __init__(self):
        self.turnos = []

    def submit(self, text, shown=None):
        self.turnos.append((text, shown))


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    j = FakeJarvis()
    return TestClient(create_app(j)), j, tmp_path


def test_upload_grava_e_abre_num_turno(cliente):
    c, j, pasta = cliente
    for _ in range(2):
        r = c.post("/api/upload", params={"nome": "../../vendas out.csv"}, content=b"a,b\n1,2\n",
                   headers={"origin": f"http://{config.HOST}:{config.PORT}"})
        assert r.status_code == 200
    assert sorted(p.name for p in pasta.iterdir()) == ["vendas out-2.csv", "vendas out.csv"]  # sem sair da pasta
    assert j.turnos[0][1] == "Arquivo enviado: vendas out.csv" and str(pasta / "vendas out.csv") in j.turnos[0][0]


def test_upload_recusa_origem_extensao_e_tamanho(cliente, monkeypatch):
    c, j, pasta = cliente
    ok = {"origin": f"http://{config.HOST}:{config.PORT}"}
    assert c.post("/api/upload", params={"nome": "a.csv"}, content=b"x",
                  headers={"origin": "http://evil.example.com"}).status_code == 403
    assert c.post("/api/upload", params={"nome": "a.sh"}, content=b"x", headers=ok).status_code == 415
    monkeypatch.setattr(config, "UPLOAD_MAX_BYTES", 10)
    assert c.post("/api/upload", params={"nome": "a.csv"}, content=b"x" * 11, headers=ok).status_code == 413
    assert list(pasta.iterdir()) == [] and j.turnos == []


def test_numero_cortado_entre_pedacos_nao_vira_duas_frases():
    """Achado no ponta a ponta: o pedaço "R$ 50." era falado como frase e "657,14" virava outra."""
    fala = Speaker.__new__(Speaker)
    fala.buffer, fala.queue, fala.guard = "", [], None
    fala.say = lambda t, first=False: fala.queue.append(t)
    for pedaco in ("São Paulo lidera com R$ 50.", "657,14, seguido do RJ com R$ 33.", "642,86. Fim"):
        fala.push(pedaco)
    fala.flush()
    assert fala.queue == ["São Paulo lidera com R$ 50.657,14, seguido do RJ com R$ 33.642,86.", "Fim"]
