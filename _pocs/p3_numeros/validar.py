"""Extrai números de um texto em pt-BR e confere se cada um saiu de um resultado de ferramenta.

Os resultados de ferramenta são JSON (ponto decimal); a resposta é pt-BR (1.234,56; 12,5%; 1,99 milhão).
Um número da resposta só passa se for igual a um número de origem, admitido o arredondamento que a
própria escrita indica ("1,99 milhão" tem 3 algarismos significativos, então vale ±5 mil).
"""
import math
import re

NUM_BR = re.compile(r"(?<![\w.,])(-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?)\s*(%|mil\b|milh(?:ão|ao|ões|oes)\b|bilh(?:ão|ao|ões|oes)\b|bi\b|mi\b)?", re.I)
NUM_JSON = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
DATA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
MULT = {"mil": 1e3, "mi": 1e6, "bi": 1e9}


def numeros_br(texto: str) -> list[tuple[str, float, int]]:
    out = []
    for m in NUM_BR.finditer(texto):
        bruto, suf = m.group(1), (m.group(2) or "").lower()
        v = float(bruto.replace(".", "").replace(",", "."))
        chave = "mi" if suf.startswith("milh") else "bi" if suf.startswith("bilh") else suf
        v *= MULT.get(chave, 1)
        digitos = re.sub(r"\D", "", bruto).lstrip("0") or "0"
        sig = len(digitos) if "," in bruto else max(len(digitos.rstrip("0")), 1)
        out.append((m.group(0).strip(), v, sig))
    return out


def numeros_fonte(texto: str) -> list[float]:
    # datas ISO viram ano, mês e dia (a resposta diz "31/12/2025"); o sinal não importa ("1,55% abaixo")
    texto = DATA_ISO.sub(lambda m: f"{m[1]} {m[2]} {m[3]}", texto)
    return [abs(float(x)) for x in NUM_JSON.findall(texto)]


def casa(v: float, sig: int, fonte: list[float]) -> bool:
    if v == 0:
        return 0 in fonte
    meia = 0.5 * 10 ** (math.floor(math.log10(abs(v))) - sig + 1) + 1e-9
    return any(abs(v - f) <= meia or abs(v - f * 100) <= meia for f in fonte)


def validar(resposta: str, resultados: list[str], pergunta: str) -> dict:
    """`resultados`: tudo que as ferramentas devolveram NA SESSÃO (a resposta pode citar um turno anterior)."""
    fonte = [f for r in resultados for f in numeros_fonte(r)] + [v for _, v, _ in numeros_br(pergunta)]
    achados = numeros_br(resposta)
    sem = [t for t, v, sig in achados if not casa(abs(v), sig, fonte)]
    return {"numeros": [t for t, _, _ in achados], "sem_origem": sem, "ok": not sem}


if __name__ == "__main__":
    res = ['[["SP", 1765072.7], ["RJ", 872492.67]]', '{"crescimento": 1985706.79}']
    casos = [("SP lidera com R$ 1.765.072,70, o dobro do RJ (872.492,67).", "qual uf fatura mais?", True),
             ("Com 12,5% a mais, SP iria a R$ 1.985.706,79.", "e se crescer 12,5%?", True),
             ("SP iria a uns R$ 1,99 milhão.", "e se crescer 12,5%?", True),
             ("SP iria a R$ 1.990.000.", "e se crescer 12,5%?", True),
             ("SP iria a R$ 1.975.000.", "e se crescer 12,5%?", False),
             ("SP fatura 2,1 milhões.", "qual uf fatura mais?", False)]
    for txt, perg, esperado in casos:
        r = validar(txt, res, perg)
        print("OK " if r["ok"] == esperado else "ERRO", r)
