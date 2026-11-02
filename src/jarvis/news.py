"""Notícias das fontes escolhidas em sources.json: RSS quando existe, senão lê os links da página."""
import json
import re
import threading
import time
import unicodedata
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
import trafilatura
from bs4 import BeautifulSoup

from jarvis import config
from jarvis.events import bus
from jarvis.memory import memory

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
status: dict[str, str] = {}  # fonte -> "ok" | mensagem de erro, para o painel
digest_textos: list[str] = []  # títulos e descrições entregues pelo último resumo: base da checagem de cópia


def load_sources() -> list[dict]:
    return json.loads(config.SOURCES_FILE.read_text(encoding="utf-8"))


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"},
                        follow_redirects=True, timeout=20)


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def scrape_html(src: dict, client: httpx.Client) -> list[tuple[str, str]]:
    """(url, título) dos artigos listados na página, na ordem em que aparecem."""
    r = client.get(src["url"])
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    pattern = re.compile(src["padrao_link"])
    host = urlparse(src["url"]).netloc
    found: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        path = urlparse(href).path if href.startswith("http") else href.split("?")[0].split("#")[0]
        if href.startswith("http") and urlparse(href).netloc != host:
            continue
        if not pattern.match(path):
            continue
        url = urljoin(src["url"], path)
        heading = a.find(["h1", "h2", "h3", "h4"])
        title = _clean_title((heading or a).get_text(" "))
        if len(title) > len(found.get(url, "")):  # o mesmo link aparece em card e em botão; fica o texto maior
            found[url] = title
    return [(u, t or u.rsplit("/", 1)[-1].replace("-", " ").capitalize()) for u, t in found.items()]


def fetch_rss(src: dict) -> list[tuple[str, str, str]]:
    """(url, título, descrição do feed). A descrição é curta e só serve de base para o resumo; nunca é repetida."""
    feed = feedparser.parse(src["rss"], agent=UA)
    out = []
    for e in feed.entries:
        desc = _clean_title(re.sub(r"<[^>]+>", " ", e.get("summary") or ""))[:400]
        out.append((e.link, _clean_title(e.title), desc))
    return out


_seeded = False


def seed_feed() -> None:
    """Ao ligar, as duas manchetes mais recentes de cada fonte vão para o feed, para ele não abrir vazio."""
    global _seeded
    if _seeded:
        return
    _seeded = True
    for src in reversed(load_sources()):
        for item in reversed(memory.latest_news(src["nome"], 2)):
            bus.feed_item(item["title"], "news", src["nome"], item["url"])


def refresh(announce: bool = True) -> int:
    """Busca todas as fontes, grava as novas e publica no feed. Retorna quantas eram novas."""
    new = 0
    first_run = not memory.latest_news(n=1)
    if not first_run:
        seed_feed()
    with _client() as client:
        for src in load_sources():
            name = src["nome"]
            fonte_nova = not memory.latest_news(name, 1)
            try:
                items = fetch_rss(src) if src.get("modo") == "rss" else [(u, t, "") for u, t in scrape_html(src, client)]
                if not items:
                    raise RuntimeError("nenhum artigo encontrado (o layout pode ter mudado)")
                for url, title, desc in reversed(items[:20]):
                    if memory.news_seen(url):
                        continue
                    memory.add_news(url, name, title, desc)
                    new += 1
                    # Na primeira coleta de uma fonte tudo é "novo"; só anuncia os três mais recentes dela
                    if announce and (not (first_run or fonte_nova) or (url, title, desc) in items[:3]):
                        bus.feed_item(title, "news", name, url)
                status[name] = "ok"
            except Exception as exc:
                status[name] = f"falhou: {exc}"
                bus.feed_item(f"{name}: não consegui ler as notícias", "warn", str(exc)[:120])
    return new


# ------------------------------------------------------------------ resumo diário
TEMAS = [t.strip() for t in config.NEWS_THEMES.split(",") if t.strip()]


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in t if not unicodedata.combining(c)))


def digest(horas: float = 36, n: int = 8) -> list[dict]:
    """Notícias novas da janela, sem repetidas, ordenadas pelos temas do usuário (config + glossário de dados)."""
    temas = TEMAS + [t for t, _ in memory.glossario(40)]
    ranq = []
    for i in memory.news_since(time.time() - horas * 3600):
        texto = _norm(f"{i['title']} {i['resumo']}")
        hits = [t for t in temas if _norm(t) and f" {_norm(t)} " in f" {texto} "]
        ranq.append((len(hits), i["ts"], {**i, "temas": hits}))
    ranq.sort(key=lambda x: (x[0], x[1]), reverse=True)
    vistos, unicos = set(), []
    for item in ranq:  # entre repetidas, fica a mais bem ranqueada
        # o mesmo assunto republicado por agregadores, que acrescentam " - Nome do site" ao título
        chave = " ".join(_norm(re.sub(r"\s[-–|]\s[^-–|]+$", "", item[2]["title"])).split()[:8])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(item)
    return [i for _, _, i in unicos[:n]]


def copia_longa(resumo: str, originais: list[str], n: int = 8) -> list[str]:
    """Trechos de n+ palavras do resumo iguais a um original (título ou descrição): indício de reprodução."""
    palavras = _norm(resumo).split()
    base = [" ".join(_norm(o).split()) for o in originais if o]
    return [" ".join(palavras[i:i + n]) for i in range(len(palavras) - n + 1)
            if any(" ".join(palavras[i:i + n]) in b for b in base)]


def article_text(url: str, limit: int = 6000) -> str:
    with _client() as client:
        r = client.get(url)
        r.raise_for_status()
    text = trafilatura.extract(r.text, include_comments=False, include_tables=False) or ""
    return text[:limit]


def start_loop() -> None:
    def loop() -> None:
        while True:
            try:
                n = refresh()
                print(f"  notícias: {n} novas")
            except Exception as exc:
                print(f"  notícias falharam: {exc}")
            time.sleep(config.NEWS_INTERVAL_S)
    threading.Thread(target=loop, daemon=True, name="news").start()
