"""Revalida as respostas salvas em resultado.json com o validador corrigido, sem chamar o modelo de novo.
Reexecuta localmente os mesmos SQL (determinísticos) e acumula os resultados da sessão."""
import json, sys
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
sys.path += [str(BASE / "p2_csv"), str(BASE / "p3_numeros")]
from carregar import abrir, perfil
from validar import validar
con, meta = abrir(BASE / "dados" / "vendas_excel_br.csv")
sessao = [json.dumps({"leitura": meta, "perfil": perfil(con)}, ensure_ascii=False, default=str)]  # perfil_arquivo foi chamado no 1º turno
for t in json.load(open(BASE / "p3_numeros" / "resultado.json")):
    for q in t["sql"]:
        if not q.get("recusado") and "erro" not in q:
            cur = con.execute(q["sql"]); sessao.append(json.dumps({"linhas": cur.fetchmany(50)}, default=str))
    v = validar(t["resposta"], sessao, t["pergunta"])
    print(f"{t['pergunta'][:45]:45s} antes={t['validacao']['sem_origem']} depois={v['sem_origem']} ({len(v['numeros'])} números)")
