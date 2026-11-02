"""Arquivos CSV: lê o padrão brasileiro, perfila e responde só com agregados.

Regra da casa (decisão do usuário, 02/11/2026): o Claude recebe nomes de colunas, um perfil sem valores
individuais e resultados agregados de grupos com pelo menos K linhas. Ele não escreve SQL: pede métricas,
agrupamentos e filtros, e esta camada monta a consulta. Linhas cruas e mensagens de erro do DuckDB (que
repetem o conteúdo das células) ficam no Mac. Provas de conceito em _pocs/p2_csv, p4_isolamento e p7_agregados.
"""
import ast
import json
import math
import operator
import os
import re
import shutil
import tempfile
import threading
import time
import unicodedata
from collections import Counter
from pathlib import Path

import duckdb
from charset_normalizer import from_bytes

from jarvis import config
from jarvis.memory import memory

AMOSTRA = 256 * 1024
EXTENSOES = {".csv", ".tsv"}  # os mesmos que o agent.py nega ao Read
IGNORAR_PASTAS = {"node_modules", "Library", "site-packages", "__pycache__", "venv", "env"}
NUM_BR = re.compile(r"^\s*-?(R\$\s*)?\d{1,3}(\.\d{3})*(,\d+)?\s*$|^\s*-?(R\$\s*)?\d+,\d+\s*$")
NUMERICOS = ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT", "TINYINT", "UBIGINT")
DATAS = ("DATE", "TIMESTAMP")
PII_NOME = re.compile(r"cpf|cnpj|\brg\b|e-?mail|telefone|celular|fone|nome|endere[cç]o|\bcep\b|placa|cart[aã]o|senha", re.I)
PII_VALOR = [re.compile(p) for p in (r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$", r"^[^@\s]+@[^@\s]+\.\w+$",
                                      r"^\(?\d{2}\)?\s?9?\d{4}-?\d{4}$")]
METRICAS = {"soma": "sum({c})", "media": "avg({c})", "mediana": "median({c})", "desvio": "stddev_samp({c})",
            "minimo": "min({c})", "maximo": "max({c})", "p25": "quantile_cont({c}, .25)",
            "p75": "quantile_cont({c}, .75)", "p90": "quantile_cont({c}, .9)",
            "contagem": "count({c})", "distintos": "count(distinct {c})",
            "participacao_pct": "100 * sum({c}) / sum(sum({c})) over ()"}
SO_NUMERO = {"soma", "media", "mediana", "desvio", "p25", "p75", "p90", "participacao_pct"}
PERIODOS = {"ano": "year({c})", "trimestre": "quarter({c})", "mes": "strftime(date_trunc('month', {c}), '%Y-%m')",
            "dia_semana": "dayname({c})", "dia": "cast({c} as date)"}
OPERADORES = {"=", "!=", ">", ">=", "<", "<=", "in", "entre"}


class Recusa(ValueError):
    """Pedido fora da regra; a mensagem vai para o Claude e não contém dados do arquivo."""


# ------------------------------------------------------------------ leitura
def detectar_codificacao(path: Path) -> str:
    amostra = path.open("rb").read(AMOSTRA)
    try:
        amostra.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as exc:
        if exc.start > len(amostra) - 4:  # caractere multibyte cortado no fim da amostra
            return "utf-8"
    # O detector genérico chamou cp1252 brasileiro de iso8859_10 e cp1250 ("Promoçăo"); o Excel no Brasil grava cp1252
    try:
        amostra.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        pass
    best = from_bytes(amostra).best()
    return best.encoding if best else "cp1252"


def _literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def carregar(path: Path, exportar: Path | None = None) -> tuple[duckdb.DuckDBPyConnection, dict]:
    """Tabela `dados` numa conexão própria, já travada: depois disso nenhum SQL alcança arquivo, rede ou extensão.
    `exportar`: Parquet com a tabela já limpa, gravado antes da trava, para o Python isolado ler."""
    t0 = time.perf_counter()
    enc = detectar_codificacao(path)
    tmp = Path(tempfile.mkdtemp(prefix="jarvis_csv_"))
    try:
        fonte = path
        if enc != "utf-8":  # cópia transcodificada; o original não é tocado
            fonte = tmp / "dados.csv"
            with path.open("r", encoding=enc, errors="replace", newline="") as src, \
                    fonte.open("w", encoding="utf-8", newline="") as out:
                while chunk := src.read(1 << 20):
                    out.write(chunk)
        con = duckdb.connect()
        lit = _literal(fonte)
        sniff = con.execute(f"select Delimiter, DateFormat from sniff_csv({lit})").fetchone()
        try:
            con.execute(f"create table bruto as select * from read_csv({lit})")
        except duckdb.Error:  # tipo mudou depois da amostra: lê o arquivo inteiro para decidir
            con.execute(f"create or replace table bruto as select * from read_csv({lit}, sample_size=-1)")
        tipos = dict(con.execute("select column_name, column_type from (describe bruto)").fetchall())
        convertidas, selects = [], []
        for col, tipo in tipos.items():
            q = f'"{col}"'
            if tipo == "VARCHAR":
                amostra = [v for (v,) in con.execute(f"select {q} from bruto where {q} is not null limit 2000").fetchall()]
                br = sum(bool(NUM_BR.match(v)) for v in amostra)
                if amostra and br / len(amostra) >= 0.95 and any("," in v for v in amostra):
                    # R$ 1.234,56 -> 1234.56; o que não casa vira nulo e aparece no perfil
                    selects.append(f"try_cast(replace(replace(regexp_replace({q}, '[R$\\s]', '', 'g'), '.', ''), ',', '.')"
                                   f" as double) as {q}")
                    convertidas.append(col)
                    continue
            selects.append(q)
        con.execute(f"create table dados as select {', '.join(selects)} from bruto")
        con.execute("drop table bruto")
        if exportar:
            con.execute(f"copy dados to {_literal(exportar)} (format parquet)")
        con.execute("SET memory_limit='1GB'")
        con.execute("SET enable_external_access=false")
        con.execute("SET lock_configuration=true")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return con, {"arquivo": path.name, "codificacao": enc, "separador": sniff[0], "formato_data": sniff[1] or None,
                 "convertidas_de_texto_pt_br": convertidas, "segundos": round(time.perf_counter() - t0, 2)}


def colunas(con) -> dict[str, str]:
    return dict(con.execute("select column_name, column_type from (describe dados)").fetchall())


def colunas_pessoais(con) -> set[str]:
    """Pelo nome da coluna ou porque metade de uma amostra parece CPF, e-mail ou telefone. É heurística."""
    out = set()
    for c, t in colunas(con).items():
        if PII_NOME.search(c):
            out.add(c)
        elif t == "VARCHAR":
            amostra = [v for (v,) in con.execute(f'select "{c}" from dados where "{c}" is not null limit 200').fetchall()]
            if amostra and sum(any(p.match(v.strip()) for p in PII_VALOR) for v in amostra) >= len(amostra) / 2:
                out.add(c)
    return out


def rotulos_permitidos(con, pessoais: set[str], k: int) -> set[str]:
    """Nomes de colunas e categorias (texto, fora das pessoais) com pelo menos k linhas."""
    out = set(colunas(con))
    for c, t in colunas(con).items():
        if t == "VARCHAR" and c not in pessoais:
            out |= {v for (v,) in con.execute(f'select "{c}" from dados where "{c}" is not null group by 1 '
                                              f"having count(*) >= ? limit 5000", [k]).fetchall()}
    return out


def perfil(con, pessoais: set[str], k: int) -> dict:
    """Perfil para o Claude: sem valores individuais (valores frequentes só de colunas não pessoais com ≥ k linhas)."""
    linhas = con.execute("select count(*) from dados").fetchone()[0]
    cols, alertas = [], []
    for nome, tipo in colunas(con).items():
        q = f'"{nome}"'
        nulos, distintos = con.execute(f"select count(*) - count({q}), approx_count_distinct({q}) from dados").fetchone()
        c = {"coluna": nome, "tipo": tipo, "nulos_pct": round(100 * nulos / linhas, 2) if linhas else 0,
             "distintos_aprox": distintos}
        if nome in pessoais:
            c["dado_pessoal"] = True
        elif tipo.startswith(NUMERICOS):
            mn, mx, med, mediana, q1, q3 = con.execute(
                f"select min({q}), max({q}), avg({q}), median({q}), quantile_cont({q}, .25), quantile_cont({q}, .75)"
                f" from dados").fetchone()
            c |= {"minimo": mn, "maximo": mx, "media": round(med, 4) if med is not None else None, "mediana": mediana}
            if q1 is not None and q3 > q1:
                iqr = q3 - q1
                n = con.execute(f"select count(*) from dados where {q} > ? or {q} < ?", [q3 + 3 * iqr, q1 - 3 * iqr]).fetchone()[0]
                if n:
                    alertas.append(f"{nome}: {n} valores extremos (fora de 3×IQR)")
        elif tipo.startswith(DATAS):
            mn, mx = con.execute(f"select min({q}), max({q}) from dados").fetchone()
            c |= {"minimo": str(mn), "maximo": str(mx)}
        else:
            top = con.execute(f"select {q}, count(*) n from dados where {q} is not null group by 1 order by n desc limit 6").fetchall()
            c["mais_frequentes"] = [[v, n] for v, n in top if n >= k]
            var = con.execute(f"select count(distinct {q}) - count(distinct lower(trim({q}))) from dados").fetchone()[0]
            if var:
                alertas.append(f"{nome}: {var} grafias diferentes para o mesmo valor (espaços ou maiúsculas)")
            num, tot = con.execute(f"select count(try_cast({q} as double)), count({q}) from dados").fetchone()
            if tot and 0.8 <= num / tot < 1:
                alertas.append(f"{nome}: {tot - num} valores não numéricos numa coluna quase toda numérica")
        if c["nulos_pct"] >= 5:
            alertas.append(f"{nome}: {c['nulos_pct']}% nulos")
        cols.append(c)
    dup = con.execute("select count(*) - (select count(*) from (select distinct * from dados)) from dados").fetchone()[0]
    if dup:
        alertas.insert(0, f"{dup} linhas duplicadas")
    return {"linhas": linhas, "total_colunas": len(cols), "colunas": cols, "alertas": alertas}


# ------------------------------------------------------------------ consultas
def _coluna(nome: str, cols: dict) -> tuple[str, str]:
    """'data_venda' ou 'data_venda:mes' -> (expressão SQL, rótulo)."""
    base, _, periodo = str(nome).partition(":")
    if base not in cols:
        raise Recusa(f"coluna inexistente: {base!r}. Colunas: {', '.join(cols)}")
    q = f'"{base}"'
    if not periodo:
        return q, base
    if periodo not in PERIODOS or not cols[base].startswith(DATAS):
        raise Recusa(f"período {periodo!r} só vale para colunas de data; use {', '.join(PERIODOS)}")
    return PERIODOS[periodo].format(c=q), f"{base}_{periodo}"


def _valor(v) -> str:
    if isinstance(v, bool) or v is None or isinstance(v, (list, dict)):
        raise Recusa("valor de filtro inválido")
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def montar_sql(pedido: dict, cols: dict, pessoais: set[str]) -> str:
    sel, grupos = [], []
    for g in pedido.get("por") or []:
        if str(g).partition(":")[0] in pessoais:
            raise Recusa(f"{g!r} parece dado pessoal: não pode ser usada para agrupar")
        expr, rotulo = _coluna(g, cols)
        sel.append(f'{expr} as "{rotulo}"')
        grupos.append(expr)
    for m in pedido.get("metricas") or [{"funcao": "contagem"}]:
        f, c = m.get("funcao"), m.get("coluna")
        if f not in METRICAS:
            raise Recusa(f"função {f!r} não permitida; use {', '.join(METRICAS)}")
        if not c:
            if f != "contagem":
                raise Recusa(f"{f} precisa de uma coluna")
            sel.append('count(*) as "linhas_contadas"')
            continue
        q, rotulo = _coluna(c, cols)
        tipo = cols[str(c).partition(":")[0]]
        if c in pessoais and f not in ("contagem", "distintos"):
            raise Recusa(f"{c!r} parece dado pessoal: só contagem e distintos")
        if f in SO_NUMERO and not tipo.startswith(NUMERICOS):
            raise Recusa(f"{f} exige coluna numérica; {c!r} é {tipo}")
        if f in ("minimo", "maximo") and not tipo.startswith(NUMERICOS + DATAS):
            raise Recusa(f"{f} só para números e datas: em texto devolveria o valor de uma linha")
        expr = METRICAS[f].format(c=q)
        if f in SO_NUMERO or f in ("minimo", "maximo") and tipo.startswith(NUMERICOS):
            expr = f"round({expr}, 4)"
        sel.append(f'{expr} as "{f}_{rotulo}"')
    onde = []
    for fl in pedido.get("filtros") or []:
        base = str(fl.get("coluna", "")).partition(":")[0]
        if base in pessoais:
            raise Recusa(f"{base!r} parece dado pessoal: não pode ser usada em filtro")
        q, _ = _coluna(fl.get("coluna", ""), cols)
        op, v = fl.get("op"), fl.get("valor")
        if op not in OPERADORES:
            raise Recusa(f"operador {op!r} não permitido; use {', '.join(sorted(OPERADORES))}")
        if op == "in":
            if not isinstance(v, list) or not v:
                raise Recusa("'in' precisa de uma lista de valores")
            onde.append(f"{q} in ({', '.join(_valor(x) for x in v)})")
        elif op == "entre":
            if not isinstance(v, list) or len(v) != 2:
                raise Recusa("'entre' precisa de [início, fim]")
            onde.append(f"{q} between {_valor(v[0])} and {_valor(v[1])}")
        else:
            onde.append(f"{q} {op} {_valor(v)}")
    sql = f"select {', '.join(sel)}, count(*) as __n from dados"
    if onde:
        sql += " where " + " and ".join(onde)
    if grupos:
        sql += " group by " + ", ".join(grupos)
    return sql


# ------------------------------------------------------------------ calculadora (projeções, variações)
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {"round": round, "abs": abs, "min": min, "max": max, "sqrt": math.sqrt}


def calcular(expressao: str) -> float:
    """Aritmética sobre números dados pelo modelo (nunca toca o arquivo): conta feita por código, não de cabeça."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 100:
                raise Recusa("expoente grande demais")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise Recusa("expressão não permitida: só números com ponto decimal, + - * / **, parênteses, "
                     "round, abs, min, max, sqrt")
    if len(expressao) > 300:
        raise Recusa("expressão longa demais")
    try:
        return ev(ast.parse(expressao, mode="eval"))
    except (SyntaxError, ZeroDivisionError, OverflowError, TypeError, ValueError) as exc:
        raise Recusa(f"conta inválida ({type(exc).__name__})") from None


# ------------------------------------------------------------------ validação dos números da resposta
NUM_BR_TEXTO = re.compile(r"(?<![\w.,])(-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?)\s*"
                          r"(%|mil\b|milh(?:ão|ao|ões|oes)\b|bilh(?:ão|ao|ões|oes)\b|bi\b|mi\b)?", re.I)
NUM_JSON = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
DATA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def numeros_resposta(texto: str) -> list[tuple[str, float, int]]:
    """(como foi escrito, valor, algarismos significativos) de cada número em pt-BR."""
    out = []
    for m in NUM_BR_TEXTO.finditer(texto):
        bruto, suf = m.group(1), (m.group(2) or "").lower()
        v = float(bruto.replace(".", "").replace(",", "."))
        v *= 1e3 if suf == "mil" else 1e6 if suf.startswith("milh") or suf == "mi" else 1e9 if suf.startswith("bi") else 1
        digitos = re.sub(r"\D", "", bruto).lstrip("0") or "0"
        sig = len(digitos) if "," in bruto else max(len(digitos.rstrip("0")), 1)
        out.append((m.group(0).strip(), v, sig))
    return out


def numeros_fonte(texto: str) -> list[float]:
    # datas ISO viram ano, mês e dia ("31/12/2025"); o sinal não importa ("1,55% abaixo")
    return [abs(float(x)) for x in NUM_JSON.findall(DATA_ISO.sub(lambda m: f"{m[1]} {m[2]} {m[3]}", texto))]


def validar(resposta: str, resultados: list[str], pergunta: str = "") -> list[str]:
    """Números da resposta sem origem num resultado de ferramenta (ou na pergunta). Aceita só o arredondamento que a
    escrita indica: "1,99 milhão" vale ±5 mil. Limite: não pega número verdadeiro atribuído à coisa errada."""
    fonte = [f for r in resultados for f in numeros_fonte(r)] + [abs(v) for _, v, _ in numeros_resposta(pergunta)]
    sem = []
    for escrito, v, sig in numeros_resposta(resposta):
        v = abs(v)
        if v == 0:
            ok = 0 in fonte
        else:
            meia = 0.5 * 10 ** (math.floor(math.log10(v)) - sig + 1) + 1e-9
            ok = any(abs(v - f) <= meia or abs(v - f * 100) <= meia for f in fonte)
        if not ok:
            sem.append(escrito)
    return sem


# ------------------------------------------------------------------ localizar arquivos
def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)))


def permitido(path: Path, pastas: list[Path]) -> bool:
    real = path.resolve()
    return any(real.is_relative_to(p.resolve()) for p in pastas if p.exists())


def _arquivos(pastas: list[Path]):
    """CSV/TSV até 3 níveis abaixo de cada pasta, sem pastas ocultas nem de dependências."""
    for pasta in pastas:
        if not pasta.is_dir():
            continue
        raiz = len(pasta.parts)
        for dirpath, dirnames, filenames in os.walk(pasta):
            atual = Path(dirpath)
            dirnames[:] = [] if len(atual.parts) - raiz >= 3 else \
                [d for d in dirnames if not d.startswith(".") and d not in IGNORAR_PASTAS]
            for f in filenames:
                p = atual / f
                if p.suffix.lower() in EXTENSOES and permitido(p, pastas):
                    yield p


def recentes(horas: float = 48, pastas: list[Path] | None = None) -> list[dict]:
    """Arquivos de dados criados ou alterados na janela: só nome, pasta, tamanho e idade (nada do conteúdo)."""
    pastas = pastas if pastas is not None else [*config.DATA_FOLDERS, config.UPLOAD_DIR]
    agora, out = time.time(), []
    for p in _arquivos(pastas):
        st = p.stat()
        if agora - st.st_mtime <= horas * 3600:
            out.append({"arquivo": p.name, "pasta": str(p.parent).replace(str(Path.home()), "~"),
                        "mb": round(st.st_size / 2**20, 1), "horas_atras": round((agora - st.st_mtime) / 3600, 1)})
    return sorted(out, key=lambda x: x["horas_atras"])[:20]


def localizar(nome: str, pastas: list[Path] | None = None) -> list[Path]:
    """Arquivos que casam com o nome falado ("vendas 2025" acha vendas_2025.csv), mais recentes primeiro."""
    pastas = pastas if pastas is not None else [*config.DATA_FOLDERS, config.UPLOAD_DIR]
    bruto = Path(nome.strip()).expanduser()
    if bruto.is_absolute():
        return [bruto] if bruto.is_file() and permitido(bruto, pastas) else []
    alvo = _norm(Path(nome).stem if Path(nome).suffix.lower() in EXTENSOES else nome)
    if not alvo:
        return []
    achados = [p for p in _arquivos(pastas) if alvo in _norm(p.stem)]
    exatos = [p for p in achados if _norm(p.stem) == alvo]
    return sorted(exatos or achados, key=lambda p: p.stat().st_mtime, reverse=True)


# ------------------------------------------------------------------ sessão
class Sessao:
    """O arquivo aberto agora e tudo que as ferramentas devolveram desde então (base do validador)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.con: duckdb.DuckDBPyConnection | None = None
        self.arquivo: Path | None = None
        self.meta: dict = {}
        self.pessoais: set[str] = set()
        self.resultados: list[str] = []
        self.usada = False  # alguma ferramenta de dados rodou neste turno
        self.resumo: dict = {}  # perfil do arquivo aberto, para o painel
        self.historico: list[dict] = []  # últimos resultados de agregar, para o painel
        self.nomes_colunas: list[str] = []  # para o prompt do Whisper (lido de outra thread, sem tocar no DuckDB)
        self.pasta: Path | None = None  # Parquet do arquivo aberto, lido pelo Python isolado
        self.rotulos: set[str] = set()  # textos que podem sair do Python: colunas e categorias com ≥ K linhas
        self.graficos: list[dict] = []  # gráficos do Python isolado, para o painel (não vão para o Claude)

    def registrar(self, obj) -> str:
        """Resultado de outra ferramenta de dados (ex.: monitor de KPI) entra na base do validador."""
        with self.lock:
            return self._registrar(obj)

    def _registrar(self, obj) -> str:
        texto = json.dumps(obj, ensure_ascii=False, default=str)
        self.resultados.append(texto)
        self.usada = True
        return texto

    def abrir(self, nome: str) -> str:
        candidatos = localizar(nome)
        if not candidatos:
            pastas = ", ".join(str(p).replace(str(Path.home()), "~") for p in [*config.DATA_FOLDERS, config.UPLOAD_DIR])
            raise Recusa(f"nenhum CSV com esse nome nas pastas permitidas ({pastas})")
        path = candidatos[0]
        pasta = Path(tempfile.mkdtemp(prefix="jarvis_sessao_"))
        try:
            con, meta = carregar(path, exportar=pasta / "dados.parquet")
        except Exception as exc:  # a mensagem do DuckDB pode citar uma célula: fica só no log local
            print(f"  dados: falha ao ler {path}: {exc}")
            shutil.rmtree(pasta, ignore_errors=True)
            raise Recusa(f"não consegui ler {path.name} ({type(exc).__name__})") from None
        with self.lock:
            if self.con:
                self.con.close()
            if self.pasta:
                shutil.rmtree(self.pasta, ignore_errors=True)
            self.pasta = pasta
            self.con, self.arquivo, self.meta, self.resultados, self.historico = con, path, meta, [], []
            self.graficos = []
            self.pessoais = colunas_pessoais(con)
            self.nomes_colunas = list(colunas(con))
            self.rotulos = rotulos_permitidos(con, self.pessoais, config.K_ANONIMATO)
            resumo = {**meta, **perfil(con, self.pessoais, config.K_ANONIMATO)}
            if decisoes := memory.decisoes(path.name):
                resumo["decisoes_anteriores"] = decisoes  # o que ele decidiu da última vez que abriu este arquivo
            self.resumo = resumo
            if len(candidatos) > 1:
                resumo["outros_arquivos_parecidos"] = [p.name for p in candidatos[1:5]]
            return self._registrar(resumo)

    def perfil(self) -> str:
        with self.lock:
            self._exigir()
            return self._registrar({**self.meta, **perfil(self.con, self.pessoais, config.K_ANONIMATO)})

    def agregar(self, pedido: dict, limite: int = 50) -> str:
        with self.lock:
            self._exigir()
            cols = colunas(self.con)
            sql = montar_sql(pedido, cols, self.pessoais)
            try:
                cur = self.con.execute(sql)
            except Exception as exc:
                print(f"  dados: consulta falhou: {exc}")
                raise Recusa(f"consulta inválida ({type(exc).__name__})") from None
            nomes = [d[0] for d in cur.description]
            linhas = cur.fetchall()
            n = nomes.index("__n")
            k = config.K_ANONIMATO
            ok = [r for r in linhas if r[n] >= k]
            ordem = str(pedido.get("ordenar") or "")
            if ordem.lstrip("-") in nomes:
                j = nomes.index(ordem.lstrip("-"))
                ok.sort(key=lambda r: (r[j] is None, r[j]), reverse=ordem.startswith("-"))
            limite = max(1, min(int(pedido.get("limite") or limite), 200))
            resultado = {"colunas": [c if c != "__n" else "linhas_no_grupo" for c in nomes], "linhas": ok[:limite],
                         "grupos_omitidos_por_terem_menos_de_k_linhas": len(linhas) - len(ok), "k": k,
                         "total_de_grupos": len(ok)}
            texto = self._registrar(resultado)
            self.historico = [{"pedido": pedido, **json.loads(texto)}, *self.historico][:5]
            return texto

    def comparar(self, nome: str) -> str:
        """Arquivo aberto (A) contra outra versão (B): linhas iguais e novas, colunas, totais e categorias que mudaram.
        Tudo agregado: contagens e somas; categorias só com pelo menos K linhas em um dos lados."""
        with self.lock:
            self._exigir()
            candidatos = [p for p in localizar(nome) if p.resolve() != self.arquivo.resolve()]
            if not candidatos:
                raise Recusa("não achei outra versão com esse nome nas pastas permitidas")
            outro = candidatos[0]
            try:
                con_b, _ = carregar(outro)
            except Exception as exc:
                print(f"  dados: falha ao ler {outro}: {exc}")
                raise Recusa(f"não consegui ler {outro.name} ({type(exc).__name__})") from None
            try:
                k = config.K_ANONIMATO
                ca, cb = colunas(self.con), colunas(con_b)
                pessoais = self.pessoais | colunas_pessoais(con_b)
                comuns = [c for c in ca if c in cb]
                n_a = self.con.execute("select count(*) from dados").fetchone()[0]
                n_b = con_b.execute("select count(*) from dados").fetchone()[0]
                out = {"a": self.arquivo.name, "b": outro.name, "linhas_a": n_a, "linhas_b": n_b,
                       "colunas_so_em_a": [c for c in ca if c not in cb], "colunas_so_em_b": [c for c in cb if c not in ca],
                       "tipo_mudou": {c: [ca[c], cb[c]] for c in comuns if ca[c] != cb[c]}}
                if comuns:  # linhas idênticas pelas colunas em comum; os hashes ficam aqui, só as contagens saem
                    expr = "hash(" + ", ".join(f'"{c}"' for c in comuns) + ")"
                    ha = Counter(h for (h,) in self.con.execute(f"select {expr} from dados").fetchall())
                    hb = Counter(h for (h,) in con_b.execute(f"select {expr} from dados").fetchall())
                    iguais = sum((ha & hb).values())
                    out |= {"linhas_iguais": iguais, "linhas_so_em_a": n_a - iguais, "linhas_so_em_b": n_b - iguais}
                numeros, periodos, categorias = {}, {}, {}
                for c in comuns:
                    if c in pessoais or ca[c] != cb[c]:
                        continue
                    q = f'"{c}"'
                    if ca[c].startswith(NUMERICOS):
                        sa, ma = self.con.execute(f"select round(sum({q}), 4), round(avg({q}), 4) from dados").fetchone()
                        sb, mb = con_b.execute(f"select round(sum({q}), 4), round(avg({q}), 4) from dados").fetchone()
                        numeros[c] = {"soma_a": sa, "soma_b": sb, "media_a": ma, "media_b": mb,
                                      "variacao_soma_pct": round(100 * (sb / sa - 1), 2) if sa else None}
                    elif ca[c].startswith(DATAS):
                        periodos[c] = {"a": [str(x) for x in self.con.execute(f"select min({q}), max({q}) from dados").fetchone()],
                                       "b": [str(x) for x in con_b.execute(f"select min({q}), max({q}) from dados").fetchone()]}
                    elif ca[c] == "VARCHAR":
                        conta = f"select {q}, count(*) from dados where {q} is not null group by 1"
                        va, vb = dict(self.con.execute(conta).fetchall()), dict(con_b.execute(conta).fetchall())
                        if len(va) > 50 or len(vb) > 50:
                            continue  # alta cardinalidade: lista de valores, não categorias
                        mudou = [[v, va.get(v, 0), vb.get(v, 0)] for v in set(va) | set(vb)
                                 if va.get(v, 0) != vb.get(v, 0) and max(va.get(v, 0), vb.get(v, 0)) >= k]
                        if mudou:
                            categorias[c] = sorted(mudou, key=lambda x: -abs(x[2] - x[1]))[:10]
                out |= {"numericas": numeros, "periodo_das_datas": periodos,
                        "categorias_que_mudaram_valor_linhas_a_linhas_b": categorias}
            finally:
                con_b.close()
            return self._registrar(out)

    def python(self, codigo: str) -> str:
        """Código no sandbox (executor.py) sobre o Parquet do arquivo aberto; volta só o que o filtro deixa."""
        from jarvis import executor  # importa pandas/matplotlib só quando o Python é usado
        with self.lock:
            self._exigir()
            parquet, rotulos = self.pasta / "dados.parquet", set(self.rotulos)
        out = executor.executar(codigo, parquet, rotulos)
        with self.lock:
            self.graficos = [*out.pop("graficos", []), *self.graficos][:4]
            if self.graficos and out.get("segundos") is not None:
                out["graficos_no_painel"] = len(self.graficos)
            return self._registrar(out)

    def calcular(self, expressao: str) -> str:
        valor = calcular(expressao)
        return self._registrar({"expressao": expressao, "resultado": round(valor, 6)})

    def _exigir(self) -> None:
        if self.con is None:
            raise Recusa("nenhum arquivo aberto; use abrir_arquivo primeiro")

    def painel(self) -> dict:
        """O que o painel mostra (o mesmo que o Claude viu: perfil seguro e agregados, nada de linha crua)."""
        r = self.resumo
        return {"arquivo": r.get("arquivo"), "linhas": r.get("linhas"), "total_colunas": r.get("total_colunas"),
                "codificacao": r.get("codificacao"), "separador": r.get("separador"),
                "colunas": [{k: c.get(k) for k in ("coluna", "tipo", "nulos_pct", "dado_pessoal")} for c in r.get("colunas", [])],
                "alertas": r.get("alertas", []), "resultados": self.historico, "graficos": self.graficos}

    def conferir_frase(self, frase: str, pergunta: str) -> list[str]:
        """Durante a fala: números da frase sem origem, se o turno usou dados (não zera a marca)."""
        return validar(frase, self.resultados, pergunta) if self.usada else []

    def conferir_turno(self, resposta: str, pergunta: str) -> list[str]:
        """Depois de um turno que usou dados: números da resposta sem origem. Zera a marca do turno."""
        usada, self.usada = self.usada, False
        return validar(resposta, self.resultados, pergunta) if usada else []


sessao = Sessao()
