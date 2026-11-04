"""Leitura robusta de CSV brasileiro + perfil automático, tudo com DuckDB (o arquivo original nunca é alterado).

Ideia central: o modelo não lê o arquivo nem faz conta. Ele recebe o perfil calculado aqui.
"""
import json
import re
import sys
import tempfile
import time
from pathlib import Path

import duckdb
from charset_normalizer import from_bytes

AMOSTRA = 256 * 1024
NUM_BR = re.compile(r"^\s*-?(R\$\s*)?\d{1,3}(\.\d{3})*(,\d+)?\s*$|^\s*-?(R\$\s*)?\d+,\d+\s*$")


def detectar_codificacao(path: Path) -> str:
    amostra = path.open("rb").read(AMOSTRA)
    try:
        amostra.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as exc:
        if exc.start > len(amostra) - 4:  # corte no meio de um caractere multibyte no fim da amostra
            return "utf-8"
    # Achado da P2: o detector genérico chamou um cp1252 brasileiro de iso8859_10 (nórdico).
    # Regra prática: fora do UTF-8, cp1252 primeiro (é o que o Excel grava no Brasil); detector só se falhar.
    try:
        amostra.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        pass
    best = from_bytes(amostra).best()
    enc = (best.encoding if best else "cp1252").lower()
    # latin-1 e cp1252 só diferem em 0x80–0x9F (€, aspas curvas, travessão): cp1252 é o que o Excel grava no Brasil
    return "cp1252" if enc in {"latin_1", "iso8859_1", "cp1252", "windows-1252", "iso-8859-1"} else enc


def para_utf8(path: Path, enc: str) -> Path:
    """Copia transcodificada (em streaming) para uma pasta temporária; o original fica intocado."""
    if enc == "utf-8":
        return path
    dst = Path(tempfile.mkdtemp(prefix="jarvis_csv_")) / (path.stem + ".utf8.csv")
    with path.open("r", encoding=enc, errors="replace", newline="") as src, dst.open("w", encoding="utf-8", newline="") as out:
        while chunk := src.read(1 << 20):
            out.write(chunk)
    return dst


def abrir(path: str | Path) -> tuple[duckdb.DuckDBPyConnection, dict]:
    path = Path(path)
    t0 = time.perf_counter()
    enc = detectar_codificacao(path)
    utf8 = para_utf8(path, enc)
    con = duckdb.connect()
    lit = "'" + str(utf8).replace("'", "''") + "'"
    sniff = con.execute(f"select Delimiter, DateFormat from sniff_csv({lit})").fetchone()
    # tabela (não view): depois de carregar, o acesso a arquivos pode ser travado (ver P4)
    con.execute(f"create table bruto as select * from read_csv({lit})")
    tipos = dict(con.execute("select column_name, column_type from (describe bruto)").fetchall())
    convertidas = {}
    selects = []
    for col, tipo in tipos.items():
        q = f'"{col}"'
        if tipo == "VARCHAR":
            amostra = [v for (v,) in con.execute(f"select {q} from bruto where {q} is not null limit 2000").fetchall()]
            br = sum(bool(NUM_BR.match(v)) for v in amostra)
            if amostra and br / len(amostra) >= 0.95 and any("," in v for v in amostra):
                # R$ 1.234,56 -> 1234.56; o que não casa vira NULL e é contado no perfil
                expr = f"try_cast(replace(replace(regexp_replace({q}, '[R$\\s]', '', 'g'), '.', ''), ',', '.') as double)"
                convertidas[col] = {"de": "texto pt-BR", "para": "DOUBLE", "nao_convertidos": len(amostra) - br}
                selects.append(f"{expr} as {q}")
                continue
        selects.append(q)
    con.execute(f"create table dados as select {', '.join(selects)} from bruto")
    con.execute("drop table bruto")
    meta = {"arquivo": path.name, "codificacao": enc, "separador": sniff[0], "formato_data": sniff[1] or None,
            "colunas_convertidas": convertidas, "segundos_leitura": round(time.perf_counter() - t0, 3)}
    return con, meta


def perfil(con: duckdb.DuckDBPyConnection) -> dict:
    t0 = time.perf_counter()
    linhas = con.execute("select count(*) from dados").fetchone()[0]
    cols = []
    for nome, tipo, *_ in con.execute("describe dados").fetchall():
        q = f'"{nome}"'
        nulos, distintos = con.execute(f"select count(*) - count({q}), approx_count_distinct({q}) from dados").fetchone()
        c = {"coluna": nome, "tipo": tipo, "nulos_pct": round(100 * nulos / linhas, 2) if linhas else 0, "distintos": distintos}
        if tipo in ("BIGINT", "DOUBLE", "INTEGER", "DECIMAL", "HUGEINT") or tipo.startswith("DECIMAL"):
            mn, mx, med, mediana, q1, q3 = con.execute(
                f"select min({q}), max({q}), avg({q}), median({q}), quantile_cont({q}, .25), quantile_cont({q}, .75) from dados").fetchone()
            iqr = (q3 - q1) if q1 is not None else 0
            outl = con.execute(f"select count(*) from dados where {q} > ? or {q} < ?", [q3 + 3 * iqr, q1 - 3 * iqr]).fetchone()[0] if iqr else 0
            c |= {"min": mn, "max": mx, "media": round(med, 4) if med is not None else None, "mediana": mediana, "outliers_3iqr": outl}
        elif tipo == "DATE":
            c |= dict(zip(("min", "max"), map(str, con.execute(f"select min({q}), max({q}) from dados").fetchone())))
        else:
            top = con.execute(f"select {q}, count(*) n from dados group by 1 order by n desc limit 5").fetchall()
            c["top"] = [[v, n] for v, n in top]
            # variações de grafia: mesma chave depois de trim+lower
            var = con.execute(f"select count(distinct {q}) - count(distinct lower(trim({q}))) from dados").fetchone()[0]
            if var:
                c["variantes_grafia"] = var
        cols.append(c)
    dup = con.execute("select count(*) - (select count(*) from (select distinct * from dados)) from dados").fetchone()[0]
    alertas = []
    if dup:
        alertas.append(f"{dup} linhas duplicadas")
    for c in cols:
        if c["nulos_pct"] >= 5:
            alertas.append(f"{c['coluna']}: {c['nulos_pct']}% nulos")
        if c.get("variantes_grafia"):
            alertas.append(f"{c['coluna']}: {c['variantes_grafia']} grafias diferentes para o mesmo valor (espaços/maiúsculas)")
        if c.get("outliers_3iqr"):
            alertas.append(f"{c['coluna']}: {c['outliers_3iqr']} valores extremos (fora de 3×IQR)")
    # coluna que deveria ser número mas tem texto: maioria numérica com exceções
    for c in cols:
        if c["tipo"] == "VARCHAR":
            q = f'"{c["coluna"]}"'
            num, tot = con.execute(f"select count(try_cast({q} as double)), count({q}) from dados").fetchone()
            if tot and 0.8 <= num / tot < 1:
                exemplos = [v for (v,) in con.execute(f"select distinct {q} from dados where {q} is not null and try_cast({q} as double) is null limit 3").fetchall()]
                alertas.append(f"{c['coluna']}: {tot - num} valores não numéricos numa coluna quase toda numérica, ex.: {exemplos}")
    return {"linhas": linhas, "colunas": cols, "alertas": alertas, "segundos_perfil": round(time.perf_counter() - t0, 3)}


if __name__ == "__main__":
    con, meta = abrir(sys.argv[1])
    print(json.dumps({"leitura": meta, "perfil": perfil(con)}, ensure_ascii=False, indent=1, default=str))
