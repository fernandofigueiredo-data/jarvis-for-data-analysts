"""Tempo e pico de memória (RSS) para ler + perfilar arquivos grandes. Uma medição por processo."""
import json, resource, sys, time
sys.path.insert(0, __import__("os").path.dirname(__file__))
modo, arq = sys.argv[1], sys.argv[2]
t = time.perf_counter()
if modo == "duckdb":
    from carregar import abrir, perfil
    con, meta = abrir(arq); t1 = time.perf_counter(); p = perfil(con); linhas = p["linhas"]
else:
    import pandas as pd
    df = pd.read_csv(arq); t1 = time.perf_counter(); d = df.describe(include="all"); linhas = len(df)
print(json.dumps({"modo": modo, "arquivo": arq.split("/")[-1], "linhas": linhas, "leitura_s": round(t1 - t, 2),
                  "total_s": round(time.perf_counter() - t, 2), "pico_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6)}))
