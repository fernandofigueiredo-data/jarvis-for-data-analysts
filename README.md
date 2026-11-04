# J.A.R.V.I.S. para analistas de dados

[![testes](https://github.com/fernandofigueiredo-data/jarvis-for-data-analysts/actions/workflows/testes.yml/badge.svg)](https://github.com/fernandofigueiredo-data/jarvis-for-data-analysts/actions/workflows/testes.yml) ![macOS](https://img.shields.io/badge/macOS-only-lightgrey) [![licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue)](LICENSE)

Assistente de voz para o Mac, em português, que responde perguntas sobre planilhas CSV **sem mandar as linhas do arquivo para a IA**. Você pergunta "Ei Jarvis, qual UF mais fatura no arquivo de outubro?". O Claude escolhe a métrica e o agrupamento, o DuckDB faz a conta no seu Mac e o Jarvis confere cada número da resposta antes de falar.

![Painel do Jarvis com um CSV aberto: alertas de qualidade, série por mês e a conversa](docs/img/painel.png)

<sub>Painel rodando com o daemon de teste e dados fictícios: arquivo aberto, alertas de qualidade (linha duplicada, UF nula), faturamento por mês e a conversa.</sub>

## Instalar

Você precisa de um Mac e do [Claude Code](https://claude.com/claude-code) instalado e logado. O Jarvis usa o seu login do Claude Code, sem chave de API.

```bash
git clone https://github.com/fernandofigueiredo-data/jarvis-for-data-analysts.git
cd jarvis-for-data-analysts
claude
```

Dentro do Claude Code, digite **`/instalar`**. O Claude conduz a instalação:
1. confere os pré-requisitos (uv, Node 20+, a voz em português);
2. pergunta seu nome, como quer ser tratado, a cidade e os temas de notícias, e grava o `.env`;
3. compila o painel, roda os testes e testa o login do Claude;
4. cria o ícone **Jarvis** para o Dock e explica as permissões do macOS.

Se algo parar de funcionar depois, digite **`/diagnostico`**.

**Ver sem instalar nada além do uv e do Node:** `scripts/demo.sh` abre o painel com o Claude, a voz e os dados simulados. Não precisa de login nem de microfone.

## O problema

Pedir a um assistente de IA que analise um CSV tem três riscos para quem trabalha com dados de empresa:

1. **Vazamento.** O arquivo inteiro, com CPF, nome e e-mail, vai para um serviço externo.
2. **Conta inventada.** O modelo pode errar uma soma ou "fazer de cabeça" um número que nenhuma consulta produziu.
3. **Arquivo do Excel brasileiro.** Um CSV em cp1252, com `;`, `R$ 1.234,56` e datas dd/mm/aaaa, quebra as ferramentas padrão. Nos testes, o DuckDB e o pandas falharam na leitura, e o detector de codificação `charset-normalizer` trocou "Promoção" por "Promoçăo".

O Jarvis trata cada risco com uma trava no código, não com uma instrução no prompt.

## Decisões de projeto

| Risco | Decisão | Alternativa descartada e por quê |
|---|---|---|
| Vazamento | O Claude não escreve SQL. Ele pede `{métricas, agrupar por, filtros}`, e a ferramenta monta a consulta a partir de uma lista fechada de funções. Grupos com menos de 5 linhas são omitidos (anonimato k). Colunas com dado pessoal só aceitam contagem. | **SQL livre:** devolvia até 50 linhas cruas. **Regra no prompt:** o modelo pode errar ou ser induzido pelo conteúdo de uma célula. |
| Conta inventada | Todo número sai do DuckDB ou de uma calculadora. Um validador extrai os números da resposta em formato brasileiro e troca por um aviso qualquer frase cujo número não apareça num resultado de ferramenta. | Confiar no modelo. |
| Execução de código | SQL roda no DuckDB travado (`enable_external_access=false`, `lock_configuration=true`). Python roda no sandbox Seatbelt do macOS, sem rede e com limites de CPU, tempo e memória. | **Docker:** isola também a memória, mas exige uma VM de cerca de 2 GB e soma 0,3 s por execução. |
| Leitura do arquivo | UTF-8 estrito, depois cp1252, e só então o detector genérico. Colunas de texto com 95% ou mais dos valores no padrão pt-BR viram número ou data. | **Detector genérico primeiro:** errou a codificação em dois dos arquivos de teste. |

## Resultados medidos

Os números vêm das provas de conceito em [`_pocs/`](_pocs/) e dos relatórios em [`docs/`](docs/). Todos foram medidos num MacBook Air M2.

- **Números rastreáveis:** em 5 perguntas reais ao Claude, os 32 números das respostas tiveram origem num resultado de ferramenta. Na primeira rodada, o validador deu 4 falsos positivos, que depois foram corrigidos. Quando foi convidado a "fazer de cabeça", o Claude recusou e calculou no SQL.
- **Bloqueios testados** (CSV sintético com CPF, nome e e-mail falsos):
  - Agrupar ou filtrar por coluna pessoal é recusado.
  - Agrupar por `valor_total` devolve 0 grupos e suprime 2.981.
  - A injeção `SP' or 1=1 --` num filtro vira texto literal.
  - Uma mensagem de erro que repetiria o conteúdo de uma célula é cortada.
- **Isolamento:** o mesmo script hostil foi rodado em quatro ambientes. Ele tentava ler e escrever fora da pasta, usar a rede, abrir um shell, rodar um laço infinito e alocar 2 GB. Sem isolamento, tudo passou. No DuckDB travado e no Seatbelt, a leitura, a escrita e a rede foram bloqueadas ([resumo](_pocs/p4_isolamento/RESUMO.md)).
- **Tamanho:** ler e perfilar 1 milhão de linhas (61 MB) leva 0,67 s. Com 5 milhões de linhas (309 MB), leva 2,46 s, com pico de 1,39 GB de memória.
- **Testes:** 126 testes unitários, rodados no CI a cada push, e uma suíte de ponta a ponta no Playwright, com Chromium e WebKit, cobrindo 76 itens do painel. Antes das correções, 36 dos 73 itens medidos falhavam ([relatório](docs/RELATORIO_TESTES.md)).

**Limites conhecidos:**
- O validador pega número inventado, mas não um número verdadeiro atribuído à coisa errada.
- Com só agregados, o Claude não faz junções nem funções de janela.
- O Jarvis só roda no macOS, porque usa AppleScript, Seatbelt e CGEventTap.

## Instalação manual

Sem o Claude Code conduzindo, os mesmos passos do `/instalar`:

```bash
cp .env.example .env            # ajuste nome, tratamento e cidade
uv sync
cd ui && npm ci && npm run build && cd ..
uv run jarvis                   # ou scripts/criar_app.sh para o ícone no Dock
```

Na primeira vez:
1. O Whisper baixa o modelo `small`, uns 460 MB.
2. O macOS pede **Microfone**. Aceite.
3. Para segurar o Option direito e falar, adicione o Terminal em **Ajustes do Sistema › Privacidade e Segurança › Monitoramento de Entrada**. Depois feche e reabra o Terminal.
4. Na primeira ação em um app, o macOS pede **Automação**. Aceite.

Comandos, notícias, perguntas sobre CSV, Python isolado, monitores de KPI e análise profunda estão em [`docs/USO.md`](docs/USO.md).

## Segurança

- Por padrão o Jarvis só **lê**: as ferramentas de terminal e escrita nem existem na sessão do Claude. Ações locais e reversíveis (abrir apps, volume, timers) sempre funcionam.
- `setting_sources=[]` impede que regras do seu `~/.claude/settings.json` passem por cima desse bloqueio.
- O servidor escuta só em `127.0.0.1`, e o WebSocket só aceita o próprio painel como origem.
- O Jarvis também carrega os servidores MCP que você configurou no Claude Code (`~/.claude.json`). Com o mesmo bloqueio, ferramentas com verbo de ação (`send`, `create`, `delete`...) ficam negadas até você ligar `--writes`.

## Como funciona

```
mic → VAD → Whisper (pt) → "Ei Jarvis"/Option → rota rápida (regex) → AppleScript
                                              └→ Claude Agent SDK → ferramentas mac/jarvis → fala frase a frase
```

- `src/jarvis/app.py`: orquestrador (voz, turnos, barge-in, timers, eventos do painel)
- `src/jarvis/router.py`: rota rápida em português
- `src/jarvis/brain/`: sessão do Claude, persona, bloqueio de permissões e ferramentas in-process
- `src/jarvis/news.py`, `telemetry.py`, `agenda.py`, `memory.py`: dados do painel
- `src/jarvis/dados.py`: leitura de CSV, perfil, agregados com anonimato k, calculadora e conferência dos números
- `ui/`: painel em React + Three.js

## Testes

```bash
uv run pytest --ignore=tests/e2e                              # unidade
uv run --with playwright playwright install chromium webkit   # uma vez
uv run --with playwright pytest tests/e2e                     # ponta a ponta, uns 4 minutos
```

Os de ponta a ponta usam o painel compilado (`ui/dist`) e sobem sozinhos um daemon de teste por módulo (`tests/e2e/daemon_teste.py`): é o Jarvis de verdade, com banco, cache e pastas de dados numa pasta temporária (o `data/` não é tocado) e o que é pago, externo ou lento simulado. O Claude vira um cérebro de roteiro que chama as ferramentas reais; a fala, um `say` falso; clima, notícias e Calendário, dados fixos. Um teste é reprovado se a página tiver erro de console ou requisição com falha que ele não provocou de propósito; o registro fica em `tests/e2e/saida/`.

## Documentação

- [`docs/USO.md`](docs/USO.md): comandos, notícias, perguntas sobre CSV, Python isolado, monitores e análise profunda
- [`docs/PLANO_ANALISE_DADOS.md`](docs/PLANO_ANALISE_DADOS.md): pesquisa, provas de conceito e roadmap da parte de dados
- [`docs/RELATORIO_TESTES.md`](docs/RELATORIO_TESTES.md): testes de ponta a ponta do painel, causa raiz das falhas e correções
- [`docs/INVENTARIO_TESTES.md`](docs/INVENTARIO_TESTES.md): os 76 itens de interface verificados
- [`_pocs/`](_pocs/): as provas de conceito, só com dados sintéticos

## Créditos

Ideias de dois projetos abertos:

- [adewaskar/jarvis](https://github.com/adewaskar/jarvis) (MIT): Claude Agent SDK como cérebro, bloqueio de ferramentas por verbo, persona curta, fala em streaming e barge-in.
- [henryklunaris/hey-jev](https://github.com/henryklunaris/hey-jev): VAD por energia, palavra de ativação no texto do Whisper, ações em AppleScript, timers e Keychain. As ideias foram reimplementadas, sem copiar o código.

O visual do painel se inspira no "Command Center" de [jarvis.institute](https://jarvis.institute/).
