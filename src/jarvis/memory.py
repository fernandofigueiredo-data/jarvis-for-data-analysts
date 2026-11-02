"""Memória persistente em SQLite: conversas, memórias, notícias vistas e contadores."""
import re
import sqlite3
import threading
import time
import unicodedata

from jarvis import config


def _key(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"https?://|www\.|\.(com|br|news|org|net)\b", "", t)
    return re.sub(r"[^a-z0-9]", "", t)

SCHEMA = """
create table if not exists turns (id integer primary key, ts real, role text, text text);
create table if not exists memories (id integer primary key, ts real, text text);
create table if not exists news (url text primary key, source text, title text, ts real);
create table if not exists counters (name text primary key, value integer);
create table if not exists decisoes (id integer primary key, arquivo text, texto text, ts real);
create table if not exists kpis (nome text primary key collate nocase, definicao text, ultimo text, ultimo_alerta text);
create table if not exists glossario (termo text primary key collate nocase, definicao text, ts real);
"""


class Memory:
    def __init__(self, path=config.DATA_DIR / "jarvis.db") -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        try:  # bancos de antes do resumo diário: a descrição do feed é a base do resumo e da checagem de cópia
            self.db.execute("alter table news add column resumo text")
        except sqlite3.OperationalError:
            pass
        self.lock = threading.Lock()

    def _exec(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self.lock:
            rows = self.db.execute(sql, args).fetchall()
            self.db.commit()
            return rows

    def add_turn(self, role: str, text: str) -> None:
        self._exec("insert into turns (ts, role, text) values (?, ?, ?)", (time.time(), role, text))

    def recent_turns(self, n: int = 20) -> list[dict]:
        rows = self._exec("select ts, role, text from turns order by id desc limit ?", (n,))
        return [{"ts": ts, "role": r, "text": t} for ts, r, t in reversed(rows)]

    def search_turns(self, q: str, n: int = 20) -> list[dict]:
        rows = self._exec("select ts, role, text from turns where text like ? order by id desc limit ?", (f"%{q}%", n))
        return [{"ts": ts, "role": r, "text": t} for ts, r, t in rows]

    def remember(self, text: str) -> None:
        self._exec("insert into memories (ts, text) values (?, ?)", (time.time(), text))

    def memories(self, n: int = 50) -> list[str]:
        return [t for (t,) in self._exec("select text from memories order by id desc limit ?", (n,))]

    def glossario_salvar(self, termo: str, definicao: str) -> None:
        self._exec("insert into glossario (termo, definicao, ts) values (?, ?, ?) "
                   "on conflict(termo) do update set definicao = excluded.definicao, ts = excluded.ts",
                   (termo.strip(), definicao.strip(), time.time()))

    def glossario(self, n: int = 200) -> list[tuple[str, str]]:
        return self._exec("select termo, definicao from glossario order by ts desc limit ?", (n,))

    def decisao_anotar(self, arquivo: str, texto: str) -> None:
        self._exec("insert into decisoes (arquivo, texto, ts) values (?, ?, ?)", (arquivo, texto.strip(), time.time()))

    def decisoes(self, arquivo: str) -> list[str]:
        return [t for (t,) in self._exec("select texto from decisoes where arquivo = ? order by id", (arquivo,))]

    def kpi_salvar(self, nome: str, definicao: str) -> None:
        self._exec("insert into kpis (nome, definicao) values (?, ?) "
                   "on conflict(nome) do update set definicao = excluded.definicao, ultimo = null, ultimo_alerta = null",
                   (nome.strip(), definicao))

    def kpis(self) -> list[tuple[str, str, str | None, str | None]]:
        return self._exec("select nome, definicao, ultimo, ultimo_alerta from kpis order by nome")

    def kpi_resultado(self, nome: str, ultimo: str, ultimo_alerta: str | None) -> None:
        self._exec("update kpis set ultimo = ?, ultimo_alerta = ? where nome = ?", (ultimo, ultimo_alerta, nome))

    def kpi_remover(self, nome: str) -> bool:
        antes = len(self.kpis())
        self._exec("delete from kpis where nome = ?", (nome.strip(),))
        return len(self.kpis()) < antes

    def bump(self, name: str, by: int = 1) -> None:
        self._exec("insert into counters (name, value) values (?, ?) "
                   "on conflict(name) do update set value = value + excluded.value", (name, by))

    def set_counter(self, name: str, value: int) -> None:
        self._exec("insert into counters (name, value) values (?, ?) "
                   "on conflict(name) do update set value = excluded.value", (name, value))

    def counter(self, name: str) -> int:
        rows = self._exec("select value from counters where name = ?", (name,))
        return rows[0][0] if rows else 0

    def news_seen(self, url: str) -> bool:
        return bool(self._exec("select 1 from news where url = ?", (url,)))

    def add_news(self, url: str, source: str, title: str, resumo: str = "") -> None:
        self._exec("insert or ignore into news (url, source, title, ts, resumo) values (?, ?, ?, ?, ?)",
                   (url, source, title, time.time(), resumo))

    def news_since(self, ts: float) -> list[dict]:
        rows = self._exec("select url, source, title, ts, coalesce(resumo, '') from news where ts >= ? order by ts desc", (ts,))
        return [{"url": u, "source": s, "title": t, "ts": x, "resumo": r} for u, s, t, x, r in rows]

    def latest_news(self, source: str | None = None, n: int = 10) -> list[dict]:
        rows = self._exec("select url, source, title, ts from news order by ts desc, rowid desc limit 500")
        items = [{"url": u, "source": s, "title": t, "ts": ts} for u, s, t, ts in rows]
        if source:
            # "Educadados", "educadados.com.br", "Data hackers news": compara sem acento, espaço nem domínio
            want = _key(source)
            items = [i for i in items if _key(i["source"]) in want or want in _key(i["source"])
                     or want in _key(i["url"])]
        return items[:n]

    def stats(self) -> dict:
        return {
            "memories": self._exec("select count(*) from memories")[0][0],
            "sessionTurns": self._exec("select count(*) from turns where role = 'user'")[0][0],
            "toolCalls": self.counter("tool_calls"),
        }


memory = Memory()
