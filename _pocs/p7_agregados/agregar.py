"""P7: "só agregados reais vão para o Claude", imposto pela ferramenta e não pelo prompt.

O modelo não escreve a consulta final. Ele pede métricas, agrupamentos e filtros; a ferramenta monta o SQL,
acrescenta count(*) e suprime grupos com menos de K linhas. Colunas com cara de dado pessoal não podem ser
agrupadas nem aparecem no perfil com valores. Mensagens de erro não ecoam valores do arquivo.
"""
import re

K = 5  # grupo menor que isso não sai (anonimato k)
FUNCOES = {"soma": "sum", "media": "avg", "mediana": "median", "contagem": "count", "distintos": "count_distinct",
           "desvio": "stddev_samp", "minimo": "min", "maximo": "max", "p25": "p25", "p75": "p75", "p90": "p90"}
NUMERICOS = ("BIGINT", "INTEGER", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT", "SMALLINT", "DATE", "TIMESTAMP")
OPS = {"=", "!=", ">", ">=", "<", "<=", "in", "entre"}
PII_NOME = re.compile(r"cpf|cnpj|rg\b|e-?mail|telefone|celular|fone|nome|endereco|endereço|cep|placa|cartao|cartão|senha", re.I)
PII_VALOR = [re.compile(p) for p in (r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$", r"^[^@\s]+@[^@\s]+\.\w+$", r"^\(?\d{2}\)?\s?9?\d{4}-?\d{4}$")]


class Recusa(ValueError):
    pass


def colunas(con) -> dict[str, str]:
    return dict(con.execute("select column_name, column_type from (describe dados)").fetchall())


def colunas_pessoais(con) -> set[str]:
    """Pelo nome ou porque ≥50% de uma amostra parece CPF, e-mail ou telefone."""
    out = set()
    for c, t in colunas(con).items():
        if PII_NOME.search(c):
            out.add(c); continue
        if t == "VARCHAR":
            amostra = [v for (v,) in con.execute(f'select "{c}" from dados where "{c}" is not null limit 200').fetchall()]
            if amostra and sum(any(p.match(v.strip()) for p in PII_VALOR) for v in amostra) >= len(amostra) / 2:
                out.add(c)
    return out


def _col(nome: str, cols: dict) -> str:
    if nome not in cols:
        raise Recusa(f"coluna inexistente: {nome!r}. Colunas: {', '.join(cols)}")
    return f'"{nome}"'


def _lit(v) -> str:
    if isinstance(v, bool) or v is None:
        raise Recusa("valor de filtro inválido")
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def montar(pedido: dict, cols: dict, pessoais: set) -> str:
    por = pedido.get("por") or []
    sel, grp = [], []
    for g in por:
        if g in pessoais:
            raise Recusa(f"{g!r} parece dado pessoal: não pode ser usada para agrupar")
        sel.append(_col(g, cols)); grp.append(_col(g, cols))
    for i, m in enumerate(pedido.get("metricas") or [{"funcao": "contagem"}]):
        f = m.get("funcao")
        if f not in FUNCOES:
            raise Recusa(f"função {f!r} não permitida; use {', '.join(FUNCOES)}")
        alias = re.sub(r"\W", "_", m.get("nome") or f"{f}_{m.get('coluna') or 'linhas'}")
        if f == "contagem" and not m.get("coluna"):
            sel.append(f'count(*) as "{alias}"'); continue
        c = m["coluna"]; q = _col(c, cols)
        if f in ("minimo", "maximo") and not cols[c].startswith(NUMERICOS):
            raise Recusa(f"{f} só para números e datas: em texto devolveria o valor de uma linha")
        if f in ("soma", "media", "mediana", "desvio", "p25", "p75", "p90") and not cols[c].startswith(NUMERICOS[:6]):
            raise Recusa(f"{f} exige coluna numérica; {c!r} é {cols[c]}")
        if c in pessoais and f not in ("contagem", "distintos"):
            raise Recusa(f"{c!r} parece dado pessoal: só contagem")
        if f == "distintos":
            sel.append(f'count(distinct {q}) as "{alias}"'); continue
        expr = {"p25": f"quantile_cont({q}, .25)", "p75": f"quantile_cont({q}, .75)", "p90": f"quantile_cont({q}, .9)"}.get(f, f"{FUNCOES[f]}({q})")
        sel.append(f'round({expr}, 4) as "{alias}"' if f not in ("contagem", "distintos", "minimo", "maximo") else f'{expr} as "{alias}"')
    onde = []
    for fl in pedido.get("filtros") or []:
        if fl["coluna"] in pessoais:
            raise Recusa(f"{fl['coluna']!r} parece dado pessoal: não pode ser usada em filtro")
        q, op, v = _col(fl["coluna"], cols), fl["op"], fl.get("valor")
        if op not in OPS:
            raise Recusa(f"operador {op!r} não permitido")
        if op == "in":
            onde.append(f"{q} in ({', '.join(_lit(x) for x in v)})")
        elif op == "entre":
            onde.append(f"{q} between {_lit(v[0])} and {_lit(v[1])}")
        else:
            onde.append(f"{q} {op} {_lit(v)}")
    sql = f"select {', '.join(sel)}, count(*) as __n from dados"
    if onde:
        sql += " where " + " and ".join(onde)
    if grp:
        sql += " group by " + ", ".join(grp)
    return sql


def agregar(con, pedido: dict, limite: int = 50) -> dict:
    cols, pessoais = colunas(con), colunas_pessoais(con)
    try:
        sql = montar(pedido, cols, pessoais)
        cur = con.execute(sql)
    except Recusa as e:
        return {"erro": str(e)}
    except Exception as e:  # o erro do DuckDB pode citar um valor do arquivo: devolve só o tipo
        return {"erro": f"consulta inválida ({type(e).__name__})"}
    nomes = [d[0] for d in cur.description]
    linhas = cur.fetchall()
    i_n = nomes.index("__n")
    ok = [r for r in linhas if r[i_n] >= K]
    sup = len(linhas) - len(ok)
    ordem = pedido.get("ordenar")
    if ordem and ordem.lstrip("-") in nomes:
        j = nomes.index(ordem.lstrip("-"))
        ok.sort(key=lambda r: (r[j] is None, r[j]), reverse=ordem.startswith("-"))
    return {"colunas": [n if n != "__n" else "linhas" for n in nomes], "linhas": ok[:limite],
            "grupos_suprimidos_por_terem_menos_de_k": sup, "k": K, "sql": sql}


def perfil_seguro(con, perfil: dict) -> dict:
    """O perfil da P2 sem valores individuais: sem valores frequentes de colunas pessoais ou raros (< K),
    sem exemplos crus nos alertas. O painel local pode mostrar o perfil completo; o Claude recebe este."""
    pessoais = colunas_pessoais(con)
    cols = []
    for c in perfil["colunas"]:
        c = dict(c)
        if "top" in c:
            c["top"] = [] if c["coluna"] in pessoais else [[v, n] for v, n in c["top"] if n >= K]
        if c["coluna"] in pessoais:
            c["dado_pessoal"] = True
            c.pop("min", None); c.pop("max", None)
        cols.append(c)
    alertas = [re.sub(r", ex\.: \[.*\]$", " (exemplos só no painel)", a) for a in perfil["alertas"]]
    return {**perfil, "colunas": cols, "alertas": alertas}
