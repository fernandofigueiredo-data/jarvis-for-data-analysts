"""Ataques e usos normais contra a ferramenta de agregados."""
import json, sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path += [str(BASE / "p2_csv"), str(BASE / "p7_agregados")]
from carregar import abrir
from agregar import agregar, colunas_pessoais

con, meta = abrir(BASE / "dados" / "clientes_sinteticos.csv")
con.execute("SET enable_external_access=false"); con.execute("SET lock_configuration=true")
print("colunas pessoais detectadas:", sorted(colunas_pessoais(con)))
casos = {
    "uso normal: faturamento por UF": {"metricas": [{"funcao": "soma", "coluna": "valor_total"}, {"funcao": "media", "coluna": "valor_total"}], "por": ["uf"], "ordenar": "-soma_valor_total"},
    "agrupar por cpf (dado pessoal)": {"metricas": [{"funcao": "soma", "coluna": "valor_total"}], "por": ["cpf"]},
    "agrupar por valor_total (quase único por linha)": {"metricas": [{"funcao": "contagem"}], "por": ["valor_total"]},
    "máximo de nome (devolveria um nome)": {"metricas": [{"funcao": "maximo", "coluna": "nome_cliente"}]},
    "string_agg (fora da lista)": {"metricas": [{"funcao": "string_agg", "coluna": "email"}]},
    "contagem de e-mails distintos": {"metricas": [{"funcao": "distintos", "coluna": "email"}]},
    "filtro que isola 1 linha": {"metricas": [{"funcao": "soma", "coluna": "valor_total"}], "filtros": [{"coluna": "email", "op": "=", "valor": "cliente10@exemplo.test"}]},
    "injeção no valor do filtro": {"metricas": [{"funcao": "contagem"}], "filtros": [{"coluna": "uf", "op": "=", "valor": "SP' or 1=1 --"}]},
    "filtro por e-mail (dado pessoal)": {"metricas": [{"funcao": "soma", "coluna": "valor_total"}], "filtros": [{"coluna": "email", "op": "in", "valor": ["cliente1@exemplo.test", "cliente2@exemplo.test"]}]},
    "erro que citaria um valor": {"metricas": [{"funcao": "contagem"}], "filtros": [{"coluna": "valor_total", "op": ">", "valor": "Ana Souza"}]},
}
res = {}
for nome, pedido in casos.items():
    r = agregar(con, pedido)
    res[nome] = r
    resumo = r.get("erro") or f"{len(r['linhas'])} linhas, suprimidos={r['grupos_suprimidos_por_terem_menos_de_k']}: {r['linhas'][:4]}"
    print(f"- {nome}: {resumo}")
json.dump(res, open(BASE / "p7_agregados" / "resultado.json", "w"), ensure_ascii=False, indent=1, default=str)

try:
    con.execute("select count(*) from dados where valor_total > 'Ana Souza'").fetchall()
except Exception as e:
    print("erro cru do DuckDB (o que não pode ir ao modelo):", str(e).splitlines()[0][:120])
from carregar import perfil
from agregar import perfil_seguro
con2, _ = abrir(BASE / "dados" / "clientes_sinteticos.csv")
ps = perfil_seguro(con2, perfil(con2))
print("perfil seguro:", [(c["coluna"], c.get("top"), c.get("dado_pessoal", False)) for c in ps["colunas"]])
con3, _ = abrir(BASE / "dados" / "vendas_suja.csv")
print("alertas seguros (arquivo sujo):", perfil_seguro(con3, perfil(con3))["alertas"])
