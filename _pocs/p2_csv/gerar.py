"""Gera CSVs sintéticos de vendas em vários formatos (nenhum dado real)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "dados"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(42)
UFS = ["SP", "RJ", "MG", "RS", "PR", "BA", "PE", "CE", "SC", "GO"]
CANAIS = ["Loja física", "E-commerce", "Televendas"]
PRODUTOS = ["Açaí", "Pão de queijo", "Café especial", "Guaraná", "Feijão", "Maçã"]


def base(n: int) -> pd.DataFrame:
    datas = pd.Timestamp("2025-01-01") + pd.to_timedelta(rng.integers(0, 365, n), unit="D")
    qtd = rng.integers(1, 20, n)
    preco = rng.gamma(3, 40, n).round(2)
    return pd.DataFrame({
        "id_venda": np.arange(1, n + 1),
        "data_venda": datas,
        "uf": rng.choice(UFS, n, p=[.3, .15, .12, .08, .08, .07, .06, .05, .05, .04]),
        "canal": rng.choice(CANAIS, n),
        "produto": rng.choice(PRODUTOS, n),
        "quantidade": qtd,
        "valor_unitario": preco,
        "valor_total": (qtd * preco).round(2),
        "nps": rng.integers(0, 11, n),
    })


def br_money(x: float) -> str:
    s = f"{x:,.2f}"  # 1,234.56
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    small = base(5000)
    # 1) padrão internacional: UTF-8, vírgula, ponto decimal, data ISO
    small.to_csv(OUT / "vendas_utf8.csv", index=False)
    # 2) padrão Excel brasileiro: cp1252, ';', vírgula decimal, R$ com milhar, data dd/mm/aaaa
    br = small.copy()
    br["data_venda"] = br["data_venda"].dt.strftime("%d/%m/%Y")
    br["valor_unitario"] = br["valor_unitario"].map(lambda v: f"{v:.2f}".replace(".", ","))
    br["valor_total"] = br["valor_total"].map(br_money)
    br.to_csv(OUT / "vendas_excel_br.csv", index=False, sep=";", encoding="cp1252")
    # 3) sujo: nulos, duplicatas, tipos mistos, espaços, linha de total no fim
    suja = small.head(1000).copy().astype({"valor_total": object, "nps": object})
    suja.loc[rng.choice(1000, 60, replace=False), "uf"] = None
    suja.loc[rng.choice(1000, 15, replace=False), "valor_total"] = "n/d"
    suja.loc[rng.choice(1000, 10, replace=False), "nps"] = "dez"
    suja["canal"] = suja["canal"].where(rng.random(1000) > .1, " e-commerce ")
    suja = pd.concat([suja, suja.sample(25, random_state=1)])
    suja.loc[len(suja)] = ["TOTAL", None, None, None, None, None, None, "999999", None]
    suja.to_csv(OUT / "vendas_suja.csv", index=False, sep=";", encoding="latin-1")
    # 4) grandes, para tempo e memória
    for n in [int(a) for a in sys.argv[1:]] or [1_000_000]:
        base(n).to_csv(OUT / f"vendas_{n // 1_000_000}M.csv", index=False)
    for f in sorted(OUT.glob("*.csv")):
        print(f"{f.name:25s} {f.stat().st_size / 1e6:8.1f} MB")


if __name__ == "__main__":
    main()
