# _pocs — provas de conceito descartáveis

Criadas para [`docs/PLANO_ANALISE_DADOS.md`](../docs/PLANO_ANALISE_DADOS.md). Só dados sintéticos. Ambiente isolado (`_pocs/.venv`, modelos em `_pocs/.cache`).
Nada aqui é importado pelo Jarvis; pode apagar a pasta inteira.

Rodar: `cd _pocs && uv run python <poc>/<script>.py`

Limpeza em 02/11/2026: apagados os ambientes (`.venv`, cache do Whisper turbo), o projeto do plugin da P5, os CSVs de 1M/5M linhas
e os áudios da P6 (~3 GB). Para refazer: `uv sync` aqui, `uv run python p2_csv/gerar.py 1000000 5000000` e o trecho de `say` da P6.
