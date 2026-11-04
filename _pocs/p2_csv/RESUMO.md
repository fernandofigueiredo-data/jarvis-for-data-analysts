# P2 — leitura de CSV brasileiro (2026-11-02)

- DuckDB 2.0 sozinho: detecta `;` e `dd/mm/aaaa`, mas **não detecta codificação** (UTF-8 falha na linha 2 de um cp1252) e **não converte vírgula decimal nem `R$ 1.234,56`** (ficam texto). pandas padrão: `UnicodeDecodeError`.
- `carregar.py`: UTF-8 estrito → cp1252 → detector; transcodifica uma cópia; DuckDB faz o resto; colunas texto com ≥95% no padrão pt-BR viram número. Resultado idêntico ao CSV UTF-8 de referência (min 10,01 · max 9.415,00 · média 1.185,44).
- Detector genérico (`charset-normalizer` 3.5.2) errou: `iso8859_10` no arquivo de vendas e `cp1250` no arquivo com “aspas” e € → "Promoçăo". A regra cp1252-primeiro acertou os dois.
- Perfil apontou no arquivo sujo: 25 duplicatas, 6,04% de UF nula, grafia variante em canal, linha "TOTAL" no id, "n/d" em valor_total, "dez" em nps.
- Desempenho (ler + perfil completo): 1M linhas/61 MB 0,67 s, pico 356 MB; 5M/309 MB 2,46 s, pico 1,39 GB (pandas: 2,83 s, 1,03 GB). Transcodificar 309 MB: 0,37 s.
