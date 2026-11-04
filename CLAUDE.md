# Jarvis para analistas de dados

Assistente de voz para o macOS, em português. Ele responde perguntas sobre CSV mandando para o Claude só agregados, nunca as linhas. O Claude roda pelo login do Claude Code de quem usa (`claude-agent-sdk`), sem chave de API.

## Se a pessoa acabou de clonar
- Ofereça o `/instalar`, que faz a instalação guiada até o ícone no Dock.
- Se algo parar de funcionar, use o `/diagnostico`.
- Para só olhar o painel, sem login nem microfone, use `scripts/demo.sh`.

## Mapa
- `src/jarvis/app.py`: orquestrador (voz, turnos, timers, eventos do painel)
- `src/jarvis/config.py`: todas as variáveis `JARVIS_*`, documentadas em `.env.example`
- `src/jarvis/brain/`: sessão do Claude (`agent.py`), prompt (`persona.py`), quem libera cada ferramenta (`gate.py`) e ferramentas in-process (`tools.py`)
- `src/jarvis/dados.py`: leitura de CSV, agregados com anonimato k e conferência dos números
- `src/jarvis/executor.py`: Python isolado no Seatbelt
- `src/jarvis/mac/`: AppleScript, Option direito e timers
- `ui/`: painel em React + Three.js, servido já compilado de `ui/dist`
- `tests/`: unitários. `tests/e2e/` tem os testes de ponta a ponta com o Claude simulado (`daemon_teste.py`, `cerebro_falso.py`).

## Comandos
```bash
uv sync
cd ui && npm ci && npm run build && cd ..
uv run ruff check src tests
uv run pytest -q --ignore=tests/e2e
uv run --with playwright pytest tests/e2e
uv run jarvis --text "pergunta"
```

O primeiro `pytest` são os testes unitários, em segundos. O de `tests/e2e` é o de ponta a ponta, que leva uns 4 minutos e precisa do `playwright install chromium webkit` uma vez. O `jarvis --text` roda um turno sem microfone nem painel.

## Regras
- **Nunca leia arquivos de dados da pessoa** (CSV, TSV, XLSX, Parquet) nem `data/jarvis.db`. É a promessa central do projeto. Para testar, use `exemplos/vendas_exemplo.csv` ou o daemon de teste.
- Não rode `uv run jarvis` sem argumentos no terminal da sessão: ele não termina sozinho. Use `--text` ou `scripts/demo.sh` em segundo plano.
- As falas fixas são escritas com "senhor" e passam por `fillers.trat()`, que aplica o `JARVIS_TRATAMENTO`. Os testes de ponta a ponta fixam "senhor".
- Mudou ferramenta, gate ou dados: rode os testes unitários. Mudou o painel: rode também o `tests/e2e`.
