"""(a) DuckDB travado: depois de carregar o CSV numa tabela, o SQL gerado pelo modelo não alcança arquivo nem rede."""
import json, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "p2_csv"))
from carregar import abrir

BASE = Path(__file__).resolve().parent
con, _ = abrir(BASE.parent / "dados" / "vendas_excel_br.csv")
con.execute("SET memory_limit='512MB'")
con.execute("SET enable_external_access=false")
con.execute("SET lock_configuration=true")

canario = BASE / "fora" / "canario.txt"
ataques = {
    "consulta_normal": "select uf, round(sum(valor_total), 2) from dados group by 1 order by 2 desc limit 3",
    "ler_outro_arquivo": f"select * from read_csv('{canario}')",
    "ler_texto": f"select content from read_text('{canario}')",
    "escrever_arquivo": f"copy dados to '{BASE / 'fora' / 'vazou.csv'}'",
    "anexar_banco": f"attach '{BASE / 'fora' / 'x.db'}'",
    "instalar_extensao": "install httpfs",
    "rede": "select * from read_csv('https://example.com/a.csv')",
    "destravar": "set enable_external_access=true",
    "shell": "select * from read_csv('/dev/stdin')",
}
res = {}
for nome, sql in ataques.items():
    try:
        out = con.execute(sql).fetchall()
        res[nome] = {"bloqueado": False, "saida": str(out)[:120]}
    except Exception as e:
        res[nome] = {"bloqueado": True, "erro": str(e).splitlines()[0][:140]}

# tempo limite: consulta explosiva (produto cartesiano) interrompida por outra thread
t = threading.Timer(2.0, con.interrupt); t.start(); t0 = time.perf_counter()
try:
    con.execute("select count(*) from dados a, dados b, dados c").fetchall(); res["tempo_limite"] = {"bloqueado": False}
except Exception as e:
    res["tempo_limite"] = {"bloqueado": True, "erro": str(e).splitlines()[0][:80], "segundos": round(time.perf_counter() - t0, 2)}
t.cancel()
res["vazou_arquivo"] = (BASE / "fora" / "vazou.csv").exists()
print(json.dumps(res, ensure_ascii=False, indent=1))
