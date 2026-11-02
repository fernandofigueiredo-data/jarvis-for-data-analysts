"""Daemon de teste: o Jarvis de verdade (`jarvis.app`), com o que é pago, externo ou lento simulado.

- Claude (pago): `cerebro_falso.CerebroFalso` no lugar do `Brain`; as ferramentas do Jarvis rodam de verdade.
- Fala: `say` e `afplay` falsos no PATH registram o texto em <dir>/fala.log e esperam o tempo da frase.
  O Keychain é ignorado, então a ElevenLabs (paga) fica desligada.
- Clima e cidade: valores fixos. Notícias: RSS e blog servidos por um servidor local, mais uma fonte quebrada.
  Calendário: três compromissos de hoje (a leitura real leva ~50 s e expõe a agenda pessoal).
- Banco, cache, uploads e pastas de dados ficam em <dir>; o data/jarvis.db real nunca é aberto.

Rodar à mão (o painel fica em http://127.0.0.1:8799):

    .venv/bin/python tests/e2e/daemon_teste.py --dir /tmp/jarvis-e2e --port 8799
"""
import argparse
import functools
import http.server
import json
import os
import random
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent

SAY = """#!/bin/sh
# say falso: registra a frase e "fala" pelo tempo aproximado dela
for a; do t=$a; done
printf '%s\\n' "$t" >> "$JARVIS_TESTE_FALA"
sleep $(awk -v n=${#t} 'BEGIN { s = n / 70; if (s < 0.3) s = 0.3; if (s > 1.5) s = 1.5; print s }')
"""
AFPLAY = """#!/bin/sh
printf 'afplay %s\\n' "$1" >> "$JARVIS_TESTE_FALA"
sleep 0.2
"""

NOTICIAS = [("duckdb", "DuckDB acelera consultas analíticas locais"),
            ("pandas", "Pandas 3 muda o tipo de texto"),
            ("bi", "Painéis de BI em tempo real"),
            ("sql", "SQL para análise de dados")]
POSTS = [("estatistica-para-analistas", "Estatística para analistas de dados"),
         ("dbt-na-pratica", "Modelagem com dbt na prática")]


def cpf(i: int) -> str:
    d = f"{(i * 7919) % 10**9:09d}"
    return f"{d[:3]}.{d[3:6]}.{d[6:]}-{i % 100:02d}"


def escrever_vendas(path: Path, novas: int = 0) -> None:
    """CSV como o Excel brasileiro grava: cp1252 (com acentos), ';', 'R$ 1.234,56' e datas dd/mm/aaaa. Maio a outubro de 2026,
    SP na frente, um grupo pequeno (AC, 2 linhas, omitido pelo anonimato k=5), UF vazia em 6% e uma linha duplicada."""
    rnd = random.Random(7)
    ufs = ["SP"] * 9 + ["RJ"] * 5 + ["MG"] * 4 + ["BA"] * 3
    linhas = []
    for i in range(200 + novas):
        mes, dia = 5 + i % 6, 1 + rnd.randrange(28)
        uf = "" if i % 17 == 3 else rnd.choice(ufs)
        valor = round(rnd.uniform(80, 2500), 2)
        linhas.append((f"{dia:02d}/{mes:02d}/2026", uf, rnd.choice(["Loja", "E-commerce", "Promoção"]),
                       f"Cliente {i}", cpf(i), valor))
    linhas += [("15/10/2026", "AC", "Loja", "Cliente AC 1", cpf(901), 310.5),
               ("16/10/2026", "AC", "Loja", "Cliente AC 2", cpf(902), 275.0)]
    linhas.append(linhas[0])
    reais = lambda v: "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    texto = "data_venda;uf;canal;cliente_nome;cpf;valor\n" + "".join(
        f"{d};{u};{c};{n};{p};{reais(v)}\n" for d, u, c, n, p, v in linhas)
    path.write_bytes(texto.replace("\n", "\r\n").encode("cp1252"))


def preparar(base: Path, porta_www: int) -> None:
    for sub in ("data", "cache", "pastas", "www/artigos", "www/blog", "bin"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    if not (base / "pastas/vendas_teste.csv").exists():
        escrever_vendas(base / "pastas/vendas_teste.csv")
        escrever_vendas(base / "pastas/vendas_teste_v2.csv", novas=12)
        os.utime(base / "pastas/vendas_teste.csv", (time.time() - 3600, time.time() - 3600))
    www = f"http://127.0.0.1:{porta_www}"
    itens = "".join(f"<item><title>{t}</title><link>{www}/artigos/{s}.html</link><description>Texto de apoio da "
                    f"notícia {s}, escrito só para o teste.</description></item>" for s, t in NOTICIAS)
    (base / "www/rss.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                                      f"<title>Fonte RSS Teste</title><link>{www}/</link><description>Teste"
                                      f"</description>{itens}</channel></rss>", encoding="utf-8")
    links = "".join(f'<a href="/blog/{s}"><h2>{t}</h2></a>' for s, t in POSTS)
    (base / "www/blog.html").write_text(f"<html><body>{links}</body></html>", encoding="utf-8")
    for s, t in [*NOTICIAS, *POSTS]:
        pasta = base / ("www/artigos" if (s, t) in NOTICIAS else "www/blog")
        (pasta / (f"{s}.html" if pasta.name == "artigos" else s)).write_text(
            f'<html><head><meta charset="utf-8"><title>{t}</title></head><body><h1>{t}</h1></body></html>',
            encoding="utf-8")
    for nome, corpo in (("say", SAY), ("afplay", AFPLAY)):
        (base / "bin" / nome).write_text(corpo, encoding="utf-8")
        (base / "bin" / nome).chmod(0o755)


def servir(pasta: Path) -> int:
    class Silencioso(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def guess_type(self, path):  # as páginas do blog não têm extensão
            return super().guess_type(path) if "." in Path(str(path)).name else "text/html"

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Silencioso, directory=str(pasta)))
    threading.Thread(target=srv.serve_forever, daemon=True, name="www-teste").start()
    return srv.server_address[1]


def eventos_de_hoje() -> list[dict]:
    """Como o JXA devolve: um compromisso já feito, um agora e um mais tarde."""
    agora = datetime.now().astimezone()
    faixa = [("Daily do time", -180, -150), ("Revisão do painel", -15, 15), ("Entrega do relatório", 120, 180)]
    return [{"title": t, "start": (agora + timedelta(minutes=a)).isoformat(), "allDay": False, "calendar": "Teste",
             "end": (agora + timedelta(minutes=b)).isoformat()} for t, a, b in faixa]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="pasta de trabalho (banco, cache, pastas de dados, fala.log)")
    ap.add_argument("--port", type=int, default=8799)
    ap.add_argument("--sem-noticias", action="store_true", help="nenhuma fonte de notícias (feed vazio)")
    ap.add_argument("--agenda-vazia", action="store_true", help="nenhum compromisso hoje")
    ap.add_argument("--agenda-atraso", type=float, default=0, help="segundos até o Calendário responder")
    ap.add_argument("--cerebro-fora", action="store_true", help="o Claude não conecta (login vencido, sem rede)")
    a = ap.parse_args()

    base = Path(a.dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    porta_www = servir(base / "www")
    preparar(base, porta_www)
    www = f"http://127.0.0.1:{porta_www}"
    fontes = [] if a.sem_noticias else [
        {"nome": "Fonte RSS Teste", "url": f"{www}/", "modo": "rss", "rss": f"{www}/rss.xml"},
        {"nome": "Blog Teste", "url": f"{www}/blog.html", "modo": "html", "padrao_link": "^/blog/[^/]+$"},
        {"nome": "Fonte Quebrada", "url": f"{www}/nao-existe", "modo": "html", "padrao_link": "^/x/"}]
    (base / "sources.json").write_text(json.dumps(fontes, ensure_ascii=False), encoding="utf-8")

    os.environ.update({
        "JARVIS_PORT": str(a.port), "JARVIS_DATA_DIR": str(base / "data"), "JARVIS_CACHE_DIR": str(base / "cache"),
        "JARVIS_PASTAS_DADOS": str(base / "pastas"), "JARVIS_UPLOAD_MAX_MB": "1", "JARVIS_RESUMO_HORA": "",
        "JARVIS_ABRIR_NOTEBOOK": "0", "JARVIS_LOCATION": "", "JARVIS_TESTE_FALA": str(base / "fala.log"),
        "PATH": f"{base / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}", "PYTHONUNBUFFERED": "1",
    })
    sys.path.insert(0, str(AQUI))

    from jarvis import keychain
    keychain.get_secret = lambda _nome: None  # antes de telemetry e tts copiarem a função

    from jarvis import agenda, config, telemetry
    config.SOURCES_FILE = base / "sources.json"
    telemetry.place = lambda: {"name": "Cidade Teste", "lat": -23.55, "lon": -46.63}
    telemetry.weather = lambda: {"tempC": 24, "desc": "Parcialmente nublado"}
    eventos = [] if a.agenda_vazia else eventos_de_hoje()
    inicio = time.time()

    def calendario(timeout: float = 0) -> list[dict]:
        time.sleep(max(0.0, inicio + a.agenda_atraso - time.time()))
        return eventos

    agenda.fetch = calendario

    from cerebro_falso import CerebroFalso

    import jarvis.app as app
    CerebroFalso.fora_do_ar = a.cerebro_fora
    app.Brain = CerebroFalso
    print(f"[teste] www {www} · pasta {base}", flush=True)
    app.run(mode="off", window=False)


if __name__ == "__main__":
    main()
