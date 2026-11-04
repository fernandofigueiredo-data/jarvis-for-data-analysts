# P4 — isolamento (2026-11-02, Mac M2, macOS 27.2)

| Ataque | Sem isolamento (= kernel Jupyter) | DuckDB travado (só SQL) | Seatbelt `deny default` | Docker (Colima) `--network none --read-only --memory 512m` |
|---|---|---|---|---|
| Ler o arquivo de dados permitido | lê | lê (tabela já carregada) | lê | lê (montado `:ro`) |
| Ler arquivo-canário fora da pasta | **lê** | bloqueado | bloqueado | bloqueado (não montado) |
| Listar a pasta pessoal | **lê (75 itens)** | n/a (só SQL) | bloqueado | só vê o home do contêiner |
| Escrever fora | **escreve** | bloqueado (`COPY`, `ATTACH`) | bloqueado | bloqueado (FS só leitura) |
| Rede (DNS/TCP) | **conecta** | bloqueado (`https://`, `INSTALL`) | bloqueado | bloqueado |
| Subprocesso/shell | **roda** | n/a | bloqueado (exec negado) | roda, mas dentro do contêiner |
| Destravar configuração | — | bloqueado (`lock_configuration`) | — | — |
| Laço infinito | sem limite | interrompido em 2,0 s (`interrupt`) | morto em 3 s (`RLIMIT_CPU`) | morto em 3 s (`timeout`) |
| Bomba de memória (2 GB) | sem limite | `memory_limit=512MB` | **não contida**: alocou 2 GB; `RLIMIT_AS` recusado pelo macOS | morta (código 137, OOM) |
| Sobrecarga por execução | 0 | 0 | ~0,03 s | ~0,3 s com a VM ligada (+VM de ~2 GB RAM) |

Arquivos: `duckdb_travado.py`/`resultado_duckdb.json`, `ataque.py`, `perfil.sb`, `resultado_*.json`, `resultado_docker.txt`.
