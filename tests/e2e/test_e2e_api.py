"""API HTTP e WebSocket do daemon: o que o painel usa e o que ele precisa recusar."""
import json
import re
import time

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import Daemon  # noqa: E402
from websockets.sync.client import connect  # noqa: E402


def abrir_ws(daemon: Daemon, origem: str | None = None):
    return connect(daemon.url.replace("http", "ws", 1) + "ws", origin=origem or daemon.url.rstrip("/"), open_timeout=5)


def receber_ate(sock, cond, timeout: float = 10) -> tuple[dict | None, list[dict]]:
    fim, vistos = time.time() + timeout, []
    while time.time() < fim:
        try:
            ev = json.loads(sock.recv(timeout=max(0.1, fim - time.time())))
        except TimeoutError:
            break
        vistos.append(ev)
        if cond(ev):
            return ev, vistos
    return None, vistos


def resposta(ev: dict) -> bool:
    return ev.get("type") == "transcript" and ev.get("role") == "assistant" and ev.get("final")


def esperar_noticias(daemon: Daemon) -> dict:
    fim = time.time() + 15
    while time.time() < fim:
        h = daemon.json("api/health")
        if "Fonte Quebrada" in h["news"]:
            return h
        time.sleep(0.2)
    raise AssertionError("a primeira coleta de notícias não terminou")


def test_conversas_comecam_vazias_e_a_busca_filtra(daemon):
    assert daemon.json("api/conversations") == []  # banco novo: nada do data/ real
    with abrir_ws(daemon) as s:
        s.recv(timeout=5)  # snapshot
        s.send(json.dumps({"type": "say", "text": "que horas são?"}))
        ev, _ = receber_ate(s, resposta)
    assert ev and re.match(r"São \d+ (e \d\d|horas)\.", ev["text"])
    turnos = daemon.json("api/conversations")
    assert [(t["role"], t["text"]) for t in turnos] == [("user", "que horas são?"), ("assistant", ev["text"])]
    assert [t["text"] for t in daemon.json("api/conversations?q=horas")] == ["que horas são?"]
    assert daemon.json("api/conversations?q=nada-parecido") == []


def test_saude_mostra_cerebro_voz_fala_e_cada_fonte(daemon):
    h = esperar_noticias(daemon)
    assert h["ok"] is True and h["brain"] is True
    assert h["voice"] == "off" and h["tts"] == "macOS (Luciana)"  # ElevenLabs (paga) desligada no teste
    assert h["news"]["Fonte RSS Teste"] == "ok" and h["news"]["Blog Teste"] == "ok"
    assert h["news"]["Fonte Quebrada"].startswith("falhou")


def test_noticias_filtram_por_fonte(daemon):
    esperar_noticias(daemon)
    todas = daemon.json("api/news")
    assert {i["source"] for i in todas} == {"Fonte RSS Teste", "Blog Teste"}
    assert all(i["url"].startswith("http://127.0.0.1:") and i["title"] for i in todas)
    so_rss = daemon.json("api/news?source=Fonte%20RSS%20Teste")
    assert so_rss and {i["source"] for i in so_rss} == {"Fonte RSS Teste"}
    assert daemon.json("api/news?source=fonte-que-nao-existe") == []


def test_arquivos_estaticos_do_painel(daemon):
    status, tipo, html = daemon.http("GET", "/")
    assert (status, tipo) == (200, "text/html")
    refs = re.findall(r'(?:src|href)="\./([^"]+)"', html.decode())
    assert any(r.endswith(".js") for r in refs) and any(r.endswith(".css") for r in refs) and "favicon.svg" in refs
    assert {r: daemon.http("GET", r)[0] for r in refs} == {r: 200 for r in refs}
    assert daemon.http("GET", "/assets/nao-existe.js")[0] == 404


@pytest.mark.parametrize("caminho", ["api/graficos/grafico.png", "api/graficos/" + "0" * 32 + ".png",
                                     "api/graficos/..%2F..%2Fdata%2Fjarvis.db", "api/graficos/" + "a" * 32 + ".svg"])
def test_graficos_so_servem_png_gerado(daemon, caminho):
    status, _, corpo = daemon.http("GET", caminho)
    assert status == 404, corpo[:200]


def enviar(daemon: Daemon, nome: str, corpo: bytes, origem: str | None = "daemon"):
    headers = {"Content-Type": "application/octet-stream"}
    if origem:
        headers["Origin"] = daemon.url.rstrip("/") if origem == "daemon" else origem
    status, _, resp = daemon.http("POST", f"api/upload?nome={nome}", corpo, headers)
    return status, json.loads(resp)


def test_upload_recusa_pagina_de_outra_origem(daemon):
    status, resp = enviar(daemon, "x.csv", b"a;b\n1;2\n", origem="http://evil.example.com")
    assert (status, resp) == (403, {"erro": "origem não permitida"})


def test_upload_recusa_extensao_que_nao_e_csv(daemon):
    status, resp = enviar(daemon, "planilha.xlsx", b"PK\x03\x04")
    assert status == 415 and ".csv" in resp["erro"] and ".tsv" in resp["erro"]


def test_upload_recusa_arquivo_vazio(daemon):
    status, resp = enviar(daemon, "vazio.csv", b"")
    assert (status, resp) == (400, {"erro": "arquivo vazio"})
    assert not (daemon.base / "data/arquivos/vazio.csv").exists()


def test_upload_recusa_acima_do_limite_sem_deixar_resto(daemon, pw):
    # o servidor responde 413 sem ler o resto e fecha a conexão (previsto no HTTP); o urllib, que manda o corpo
    # inteiro antes de ler a resposta, às vezes só vê o "connection reset". Os navegadores leem o 413, como este cliente
    api = pw.request.new_context(base_url=daemon.url)
    r = api.post("api/upload?nome=grande.csv", data=b"a;b\n" + b"1;2\n" * 330_000,  # ~1,3 MB; limite do teste: 1 MB
                 headers={"Origin": daemon.url.rstrip("/"), "Content-Type": "application/octet-stream"})
    assert (r.status, r.json()) == (413, {"erro": "arquivo acima de 1 MB"})
    api.dispose()
    assert not list((daemon.base / "data/arquivos").glob("grande*"))


def test_upload_sem_nome_e_recusado(daemon):
    status, _, _ = daemon.http("POST", "api/upload", b"a;b\n1;2\n", {"Origin": daemon.url.rstrip("/")})
    assert status == 422


def test_upload_valido_grava_com_nome_seguro_e_abre_o_arquivo(daemon):
    csv = (daemon.base / "pastas/vendas_teste.csv").read_bytes()
    with abrir_ws(daemon) as s:
        s.recv(timeout=5)
        status, resp = enviar(daemon, "..%2F..%2Fvendas%20enviadas.csv", csv)
        assert status == 200 and resp == {"ok": True, "arquivo": "vendas enviadas.csv", "bytes": len(csv)}
        assert (daemon.base / "data/arquivos/vendas enviadas.csv").read_bytes() == csv
        pergunta, _ = receber_ate(s, lambda e: e.get("type") == "transcript" and e.get("role") == "user")
        ev, vistos = receber_ate(s, resposta, timeout=20)
    assert pergunta["text"] == "Arquivo enviado: vendas enviadas.csv"
    assert ev and ev["text"].startswith("Abri o vendas enviadas.csv: 203 linhas e 6 colunas"), ev
    dados = [e for e in vistos if e.get("type") == "data"]
    assert dados and dados[-1]["arquivo"] == "vendas enviadas.csv"
    # mesmo nome de novo: não sobrescreve
    status, resp = enviar(daemon, "vendas%20enviadas.csv", csv)
    assert status == 200 and resp["arquivo"] == "vendas enviadas-2.csv"


def test_websocket_recusa_outra_origem(daemon):
    with pytest.raises(Exception) as exc:
        with abrir_ws(daemon, origem="http://evil.example.com"):
            pass
    assert "403" in str(exc.value)


def test_websocket_comeca_com_snapshot_completo(daemon):
    with abrir_ws(daemon) as s:
        snap = json.loads(s.recv(timeout=5))
    assert snap["type"] == "snapshot"
    assert {"feed", "state", "health", "telemetry", "llms", "memory", "agents", "timeline", "kpis"} <= set(snap)
    assert snap["telemetry"]["location"] == "Cidade Teste"
    assert [e["title"] for e in snap["timeline"]["events"]] == ["Daily do time", "Revisão do painel", "Entrega do relatório"]


def test_websocket_ignora_mensagens_invalidas_e_segue_vivo(daemon):
    with abrir_ws(daemon) as s:
        s.recv(timeout=5)
        for msg in ["isto não é json", "[1, 2]", "42", "null", json.dumps({"type": "command", "id": "nao_existe"}),
                    json.dumps({"type": "command"}), json.dumps({"type": "say", "text": 123}),
                    json.dumps({"type": "say", "text": "   "}), json.dumps({"tipo": "say"})]:
            s.send(msg)
        s.send(json.dumps({"type": "say", "text": "qual a capital da Austrália?"}))
        ev, vistos = receber_ate(s, resposta, timeout=15)
    assert ev and ev["text"] == "A capital da Austrália é Camberra, senhor."
    perguntas = [e["text"] for e in vistos if e.get("type") == "transcript" and e.get("role") == "user"]
    assert perguntas == ["qual a capital da Austrália?"]
