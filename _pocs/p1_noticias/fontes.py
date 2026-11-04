"""Testa fontes reais de notícias de dados: disponibilidade, volume e frescor. Só lê feeds públicos."""
import calendar, json, time
from datetime import datetime, timezone
from urllib.parse import quote

import feedparser, httpx

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
GNEWS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
FONTES = {
    "KDnuggets": "https://www.kdnuggets.com/feed",
    "Towards Data Science": "https://towardsdatascience.com/feed",
    "Databricks Blog": "https://www.databricks.com/feed",
    "DuckDB Blog": "https://duckdb.org/feed.xml",
    "dbt Labs Blog": "https://www.getdbt.com/blog/rss.xml",
    "benn.substack": "https://benn.substack.com/feed",
    "Data Hackers (feed?)": "https://www.datahackers.news/feed",
    "Google News pt-BR": GNEWS.format(q=quote('"ciência de dados" OR "análise de dados" OR "engenharia de dados"')),
}
HN = "https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&numericFilters=created_at_i>{t},points>20&hitsPerPage=20"

agora = time.time()
res = {}
with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=20) as c:
    for nome, url in FONTES.items():
        t0 = time.perf_counter()
        try:
            r = c.get(url); r.raise_for_status()
            f = feedparser.parse(r.content)
            datas = [calendar.timegm(e.published_parsed) for e in f.entries if getattr(e, "published_parsed", None)]
            resumo_len = [len((e.get("summary") or "")) for e in f.entries]
            conteudo_completo = sum(1 for e in f.entries if e.get("content") and len(e.content[0].value) > 3000)
            res[nome] = {"ok": bool(f.entries), "itens": len(f.entries),
                         "mais_recente_h": round((agora - max(datas)) / 3600, 1) if datas else None,
                         "itens_ultimas_24h": sum(1 for d in datas if agora - d < 86400),
                         "resumo_medio_chars": round(sum(resumo_len) / len(resumo_len)) if resumo_len else 0,
                         "itens_com_texto_integral": conteudo_completo, "ms": round((time.perf_counter() - t0) * 1000),
                         "exemplo": f.entries[0].title[:90] if f.entries else None}
        except Exception as e:
            res[nome] = {"ok": False, "erro": f"{type(e).__name__}: {str(e)[:100]}"}
    t0 = time.perf_counter()
    try:
        q = quote('"data engineering" OR duckdb OR "data analysis" OR pandas OR dbt')
        hits = c.get(HN.format(q="data", t=int(agora - 86400 * 2))).json()["hits"]
        res["Hacker News (Algolia, 48h, >20 pontos, 'data')"] = {"ok": True, "itens": len(hits),
            "ms": round((time.perf_counter() - t0) * 1000), "exemplo": hits[0]["title"][:90] if hits else None}
    except Exception as e:
        res["Hacker News"] = {"ok": False, "erro": str(e)[:100]}
json.dump(res, open("p1_noticias/fontes_resultado.json", "w"), ensure_ascii=False, indent=1)
for k, v in res.items():
    print(f"{k:45s}", {kk: vv for kk, vv in v.items() if kk != "exemplo"}, "|", v.get("exemplo"))
