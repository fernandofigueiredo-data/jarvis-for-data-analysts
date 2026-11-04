"""Classifica o comando transcrito: consulta (roda direto) × alteração (exige confirmação, só em cópia).

Regra conservadora: na dúvida, é alteração. A confirmação repete o que foi ENTENDIDO, não o que foi dito,
porque a transcrição pode errar (P6: "Apaga as linhas com UF nula" virou "Apaga as linhas com o F0").
"""
import json, re, unicodedata
from pathlib import Path

ALTERA = re.compile(r"\b(apag|remov|exclu|clui|delet|subst|sobrescrev|salv\w* por cima|alter|renomei|limp|descart|corrig|preench|"
                    r"drop|truncat|update|insert|mescl|sobrepo|zera)", re.I)


def norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def classificar(texto: str) -> str:
    return "alteracao" if ALTERA.search(norm(texto)) else "consulta"


if __name__ == "__main__":
    base = Path(__file__).parent
    frases = json.load(open(base / "frases.json"))
    r = json.load(open(base / "resultado_small.json"))
    # reconstroi o que foi ouvido: erros guardados; o resto foi transcrito com todos os termos
    ouvidos = {(e["voz"], e["esperado"]): e["ouvido"] for e in r["configs"]["atual_jarvis"]["erros"]}
    fn = fp = 0
    for voz in ("luciana", "eddy"):
        for f in frases:
            txt = ouvidos.get((voz, f["texto"]), f["texto"])
            c = classificar(txt)
            if f["destrutivo"] and c != "alteracao":
                fn += 1; print("NÃO PEGOU:", voz, txt)
            if not f["destrutivo"] and c == "alteracao":
                fp += 1; print("falso alarme:", voz, txt)
    print(f"comandos destrutivos não detectados: {fn} de 8 · consultas tratadas como alteração: {fp} de 24")
