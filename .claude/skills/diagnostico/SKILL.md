---
name: diagnostico
description: Descobre por que o Jarvis não abre, não ouve, não fala ou não responde, com conferências só de leitura, e diz a correção. Use quando a pessoa disser que o Jarvis parou, travou, não responde, não escuta o "Ei Jarvis", não reage ao Option direito, está mudo ou dá erro ao abrir.
---

# Diagnóstico do Jarvis

Só leitura: não altere arquivos, não reinstale e não encerre processos sem a pessoa pedir. Rode as conferências, mostre uma tabela com ✅ e ❌ e, para cada ❌, a correção da tabela de sintomas. Nunca leia arquivos de dados da pessoa.

## Conferências

1. **Pasta certa:** `pyproject.toml` e `ui/` existem na pasta atual. Os erros `No pyproject.toml found` e `Failed to spawn: jarvis` querem dizer que o comando rodou fora do repositório.
2. **Jarvis já aberto:** `lsof -nP -iTCP:${JARVIS_PORT:-8787} -sTCP:LISTEN` (leia `JARVIS_PORT` do `.env`, se houver).
3. **`.env`:** o arquivo existe. `JARVIS_TRATAMENTO` é senhor, senhora ou nenhum. Nenhuma linha `CHAVE=` está vazia sem `# ` na frente quando o padrão importa (`JARVIS_DATA_DIR=` vazio faz o banco ir para a pasta atual).
4. **Painel compilado:** `ui/dist/index.html` existe.
5. **Dependências:** `uv sync --locked` termina sem erro.
6. **Login do Claude:** `uv run jarvis --text "diga apenas ok"` devolve uma frase. Avise que isso usa um turno da assinatura.
7. **Voz:** `say -v '?' | grep -i "${JARVIS_VOICE:-Luciana}"`.
8. **Localização:** se `JARVIS_LOCATION` está vazia e `JARVIS_LOCAL_PRECISO` não é `0`, `uv run python -c "from jarvis.mac import location; print(location.current() is not None)"` devolve `True`. Não mostre coordenadas.
9. **Ícone do Dock:** se `~/Applications/Jarvis.app` existe, `osadecompile ~/Applications/Jarvis.app/Contents/Resources/Scripts/main.scpt | grep "cd "` aponta para esta pasta.

As permissões do macOS não podem ser lidas daqui. Pergunte o que a pessoa vê e use a tabela.

## Sintomas e correções

| Sintoma | Causa provável | Correção |
|---|---|---|
| "No pyproject.toml found" ou "Failed to spawn: jarvis" | comando rodado fora da pasta do repositório | `cd` para a pasta do repositório |
| Clicar no ícone só avisa "O Jarvis já está aberto" | outro Jarvis ocupa a porta | fechar a janela do Terminal onde ele roda, ou Ctrl+C nela |
| O ícone não faz nada ou abre a pasta errada | a pasta do repositório mudou de lugar | `scripts/criar_app.sh` de novo |
| Responde no texto, mas nada é falado | voz não instalada ou som baixo | instalar a Luciana (veja o `/instalar`, passo 1) ou trocar `JARVIS_VOICE` |
| "Infelizmente o cérebro não respondeu" e um aviso no feed | login expirado, limite de uso ou modelo inválido; o texto do aviso diz qual | `claude` num terminal e `/login`; esperar o limite; conferir `JARVIS_MODEL` |
| Não reage ao "Ei Jarvis" | Microfone negado ao Terminal ou modo errado | Ajustes › Privacidade e Segurança › Microfone › Terminal; abrir sem `--mode off` |
| Segurar o Option direito não faz nada | Monitoramento de Entrada negado ao Terminal | liberar em Ajustes › Privacidade e Segurança › Monitoramento de Entrada e reabrir o Terminal |
| "Abre o Chrome" responde, mas o app não abre | Automação negada | Ajustes › Privacidade e Segurança › Automação › Terminal |
| Primeira abertura demora minutos | o Whisper está baixando o modelo (~460 MB no `small`) | esperar; só acontece uma vez |
| A agenda demora ou fica "sendo lida" | o Calendário do macOS leva até ~50 s em agendas grandes | esperar; a leitura roda em segundo plano |
| Diz que não encontrou o arquivo | o CSV está fora das pastas de `JARVIS_PASTAS_DADOS` (até três níveis abaixo) | mover o arquivo, arrastar para o painel ou acrescentar a pasta no `.env` |
| O Local mostra outra cidade com "(aprox.)" | a localização do Mac está negada ou o app auxiliar não compilou; ficou a cidade do IP | Ajustes › Privacidade e Segurança › Serviços de Localização › Jarvis Localização; sem `swiftc`, `xcode-select --install`; ou pôr a cidade em `JARVIS_LOCATION` |
| Fala com a voz do macOS e o feed diz "ElevenLabs recusou a fala" | o texto do aviso diz o motivo: `402 paid_plan_required` é voz da Voice Library no plano gratuito; `401` é chave inválida | trocar `JARVIS_ELEVEN_VOICE_ID` por uma voz padrão (ou assinar um plano); refazer a chave |
| A análise profunda não abre | plugin `analise-dados` não instalado | `/instalar`, passo 6 |

Termine com a causa mais provável em uma frase e o próximo passo.
