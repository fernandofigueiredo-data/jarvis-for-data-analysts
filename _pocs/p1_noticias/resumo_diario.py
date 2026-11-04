"""Monta o resumo diário: coleta, deduplica, ranqueia por perfil e confere que o resumo não copia o texto.

Saída: lista de {titulo, link, fonte, data, motivo}. O texto do artigo nunca é guardado nem repetido;
o resumo (feito pelo modelo a partir de título + descrição do feed) passa pelo verificador `copia_longa`.
"""
import calendar, json, re, sys, time, unicodedata
from pathlib import Path
import feedparser, httpx

sys.path.insert(0, str(Path(__file__).parent))
from fontes import FONTES, UA  # noqa: E402  (reusa a lista testada)

PERFIL = {  # pesos editáveis pelo usuário; nada aprendido automaticamente nesta PoC
    "duckdb": 3, "dbt": 3, "pandas": 3, "sql": 2, "power bi": 3, "databricks": 2, "análise de dados": 3,
    "analytics": 2, "dashboard": 2, "llm": 1, "agent": 1, "engenharia de dados": 3, "data engineer": 2, "lakehouse": 1,
}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^a-z0-9 ]", "", "".join(c for c in t if not unicodedata.combining(c)))


def coletar() -> list[dict]:
    itens = []
    with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20) as c:
        for nome, url in FONTES.items():
            try:
                f = feedparser.parse(c.get(url).content)
            except Exception:
                continue
            for e in f.entries:
                ts = calendar.timegm(e.published_parsed) if getattr(e, "published_parsed", None) else None
                desc = re.sub(r"<[^>]+>", " ", e.get("summary") or "")
                itens.append({"titulo": e.title.strip(), "link": e.link, "fonte": nome, "ts": ts, "descricao": desc[:400]})
    return itens


def deduplicar(itens):
    vistos, out = set(), []
    for i in sorted(itens, key=lambda x: -(x["ts"] or 0)):
        chave = " ".join(norm(i["titulo"]).split()[:8])  # mesmo assunto republicado por agregadores
        url = i["link"].split("?")[0].rstrip("/")
        if chave in vistos or url in vistos:
            continue
        vistos |= {chave, url}
        out.append(i)
    return out


def pontuar(i, agora):
    texto = norm(i["titulo"] + " " + i["descricao"])
    hits = [k for k in PERFIL if norm(k) in texto]
    frescor = 1.0 if i["ts"] and agora - i["ts"] < 86400 else .5 if i["ts"] and agora - i["ts"] < 3 * 86400 else .1
    return sum(PERFIL[k] for k in hits) * frescor, hits


def copia_longa(resumo: str, original: str, n: int = 8) -> list[str]:
    """Sequências de n+ palavras do resumo que aparecem iguais no original (indício de reprodução)."""
    a, b = norm(resumo).split(), " ".join(norm(original).split())
    return [" ".join(a[i:i + n]) for i in range(len(a) - n + 1) if " ".join(a[i:i + n]) in b]


if __name__ == "__main__":
    agora = time.time()
    brutos = coletar()
    unicos = deduplicar(brutos)
    ranq = sorted(((pontuar(i, agora), i) for i in unicos), key=lambda x: -x[0][0])
    top = [{"titulo": i["titulo"], "link": i["link"], "fonte": i["fonte"],
            "data": time.strftime("%Y-%m-%d", time.gmtime(i["ts"])) if i["ts"] else None,
            "pontos": round(p, 1), "motivo": hits, "descricao_feed": i["descricao"][:200]} for (p, hits), i in ranq[:8] if p > 0]
    json.dump({"coletados": len(brutos), "apos_dedup": len(unicos), "top": top}, open(Path(__file__).parent / "digest.json", "w"),
              ensure_ascii=False, indent=1)
    print(f"coletados={len(brutos)} após deduplicar={len(unicos)} com pontuação>0={sum(1 for (p,_),_ in ranq if p>0)}")
    for t in top:
        print(f" {t['pontos']:5} {t['fonte'][:18]:18s} {t['titulo'][:80]}  {t['motivo']}")
    # teste do verificador de cópia
    orig = "DuckDB 2.0 brings a new storage format that makes analytical queries over large Parquet files much faster than before"
    print("verificador, resumo próprio:", copia_longa("Nova versão do DuckDB acelera consultas analíticas em arquivos Parquet grandes.", orig))
    print("verificador, resumo copiado:", copia_longa("DuckDB 2.0 brings a new storage format that makes analytical queries faster", orig))
