#!/bin/bash
# Painel de demonstração: o Jarvis de verdade com o Claude, a voz, o clima, as notícias e a agenda simulados
# (o daemon dos testes de ponta a ponta). Não precisa de login no Claude, microfone nem permissões.
# Uso: scripts/demo.sh [porta]   (padrão: 8799). Ctrl+C encerra; nada fora da pasta temporária é tocado.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORTA="${1:-8799}"
PASTA="$(mktemp -d -t jarvis-demo)"
trap 'rm -rf "$PASTA"' EXIT
cd "$REPO"

[ -d ui/dist ] || { echo "Compilando o painel..."; (cd ui && npm ci --silent && npm run build --silent); }
uv sync --quiet

cat <<EOF
Painel: http://127.0.0.1:$PORTA
Experimente no campo "Pesquisar ou comandar":
  abra o arquivo vendas_teste
  qual o faturamento por mês?
  qual uf mais fatura?
  me mostra a distribuição em gráfico
EOF
( for _ in $(seq 1 60); do curl -s -o /dev/null "http://127.0.0.1:$PORTA" && exec open "http://127.0.0.1:$PORTA"; sleep 1; done ) &
uv run python tests/e2e/daemon_teste.py --dir "$PASTA" --port "$PORTA"
