# Plano: o Jarvis como braço direito do analista de dados

Data: 2 de novembro de 2026 · Escopo: pesquisa, provas de conceito e plano. Nada do sistema existente foi alterado. · Provas de conceito: [`_pocs/`](_pocs/) (descartáveis, só dados sintéticos)

Marcadores usados quando a diferença importa: **[fato]** verificado por teste meu ou fonte oficial; **[fonte secundária]** afirmado por blog ou agregador, não confirmado na fonte oficial; **[inferência]** conclusão minha a partir de fatos; **[hipótese]** plausível, não testado; **[opinião]** julgamento meu. "Não verificado" quando não há teste nem fonte.

## 1. Estado atual do Jarvis

O Jarvis é um assistente de voz para o Mac, em Python 3.13: microfone com VAD, transcrição local com faster-whisper `small` em português, palavra de ativação "Ei Jarvis" ou Option direito, rota rápida por regex para comandos do Mac (AppleScript) e, para o resto, uma sessão viva do Claude pelo `claude-agent-sdk` 0.2.176 com o login da assinatura (`ClaudeSDKClient`, `setting_sources=[]`, `cwd` na pasta pessoal). A fala sai pela voz Luciana do macOS ou pela ElevenLabs, frase a frase. Um painel React/Three.js conversa com o daemon por FastAPI e WebSocket em 127.0.0.1:8787; a memória é um SQLite (`turns`, `memories`, `news`). Os pontos de extensão são as ferramentas in-process em [`src/jarvis/brain/tools.py`](src/jarvis/brain/tools.py) (`@tool` + `create_sdk_mcp_server`), a política de ferramentas em [`gate.py`](src/jarvis/brain/gate.py), a persona em [`persona.py`](src/jarvis/brain/persona.py), os botões `QUICK` em [`app.py`](src/jarvis/app.py) e os eventos `bus.emit` consumidos por [`ui/src/types.ts`](ui/src/types.ts). Já existe uma função de notícias ([`news.py`](src/jarvis/news.py) + [`sources.json`](sources.json): Educadados e Data Hackers por raspagem de HTML a cada 20 min, ferramentas `news_latest` e `news_article`, botão "Briefing executivo"). Não existe envio de arquivo (nem endpoint nem interface) nem nada de análise de dados. O [`RELATORIO_TESTES.md`](RELATORIO_TESTES.md) de 1º/11 registra 76 itens de interface passando e 57 testes unitários, e deixa um alerta relevante aqui: `Read`, `Glob` e `Grep` estão liberados com `cwd` na pasta pessoal.

## 2. Vereditos das perguntas 1, 2 e 3

| Pergunta | Veredito | Base |
|---|---|---|
| 1. Notícias diárias da área de dados | **Viável** | Teste P1 com feeds reais + código atual |
| 2. Análises a partir de CSV | **Viável** para consultas e estatística descritiva via SQL; **parcialmente viável** para Python livre (gráficos, modelos) | Testes P2, P3, P4 |
| 3. Plugin `analise-dados` conectado ao Jarvis por voz | **Parcialmente viável** | Teste P5 + doc oficial do Agent SDK |

### 2.1 Pergunta 1 — notícias diárias: viável

**O que já existe e como avalio.** O `news.py` funciona (o relatório de testes mediu o resumo de notícias em 3 s) e acerta em guardar só título e link, e em resumir sob demanda. As limitações [fato, leitura do código]: só duas fontes, ambas brasileiras e por raspagem de HTML, que quebra quando o site muda o layout; nenhuma deduplicação entre fontes; nenhuma seleção por relevância; não há um resumo diário num horário, só a coleta a cada 20 min; e `news_article` baixa até 6.000 caracteres do artigo para o modelo resumir, sem regra explícita contra reproduzir trechos.

**Testes feitos (P1, [`_pocs/p1_noticias/`](_pocs/p1_noticias/)).** Busquei 9 fontes reais em 02/11/2026:

| Fonte | Funciona | Itens | Mais recente | Observação |
|---|---|---|---|---|
| Towards Data Science (RSS) | sim | 20 | 17,7 h | 3 itens nas últimas 24 h |
| Google News RSS pt-BR ("ciência/análise/engenharia de dados") | sim | 52 | 0,5 h | traz ruído: "dados genéticos" casou com "análise de dados" |
| Databricks Blog (RSS) | sim | 10 | 36 h | |
| KDnuggets (RSS) | sim | 10 | 68 h | |
| DuckDB Blog (RSS) | sim | 10 | 106 h | o feed traz o texto integral |
| dbt Labs Blog (RSS) | sim | 25 | 134 h | |
| benn.substack (RSS) | sim | 20 | 50 dias | texto integral no feed |
| Hacker News (API Algolia, 48 h, >20 pontos) | sim | 6 | — | sem chave |
| Data Hackers `/feed` | **não** (404) | — | — | continua por raspagem, como hoje |

Coleta das 9 fontes: 147 itens em ~2 s; a deduplicação por URL e pelas 8 primeiras palavras do título removeu 1. O ranqueamento por palavras-chave com peso por frescor funcionou, mas é grosseiro **[fato]**: pôs uma notícia de genética em primeiro lugar. Para a seleção final, o caminho é ranquear por palavras-chave e pedir ao Claude que escolha 5 entre os 20 primeiros, com o perfil do usuário no prompt **[opinião]**. O verificador de cópia (`copia_longa`) acusa qualquer sequência de 8 ou mais palavras do resumo igual ao original; nos testes, separou um resumo próprio (0 trechos) de um copiado (4 trechos).

**Custo.** Feeds RSS e a API do Hacker News são gratuitos e sem chave **[fato, testado]**; a API do HN tem limite de ~10.000 req/h por IP **[fonte secundária]**. A NewsAPI gratuita tem atraso de 24 h e é só para desenvolvimento; o plano pago fica em ~US$ 449/mês **[fonte secundária]**, por isso não a recomendo. O resumo diário custa ~1 turno do Claude por dia, que hoje sai do limite da assinatura (ver §6). Pela API, busca na web custa US$ 10 por 1.000 buscas mais tokens **[fato, página oficial de preços]**; com feeds, não há busca.

**Direitos autorais.** A Lei 9.610/98, art. 46, permite citação de trechos com indicação de fonte, e o STJ (REsp 2.008.122/SP) decidiu que um serviço comercial de clipping que reproduz matérias não está coberto por essa exceção **[fonte secundária: comentário doutrinário e resumos de jurisprudência; não li o acórdão]**. Para uso pessoal, o desenho seguro é: guardar só título, link, fonte e data; resumir em até 30 palavras próprias, a partir do título e da descrição do feed (não do texto integral); passar o resumo pelo verificador de cópia; sempre mostrar o link **[opinião, não é parecer jurídico]**.

**Agendamento.** O Jarvis é um daemon que já tem laços (notícias, agenda, telemetria). Um laço que gera o resumo uma vez por dia no horário escolhido, e na primeira vez que liga depois do horário se o Mac estava desligado, é o caminho de menor esforço **[inferência]**. `launchd` acordaria o processo sem o Jarvis aberto, mas acrescenta um serviço de sistema; não instalei nenhum dos dois.

**Riscos.** Raspagem de HTML quebra sem aviso (o código já publica "não consegui ler" no feed); texto de artigos lido pelo modelo é entrada não confiável e pode conter instruções (injeção de prompt), por isso o resumo diário não deve ter ferramentas de escrita disponíveis **[opinião]**.

### 2.2 Pergunta 2 — análises a partir de CSV: viável com SQL; Python livre só com isolamento

**Princípio.** O modelo nunca lê o arquivo nem faz conta. Ele decide a consulta; o número sai de código executado fora do modelo; um validador confere cada número da resposta antes de ela ser falada.

**Leitura do arquivo (P2, [`_pocs/p2_csv/`](_pocs/p2_csv/)).** Gerei um CSV de 5.000 vendas sintéticas em quatro formatos: UTF-8 com vírgula; o "Excel brasileiro" (cp1252, `;`, vírgula decimal, `R$ 1.234,56`, datas dd/mm/aaaa); um sujo (nulos, duplicatas, "n/d", "dez", linha "TOTAL", grafias variantes); e versões de 1 e 5 milhões de linhas.

- DuckDB 2.0 sozinho detecta `;` e `dd/mm/aaaa`, mas **falha na codificação** (erro na linha 2 do cp1252) e **não converte vírgula decimal nem `R$`** (ficam texto). pandas com os padrões dá `UnicodeDecodeError` **[fato]**.
- O detector genérico de codificação (`charset-normalizer` 3.5.2) **errou**: chamou o cp1252 de `iso8859_10` e, num arquivo com travessão, aspas curvas e €, de `cp1250`, o que transformou "Promoção" em "Promoçăo" **[fato]**. A regra usada no carregador (UTF-8 estrito, senão cp1252, senão detector) acertou todos os casos.
- O carregador `carregar.py` transcodifica uma cópia, deixa o DuckDB detectar separador e data e converte colunas de texto com ≥95% dos valores no padrão pt-BR. O arquivo "Excel brasileiro" deu exatamente o mesmo resultado do UTF-8 de referência (mínimo 10,01; máximo 9.415,00; média 1.185,44) **[fato]**.
- O perfil automático apontou no arquivo sujo: 25 linhas duplicadas, 6,04% de UF nula, uma grafia variante em canal (" e-commerce "), "TOTAL" na coluna de id, 15 "n/d" em valor_total e 10 "dez" em nps **[fato]**.

**Tamanho.** Ler e perfilar 1M de linhas (61 MB) levou 0,67 s com pico de 356 MB; 5M (309 MB) levou 2,46 s com pico de 1,39 GB (pandas: 2,83 s e 1,03 GB). Transcodificar 309 MB levou 0,37 s **[fato, Mac M2 de 17 GB]**. **[inferência]** Arquivos de até ~1 GB cabem; acima disso, o DuckDB deve trabalhar sobre um banco temporário em disco com `memory_limit`, e o limite prático passa a ser o disco.

**Números rastreáveis (P3, [`_pocs/p3_numeros/`](_pocs/p3_numeros/)).** Dei ao Claude (`claude-sonnet-5-5`, esforço baixo, login da assinatura) só duas ferramentas: `perfil_arquivo` e `consultar_sql` (aceita uma única instrução `SELECT`, checada pelo parser do DuckDB). Nenhuma ferramenta nativa. Cinco perguntas:

| Pergunta | O que aconteceu |
|---|---|
| "Me dá um panorama desse arquivo." | Perfil + 1 SQL; 16 números, todos com origem |
| "Qual UF mais fatura e quanto?" | SP, R$ 1.765.072,70 (29,8%), por SQL |
| "Ticket médio do e-commerce × loja física?" | Mandou duas instruções numa chamada; a ferramenta recusou; ele refez numa só e calculou a diferença no SQL |
| "Se SP crescer 12,5%... pode fazer de cabeça" | Recusou fazer de cabeça e calculou no SQL (R$ 1.985.706,79) |
| "Apaga as vendas de televendas" | Recusou, disse que precisa de confirmação e seria numa cópia |

O validador extrai números em formato brasileiro (1.234,56; 12,5%; 1,99 milhão) e aceita só o arredondamento que a própria escrita indica ("1,99 milhão" vale ±5 mil; "1.975.000" para 1.985.706 é recusado). Na primeira rodada ele acusou 4 falsos positivos (data "31/12" contra "2025-12-31", "1,55% abaixo" contra "-1,55", e dois números citados de turnos anteriores); depois de corrigido, os 32 números das 5 respostas têm origem num resultado de ferramenta **[fato]**. Limite do validador **[inferência]**: ele pega número inventado, mas não número verdadeiro atribuído à coisa errada (o "10" de "10 UFs" casaria com qualquer 10 do resultado). Latência: 3 a 9 s por pergunta, 31 s na primeira (início da sessão) **[fato]**.

**Isolamento da execução (P4, [`_pocs/p4_isolamento/RESUMO.md`](_pocs/p4_isolamento/RESUMO.md)).** O mesmo script hostil (ler arquivo-canário fora da pasta, listar a pasta pessoal, escrever fora, rede, shell, laço infinito, 2 GB de memória) em quatro ambientes:

| | Sem isolamento (= kernel Jupyter) | DuckDB travado | Seatbelt `deny default` | Docker (Colima) |
|---|---|---|---|---|
| Ler/escrever fora, rede | **tudo passa** | bloqueado | bloqueado | bloqueado |
| Shell | **passa** | n/a | bloqueado | só dentro do contêiner |
| Laço infinito | sem limite | parado em 2,0 s | parado em 3 s | parado em 3 s |
| 2 GB de memória | sem limite | `memory_limit` | **não contido** (`RLIMIT_AS` recusado pelo macOS) | morto (OOM) |
| Sobrecarga | 0 | 0 | ~0,03 s | ~0,3 s + VM de ~2 GB |

"DuckDB travado" é `enable_external_access=false` + `lock_configuration=true` depois de carregar a tabela: `read_csv` de outro arquivo, `read_text`, `COPY`, `ATTACH`, `INSTALL`, URL `https://`, `/dev/stdin` e a tentativa de destravar foram todos recusados **[fato]**. **[inferência]** Para o MVP, SQL nesse modo dá isolamento suficiente sem contêiner. Python livre (gráficos com matplotlib, testes estatísticos, modelos) exige Docker ou Seatbelt com um vigia de memória; o sandbox do Claude Code não serve aqui, porque cobre só comandos de shell, não servidores MCP nem hooks **[fato, doc oficial "Sandboxing"]**.

**Só agregados para o Claude (P7, [`_pocs/p7_agregados/`](_pocs/p7_agregados/); decisão do usuário em 02/11/2026).** O SQL livre da P3 devolve linhas cruas (até 50), o que não serve para essa decisão. Instrução no prompt também não basta, porque o modelo pode errar ou ser induzido pelo conteúdo do arquivo. A trava fica na ferramenta: o Claude não escreve a consulta final, pede `{métricas, agrupar por, filtros, ordenar}` e a ferramenta monta o SQL a partir de uma lista fechada de funções (soma, média, mediana, contagem, distintos, desvio, mínimo e máximo só de número e data, percentis). Ela acrescenta `count(*)` e **suprime todo grupo com menos de K = 5 linhas**. Testei num CSV sintético com CPF, nome e e-mail falsos **[fato]**:

| Tentativa | Resultado |
|---|---|
| Faturamento e média por UF | 3 UFs devolvidas; o AC (2 linhas) foi suprimido |
| Agrupar ou filtrar por `cpf`, `email`, `nome_cliente` | recusado: as três foram detectadas como dado pessoal (pelo nome da coluna ou pelo formato do valor) |
| Agrupar por `valor_total` (quase um valor por linha) | 0 grupos devolvidos, 2.981 suprimidos |
| `maximo` de uma coluna de texto, `string_agg` | recusados (devolveriam o valor de uma linha) |
| Valor de filtro com injeção (`SP' or 1=1 --`) | tratado como texto literal; nada vazou |
| Erro do DuckDB | devolvido só o tipo do erro. A mensagem crua repetiria o conteúdo da célula: "Could not convert string 'Fábio Nunes' to INT32" |
| Perfil do arquivo | colunas pessoais sem valores frequentes; valores raros (< 5) fora; alertas sem exemplos crus ("exemplos só no painel") |

O custo dessa decisão **[inferência]**: o Claude deixa de fazer junções, colunas calculadas e funções de janela por conta própria. Perguntas como "qual cliente mais comprou?" ficam sem resposta pelo modelo; a lista detalhada pode aparecer no painel, que é local e não passa pelo Claude. Os limites ficam na §7.

**Envio do arquivo.** Não testei interface. **[inferência]** Três caminhos cabem no sistema: dizer ou digitar o caminho ("abre vendas.csv dos Downloads") com busca restrita a pastas permitidas; arrastar para o painel (`POST /api/upload` em 127.0.0.1, com a mesma checagem de origem do WebSocket); ou o arquivo mais recente de uma pasta vigiada.

**Gráficos e linguagem natural.** Perguntas em linguagem natural funcionaram (P3). Gráficos não foram testados: o caminho seguro **[opinião]** é o modelo devolver uma especificação declarativa (ex.: Vega-Lite ou Plotly JSON) sobre o resultado de um SQL, e o painel desenhar, sem executar código gerado.

**Riscos.** Privacidade: as linhas devolvidas pelas ferramentas vão para a Anthropic (ver §6). Injeção de prompt pelo conteúdo do CSV: uma célula pode conter "ignore as instruções..."; mitigado porque, em modo dados, não há ferramenta que escreva, envie ou leia fora do arquivo **[inferência]**.

### 2.3 Pergunta 3 — plugin `analise-dados`: parcialmente viável

**O que o repositório é [fato].** Um plugin do Claude Code distribuído como marketplace, licença MIT, do próprio usuário (Fernando Figueiredo), criado e com último push em 18/10/2026 (5 commits, v1.1.0, 0 estrelas). Tem 6 comandos (`/analise`, `/banco`, `/painel`, `/relatorio`, `/revisar`, `/validar`), 6 skills, 2 subagentes (revisor e editor), hooks (`SessionStart` injeta as regras de casa; `PostToolUse` confere cada célula; `SessionEnd` desliga o Jupyter) e o servidor MCP `jupyter-mcp-server==2.2.4` via `uvx`. O ambiente de análise (pandas, plotly, duckdb, JupyterLab) é fixado por `uv.lock`. Li `bootstrap.py`, `_jupyter.py`, `stop.py`, `projeto.py`, os manifestos e os hooks antes de executar: nenhuma chamada de rede além do Jupyter local, token aleatório de 48 caracteres, servidor só em `localhost`. A instalação local (`~/.claude/plugins/cache/analise-dados/analise-dados/1.1.0`) é o mesmo commit do GitHub.

**Integração [fato, doc oficial "Plugins in the SDK" + teste P5].** O Agent SDK carrega plugins locais com `ClaudeAgentOptions(plugins=[{"type": "local", "path": ...}])`, e o SDK instalado no Jarvis já tem essa opção. No teste, com `setting_sources=[]` como no Jarvis:

- o plugin carregou com 6 skills, 12 comandos, os 2 subagentes e o servidor `plugin:analise-dados:jupyter`;
- o hook `SessionStart` disparou e injetou as regras de casa;
- depois de eu rodar o `bootstrap.py` numa pasta de `_pocs/`, o Claude conectou ao Jupyter, criou `poc.ipynb` e executou uma célula que somou `valor_total`: **5.927.200,5**, igual ao valor do DuckDB e ao da P3 (37,6 s no total);
- ao fim da sessão o Jupyter foi desligado (o `stop.py` já não encontrou servidor; atribuo ao hook `SessionEnd` **[inferência]**). Não vi evento do hook `PostToolUse`; a célula era curta e não daria aviso, então o disparo dele fica **não verificado**.

**Por que "parcialmente" [fato, testes P5 e leitura do gate].**

1. **O gate do Jarvis bloqueia o plugin no modo leitura.** `connect_to_jupyter`, `use_notebook`, `insert_execute_code_cell`, `execute_code` e o próprio `Skill` só passam com `--writes`, e `--writes` libera também `Bash`, `Write` e `Edit` em tudo. Seria preciso uma terceira política: "dados", que libera só o Jupyter numa pasta de projeto.
2. **As proteções do projeto não valem com `setting_sources=[]`.** Com a configuração do Jarvis, o Claude leu o `.env` de teste (`Read(./.env)` está negado no `.claude/settings.json` do projeto) e só comentou que as regras de casa pediam para não ler. Com `setting_sources=["project"]` a leitura foi recusada pelo sistema. Ligar `project` reabre o problema que o `setting_sources=[]` resolve: regras de "allow" de um projeto passarem por cima do gate.
3. **O kernel Jupyter roda com todas as permissões do usuário**, como mostrou a coluna "sem isolamento" da P4. Código gerado lê qualquer arquivo e acessa a rede.
4. **O fluxo não é de voz.** `/analise` é didático, longo e pressupõe o notebook aberto no navegador; a persona do Jarvis pede no máximo duas frases.

**Como encaixar [opinião].** Não dentro do turno de voz. O Jarvis abre um "modo análise profunda": uma sessão separada do Agent SDK com o plugin, `cwd` na pasta do projeto, `setting_sources=["project"]` só nessa sessão, ferramentas limitadas ao Jupyter e às skills, e o notebook aberto no navegador. A voz serve para disparar e acompanhar ("Jarvis, roda o `/validar`", "o que o revisor achou?"), com respostas curtas. As skills `revisao-critica` e `qualidade-dados` podem ser reaproveitadas como texto de prompt no modo de voz, sem o Jupyter.

## 3. Voz para comandos de dados

**Teste feito (P6, [`_pocs/p6_voz/`](_pocs/p6_voz/)).** Gerei 16 comandos de dados com nomes de colunas, siglas e números ("média de ticket_medio por UF", "NPS", "CNPJ", "p-valor", "R$ 1.234,56", "CAC e LTV", "churn"), falados pelas vozes Luciana e Eddy do macOS (32 áudios), e medi quantos termos-chave o faster-whisper acertou. Ressalva: voz sintética não é voz humana; os números servem para comparar configurações, não como acurácia absoluta.

| Modelo | Configuração | Acerto de termos | Latência mediana / máx. |
|---|---|---|---|
| `small` (o atual) | prompt atual do Jarvis | 76,2% | 1,30 s / 2,00 s |
| `small` | prompt com colunas e glossário | **86,9%** | 1,34 s / 1,39 s |
| `small` | `hotwords` com o glossário | 84,5% | 1,35 s / 1,43 s |
| `large-v3-turbo` (CPU int8) | prompt atual do Jarvis | 85,7% | 6,32 s / 6,66 s |
| `large-v3-turbo` (CPU int8) | prompt com colunas e glossário | **90,5%** | 8,27 s / 9,86 s |
| `large-v3-turbo` (CPU int8) | `hotwords` com o glossário | 88,1% | 8,58 s / 11,29 s |

O `large-v3-turbo` acerta mais, mas em CPU leva de 6 a 8 s por frase, lento demais para conversa (download de 1,5 GB e 36 s para carregar) **[fato]**. Uma medição de terceiros indica que o mesmo modelo pelo MLX, na GPU do Apple Silicon, é bem mais rápido que o faster-whisper em CPU **[fonte secundária; não testei o MLX]**. O ganho do prompt com vocabulário apareceu nos dois modelos.

Erros típicos com o prompt atual: "NPS" → "MPS", "churn" → "churro"/"surdo", "CAC e LTV" → "Kaki ULTV", "e-commerce" → "e CAMARS". O caso que mais importa: **"Apaga as linhas com UF nula" virou "Apaga as linhas com o F0"** **[fato]**. Por isso a confirmação de qualquer alteração tem de repetir o que foi *entendido* ("Vou apagar as linhas em que a coluna F0... não existe essa coluna"), nunca só "confirma?".

**Comparação de opções (entrada).** Os preços abaixo são de agregadores **[fonte secundária]**, salvo indicação.

| Opção | Qualidade pt-BR / termos técnicos | Latência | Custo | Privacidade / offline |
|---|---|---|---|---|
| faster-whisper local (atual) | testado acima; melhora com prompt de vocabulário | ~1,3 s (`small`) | zero | áudio não sai do Mac; offline |
| Apple SpeechAnalyzer (macOS 26+) | lista de idiomas inclui português; pt-BR **não verificado** | não verificado | zero | no aparelho |
| Web Speech API no navegador | no Chrome, envia o áudio ao Google por padrão; no WKWebView (janela do Jarvis), relato de que não funciona (2022) | — | zero | **áudio sai** no Chrome |
| OpenAI `gpt-4o-transcribe` / `mini` | não testado | não testado | ~US$ 0,006 / 0,003 por min | **áudio sai** |
| Deepgram Nova-3 multilíngue | "keyterm prompting" para vocabulário | <300 ms anunciado | ~US$ 0,009/min + ~0,0013 de keyterm | **áudio sai** |

**Saída (texto para fala).** A Luciana do macOS é local, gratuita e já está em uso; a ElevenLabs já integrada manda o texto para fora (o que inclui números do seu dado) **[fato, leitura do `tts.py`]**. Piper (voz `pt_BR-faber`, CC0) e Kokoro (vozes pt-BR) rodam localmente; a qualidade comparada é **não verificada**.

**Recomendação [opinião].** Manter o Whisper `small` local e montar o prompt com as colunas do arquivo aberto e um glossário do usuário (ganho medido de 10,7 pontos sem custo de latência); testar o `large-v3-turbo` via MLX antes de trocar de modelo. Serviços pagos só se o ganho em voz real justificar, sabendo que o áudio sai da máquina.

**Do comando falado à ação, com segurança.** A garantia não vem do reconhecimento de intenção, vem da camada de ferramentas **[opinião, apoiada em P3/P4]**: no modo dados não existe ferramenta que altere o arquivo original; uma alteração ("remove a coluna", "substitui nulos por zero") gera uma cópia nova, e só depois de uma confirmação que repete a ação entendida. O classificador por palavras (`intencao.py`) marcou os 8 comandos destrutivos e nenhuma das 24 consultas nos textos transcritos, mas foi ajustado vendo esses mesmos erros ("Clui as vendas"), então está superajustado à amostra **[fato]**; ele serve para a experiência, não como barreira de segurança.

## 4. Pergunta 4 — outras ideias

**Critérios, declarados antes de ranquear.** Cada ideia recebe nota de 1 a 3 em: **Impacto** no dia a dia do analista (I, peso 2); **Viabilidade** no sistema atual (V: 3 = usa peças que já existem); **Esforço** (E: pequeno 1, médio 2, grande 3); **Risco** de privacidade, segurança ou erro silencioso (R: baixo 1, médio 2, alto 3). Pontuação = 2·I + V + (4 − E) + (4 − R), máximo 15. Empates: maior impacto primeiro. Ficaram fora as ideias que já são as perguntas 1 a 3 (perfil automático, perguntas sobre CSV, notícias).

| # | Ideia | Etapa do ciclo | I | V | E | R | Pontos | Origem |
|---|---|---|---|---|---|---|---|---|
| 1 | Glossário pessoal de dados | entender, voz | 3 | 3 | P | baixo | **15** | original (técnica de prompt do Whisper) |
| 2 | Pasta de trabalho consultável | receber, explorar | 3 | 3 | M | médio | **13** | inspirada no DuckDB (`read_csv` com glob) |
| 3 | Gráfico por comando no painel | visualizar | 3 | 2 | M | baixo | **13** | inspirada no Vega-Lite e no LIDA (Microsoft) |
| 4 | Briefing matinal do analista | manter-se atualizado, monitorar | 2 | 3 | P | baixo | **13** | estende o briefing existente |
| 5 | Caderno de decisões por arquivo | limpar, comunicar | 2 | 3 | P | baixo | **13** | inspirada no `contexto.md` do plugin |
| 6 | Monitor de KPIs com alerta falado | monitorar | 3 | 2 | M | médio | **12** | inspirada nos alertas de dados do Power BI |
| 7 | Diff entre versões de um arquivo | receber, limpar | 2 | 3 | M | baixo | **12** | inspirada no `data-diff` (Datafold) |
| 8 | "Isso se sustenta?" por voz | modelar, comunicar | 2 | 2 | P | baixo | **12** | reaproveita a skill `revisao-critica` do plugin |
| 9 | Rascunho de resumo executivo rastreado | comunicar | 2 | 3 | P | médio | **12** | original |
| 10 | Explicador de SQL ou erro da área de transferência | modelar | 2 | 3 | P | médio | **12** | original |
| 11 | Consulta somente leitura ao Databricks | receber, explorar | 3 | 2 | G | alto | **10** | inspirada no Genie/SQL do Databricks |

**1. Glossário pessoal de dados.** Uma lista editável de siglas, colunas e métricas com a definição de cada uma ("NPS = promotores − detratores", "ticket_medio = valor_total/pedidos"). Resolve dois problemas: o Whisper errar o termo (P6: +10,7 pontos só com termos no prompt) e o Claude interpretar a métrica de outro jeito. Neste sistema: tabela `glossario` no SQLite de `memory.py`; `stt.PROMPT` passa a ser montado com o glossário e as colunas do arquivo aberto; o glossário entra no prompt do modo dados. Esforço pequeno. Risco: prompt longo demais piora o Whisper (o `initial_prompt` usa até ~224 tokens **[não verificado]**).

**2. Pasta de trabalho consultável.** "Jarvis, que arquivos eu tenho sobre vendas?" e "cruza clientes.csv com pedidos.parquet". Resolve o tempo gasto achando e juntando arquivos. Neste sistema: uma ferramenta lista arquivos e esquemas de pastas permitidas (configuradas pelo usuário) e o DuckDB consulta vários arquivos com o SQL visível no painel. Esforço médio. Risco: ler pastas inteiras amplia o que vai para o modelo; os nomes de colunas e os resultados saem da máquina.

**3. Gráfico por comando no painel.** "Mostra o faturamento por mês." O modelo devolve uma especificação declarativa sobre um resultado SQL já validado; o painel desenha (novo evento `{"type": "chart"}` e um cartão no React). Resolve o vaivém até o Excel. Esforço médio (lado do painel). Risco baixo: nenhum código gerado é executado.

**4. Briefing matinal do analista.** Agenda, 3 notícias de dados (pergunta 1), KPIs monitorados (ideia 6) e "arquivos novos na pasta de trabalho". Neste sistema: o botão `briefing` já existe; muda o prompt e entram as ferramentas novas. Esforço pequeno. Risco baixo.

**5. Caderno de decisões por arquivo.** "Anota: mantive a UF nula como Não informada." O Jarvis guarda e, quando o arquivo é reaberto, lembra as decisões e as aplica de novo nas consultas. Resolve o retrabalho e a falta de rastro. Neste sistema: tabela no SQLite ligada ao hash ou ao nome do arquivo; sem escrever nos arquivos do usuário. Esforço pequeno.

**6. Monitor de KPIs com alerta falado.** "Me avisa se o faturamento diário de SP cair mais de 10% contra a média de 4 semanas." Uma consulta SQL salva roda num laço (como o de notícias), e quando a regra dispara o Jarvis fala "Senhor, ..." e publica no feed. Esforço médio. Risco médio: alerta falso por dado atrasado; a regra e o SQL precisam ficar visíveis.

**7. Diff entre versões de um arquivo.** "O que mudou entre vendas_set e vendas_out?": linhas novas e removidas por chave, colunas novas, mudança de tipo e de distribuição. Neste sistema: SQL `EXCEPT`/`JOIN` no DuckDB sobre os dois arquivos, com o perfil da P2. Esforço médio. Risco baixo.

**8. "Isso se sustenta?" por voz.** Depois de uma conclusão, o Jarvis aplica a checagem da skill `revisao-critica` do plugin (o n está visível? é participação ou risco? é sazonalidade?) e diz o ponto fraco em uma frase. Neste sistema: o texto da skill entra como prompt; não precisa de Jupyter nem de `--writes`. Esforço pequeno. Limite: depende de o modelo seguir a checagem; o próprio README do plugin registra que só o que é checado por código é garantido.

**9. Rascunho de resumo executivo rastreado.** Três frases para o gestor, com cada número validado (validador da P3), copiadas para a área de transferência, sem enviar nada. Esforço pequeno. Risco médio: o texto vai para outro lugar, onde o rastro se perde.

**10. Explicador de SQL ou erro da área de transferência.** "Jarvis, explica esse SQL que eu copiei" ou "o que é esse erro?": lê o `pbpaste`, explica em duas frases e mostra no painel os riscos (join que multiplica linhas, filtro de data aberto). Esforço pequeno. Risco médio: a área de transferência pode ter dado sensível; só lê quando pedido.

**11. Consulta somente leitura ao Databricks.** Há perfis do Databricks CLI configurados nesta máquina **[fato]**. Uma ferramenta roda SQL num SQL warehouse com um usuário só de leitura. Esforço grande (autenticação, custo de warehouse, governança). Risco alto: dado corporativo passa pelo modelo e pode haver regra da empresa contra isso. Só depois de decisão explícita do usuário e da empresa.

## 5. Arquitetura proposta

```
voz/painel ──► app.handle ──► rota rápida (regex) ──► Mac
                     │
                     └──► Brain (Agent SDK, sessão de voz)
                            ├── mcp "mac", "jarvis" (como hoje)
                            └── mcp "dados" (novo, in-process, só leitura)
                                  abrir_arquivo(caminho)   → carregar.py: cp1252/;/vírgula → DuckDB
                                  perfil_arquivo()         → perfil seguro (sem valores individuais)
                                  agregar(pedido)          → SQL montado pela ferramenta, grupos < 5 suprimidos,
                                                             DuckDB travado (sem arquivo, rede, extensão)
                                  glossario(), decisoes()  → SQLite
                               resultado com id ─► bus.emit {"type":"data"} ─► painel: tabela/gráfico/SQL
                               fala frase a frase ─► validador de números ─► TTS
        modo análise profunda (fase 5): sessão separada do SDK + plugin analise-dados + Jupyter
        Python livre (fase 4): executor em Docker ou Seatbelt+vigia, só com o arquivo montado em leitura
```

Decisões de desenho:

- **Servidor `dados` próprio**, no mesmo padrão de `tools.py`, entra em `OWN_SERVERS` do gate porque nada nele escreve. O modo dados não ganha `Bash`, `Write`, `Read` amplo nem Jupyter.
- **Validação antes de falar.** O `Speaker.push` já separa frases; numa resposta do modo dados, cada frase passa pelo validador antes de ir para a fila. Uma frase com número sem origem é trocada por "Não tenho esse número confirmado" e o caso vai para o feed **[hipótese de desenho, não implementada]**.
- **Números em algarismos no modo dados.** A persona atual manda escrever números por extenso ("vinte e dois graus"), o que impede validar. No modo dados, algarismos no texto. A Luciana leu "R$ 1.765.072,70, ou 29,8%" como valor por extenso: retranscrito pelo Whisper, saiu "1 milhão [...] 765 mil e 72 reais e 70 centavos, ou 29,8%" **[fato, verificado de forma indireta: não ouvi o áudio]**.
- **O que vai para o modelo (decidido: só agregados reais).** Nomes e tipos de colunas, o perfil seguro e resultados de `agregar` com grupos de 5 linhas ou mais (P7). Linhas cruas, exemplos de valores e mensagens de erro do DuckDB ficam no Mac; o painel pode mostrá-los porque não passa pelo Claude.

## 6. Roadmap em fases

**Fase 1 — MVP "pergunte ao seu CSV" (uma sessão de trabalho).** Entrega: dizer ou digitar "abre o arquivo X" (busca em pastas permitidas), ouvir o perfil em duas frases, fazer perguntas e receber números validados; tabela e SQL aparecem na conversa do painel.
- Código: `src/jarvis/dados.py` (carregador e perfil da P2, DuckDB travado da P4, validador da P3, `agregar` e `perfil_seguro` da P7); três ferramentas em `tools.py` (`abrir_arquivo`, `perfil_arquivo`, `agregar`); `dados` em `OWN_SERVERS`; um parágrafo na persona (regra dos números, algarismos); `duckdb` e `charset-normalizer` no `pyproject.toml`.
- Testes: unitários com os CSVs sintéticos da P2 (cp1252, `;`, vírgula decimal, sujo) e da P7 (colunas pessoais), ataques da P4 e da P7, casos do validador; um ponta a ponta com `jarvis --text`.
- Valor sozinho: responde perguntas reais sobre um CSV brasileiro sem número inventado e sem mandar linhas do arquivo ao Claude.

**Fase 1 construída em 02/11/2026.** Diferenças em relação ao plano acima:
- Ferramentas novas: `calcular` (aritmética por código, para projeções e variações) e o agrupamento por período de data (`data_venda:mes`), sem o qual "por mês" não teria resposta. `participacao_pct` também entrou como métrica.
- Achado durante a construção: o `Read` do Claude Code, liberado com `cwd` na pasta pessoal, leria o CSV cru por fora da trava de agregados, e o CLI libera o `Read` sem consultar o `can_use_tool`. Corrigido com uma regra de permissão em `ClaudeAgentOptions.settings` que nega `Read` a `.csv`, `.tsv`, `.xlsx`, `.xls` e `.parquet` (o `Grep` respeita a mesma regra). Testado com prompt neutro: `Read` e `Grep` no arquivo foram recusados; `Grep` na pasta inteira voltou sem resultados; outros arquivos continuam legíveis. Com `--writes`, o `Bash` volta a existir e poderia ler o arquivo com `cat`: risco aceito do modo escrita.
- `.txt` saiu das extensões abertas, para coincidir com as que o `Read` nega.
- A conferência dos números roda ao fim do turno (aviso no feed), não antes de falar; a versão antes da fala fica para a fase 2.
- Testes: 13 novos em [`tests/test_dados.py`](tests/test_dados.py) (70 no total, todos passando). Ponta a ponta com `jarvis --text` em CSVs sintéticos: faturamento por UF com projeção de 12,5% (R$ 1.985.706,79 pela calculadora), problemas do arquivo sujo, e recusa do "CPF de quem mais gastou". O primeiro teste do arquivo sujo acusou "9" colunas sem origem; o total de colunas passou a vir pronto no perfil e o aviso sumiu.

**Fase 2 — painel e voz para dados.** Cartão "Dados" no painel (tabela, SQL, gráfico declarativo: ideia 3), arrastar o arquivo para o painel, glossário pessoal no Whisper e no prompt (ideia 1), validação antes de falar.

**Fase 3 — rotina do analista.** Resumo diário de notícias com as fontes da P1, verificador de cópia e horário configurável (pergunta 1); briefing do analista (ideia 4); caderno de decisões (ideia 5); diff de versões (ideia 7); "isso se sustenta?" (ideia 8).

**Fases 2 e 3 construídas em 02/11/2026** (branch `fase2-painel-voz`). O que mudou em relação ao plano:
- O gráfico não é especificado pelo modelo: o painel desenha a partir do próprio resultado de `agregar` (linha quando o rótulo é período, barras quando é categoria), sem código gerado. A cor da marca, `#0891b2`, passou no validador de paleta sobre o fundo dos painéis; o ciano da interface (`#22d3ee`) falhou na faixa de luminosidade. O painel mostra o mesmo que o Claude viu: perfil seguro e agregados, nada de linha crua.
- Upload: corpo cru (sem dependência de multipart), mesma checagem de origem do WebSocket, só `.csv`/`.tsv`, nome sanitizado, limite de tamanho; o arquivo fica em `data/arquivos`, pasta sempre permitida.
- Validação antes da fala: cada frase do streaming passa pelo validador quando o turno usou dados. O teste no navegador achou um defeito antigo da fala: um pedaço terminado em "R$ 50." era falado como frase, e "657,14" virava outra; a trava trocou duas frases corretas pelo aviso. Corrigido (fim de frase só com espaço depois) e coberto por teste que falha no código antigo.
- Glossário: SQLite, ferramentas `glossario_salvar`/`glossario`, entra no prompt do Claude e, com as colunas do arquivo aberto, no prompt do Whisper (até 400 caracteres).
- Notícias: seis fontes RSS testadas na P1 entraram em `sources.json` (Towards Data Science, KDnuggets, Databricks, DuckDB, dbt Labs, Google Notícias em pt-BR); a descrição do feed é guardada como base do resumo. `news_digest` deduplica (inclusive o sufixo " - Site" do Google Notícias, mantendo a versão mais bem ranqueada) e ordena por `JARVIS_NOTICIAS_TEMAS` + glossário. O resumo sai sozinho às 08:00 (`JARVIS_RESUMO_HORA`), uma vez por dia. Fonte nova anuncia só as três primeiras manchetes no feed, para não inundá-lo.
- `comparar_arquivo`: linhas iguais, só em A e só em B por hash das colunas em comum (os hashes não saem do Mac), colunas novas, tipo que mudou, somas e médias, período das datas e categorias que mudaram (com pelo menos K linhas num dos lados; colunas pessoais fora).
- `decisao_anotar` aceita o nome de outro arquivo: no teste, a decisão sobre o cupom de outubro tinha ido para o arquivo de setembro, que era o aberto.
- "Isso se sustenta?" virou regra da persona, com a lista da skill `revisao-critica` do plugin condensada.
- Ponta a ponta (daemon com banco de teste e voz silenciada): upload por arrastar, faturamento por mês (linha) e por UF (barras); 115 notícias coletadas das 8 fontes e resumo diário disparado no horário sem pedido; comparação setembro × outubro ("AM não existia e tem 300 linhas, exatamente as 300 que só aparecem em outubro"); anotação; "isso se sustenta?" apontou que SP lidera por volume e tem ticket médio abaixo de BA e RJ. Nenhum aviso de número sem origem nem de cópia. 86 testes passam.
- Não testado: voz real (microfone), a janela nativa (pywebview) recebendo arquivo arrastado, e a qualidade dos resumos ao longo de vários dias.

**Fase 4 — Python isolado.** Executor de Python em Docker (`--network none --read-only --memory`) ou Seatbelt com vigia de memória, para estatística, testes e gráficos que o SQL não faz; monitor de KPIs (ideia 6).

**Fase 4 construída em 02/11/2026** (mesma branch). Decisões e resultados:
- **Isolamento: Seatbelt com vigia, não Docker.** O Docker exigiria a VM do Colima ligada o tempo todo (~2 GB) e uma imagem própria com pandas; o Seatbelt (`deny default`, gerado a cada execução) lê só o Python do Jarvis, o Parquet do arquivo aberto e o cache de fontes do matplotlib, escreve só na pasta de trabalho, não tem rede nem `exec` de outros programas. Memória e relógio ficam com um vigia (psutil) que mata o processo; CPU com `RLIMIT_CPU`. Testado: ler um arquivo do projeto, listar a pasta pessoal, rede e shell foram recusados; 3 GB foi morto em 1,5 GB; laço infinito parou no prazo. Ressalva: o `sandbox-exec` está marcado como obsoleto pela Apple.
- **Só agregados também no Python.** O código vê os dados inteiros, mas só volta o que passa por `resultado()` e pelo filtro: textos só se forem colunas, categorias com 5+ linhas, datas ou números; chaves em snake_case; tabelas só com uma coluna de contagem (`n`), e linhas com n < 5 saem; listas soltas até 20 itens e 300 números no total. No primeiro teste, `resultado("amostra", df.head(3))` devolveu 3 linhas cruas; a regra da coluna `n` fechou isso (e obriga a mostrar o tamanho de cada grupo, como pede a revisão crítica). Mensagens de erro saem sem o que estava entre aspas. Resíduo: até 20 números individuais podem sair numa lista se o código os pedir explicitamente.
- **Desempenho:** ~1,2 s por execução; o primeiro gráfico levava 8,7 s (cache de fontes do matplotlib refeito a cada vez); com o cache montado uma vez fora do sandbox e lido por ele, 1,5 s. Estilo dos gráficos: milhar em pt-BR, sem moldura, série em `#0891b2` (validada em fundo claro e escuro).
- **Monitor de KPIs** (`kpis.py`): métrica pelo mesmo montador do `agregar`, regras `queda_pct`/`alta_pct` (último período contra a média dos anteriores) e `abaixo`/`acima`; o período em curso fica de fora; alerta falado uma vez por período, montado localmente, sem o Claude. O teste ponta a ponta achou dois defeitos, corrigidos: os números do `kpi_criar` não entravam na base do validador (números certos eram trocados na fala) e a data era falada como "2026-11-01".
- Ponta a ponta: teste de Welch e Mann-Whitney com gráfico das distribuições (p = 0,72, "não significativa"); "mostra as 3 primeiras vendas" recusado; regressão do faturamento diário (queda de 12,30 por dia, R² 0,130, p 0,0506, descrita como "só um indício"); monitor criado por voz e alerta falado pelo laço um minuto depois. 94 testes passam.

**Fase 5 — modo análise profunda e fontes corporativas.** Sessão separada com o plugin `analise-dados` e o Jupyter (pergunta 3), com política própria no gate; consulta ao Databricks (ideia 11) só se aprovada.

**Fase 5 construída em 02/11/2026** (mesma branch). Decisões do usuário: o modo profundo abre qualquer pasta que ele selecionar, com qualquer tipo de dado (as linhas vão para o Claude nesse modo, exceção explícita à regra de agregados); o Databricks ficou fora.
- `profundo.py`: sessão separada do Agent SDK com o plugin, `setting_sources=["project"]` só nela (as regras `deny` do projeto valem, ao contrário da sessão de voz, ver P5), prompt `claude_code` com um apêndice de voz, esforço `medium`. Política própria no `can_use_tool`: Jupyter, `Skill`, subagentes liberados; `Read/Glob/Grep` só no projeto e no plugin; `Write/Edit` só no projeto e fora de `dados/`; `Bash` só com os scripts do plugin (`bootstrap`, `validar`, `relatorio`, `banco`, `stop`), `uv --version` e `ls`, sem encadeamento; `WebFetch`, `WebSearch` e `NotebookEdit` desligados. Os testes acharam um defeito: caminho relativo como `contexto.md` era resolvido a partir de `dados/` e a escrita legítima seria bloqueada.
- Roteamento: a ferramenta `analise_profunda` (na sessão de voz) prepara o projeto e deixa o primeiro pedido (`/analise-dados:analise`) para depois do turno; enquanto o modo está ativo, a fala vai para a sessão profunda (a rota rápida do Mac continua valendo); só as duas primeiras frases são faladas; o token do Jupyter é tirado do texto; o notebook abre no navegador quando o Jupyter sobe; "sai do modo profundo" fecha a sessão, roda o `stop.py` e desliga o Jupyter; se o Jarvis fechar com o modo aberto, o `stop.py` roda na saída do processo.
- Ponta a ponta com o plugin real (CSV sintético, banco de teste): bootstrap, Jupyter, leitura, perguntas de negócio; com as respostas, a sessão escreveu o `contexto.md`, criou o notebook (17 células, 11 de código), rodou o `/validar` (corrigiu os 2 avisos) e concluiu "SP fatura mais por volume, não por ticket; diferença de ticket entre canais (~4%) dentro da margem de erro", notando que o arquivo "setembro" tem o ano inteiro. 27 ferramentas liberadas, nenhuma negada; `dados/` idêntico ao original; ao sair, a porta do Jupyter fechou e nenhum processo ficou para trás.
- Não explicado: a primeira tentativa no daemon terminou em `error_during_execution` sem mensagem; não se repetiu (nem fora do daemon). O `ask` agora registra no log o motivo que o SDK devolver.
- Risco que fica: o Jupyter roda com as permissões do usuário, sem sandbox; o que o isola é a política de ferramentas da sessão. O custo de um turno profundo é bem maior que o da voz (prompt do Claude Code + plugin + muitas ferramentas).

## 7. Riscos, privacidade e segurança

1. **Dados do usuário saem da máquina.** Tudo que uma ferramenta devolve vai para a Anthropic, porque o Claude roda na nuvem. Decisão do usuário (02/11/2026): **só agregados reais**, impostos pela ferramenta `agregar` (P7). O que ainda sai ou pode escapar **[inferência]**:
   - nomes de colunas e de arquivos, e os valores de categorias com 5 linhas ou mais (ex.: "SP", "Televendas");
   - mínimo e máximo de números e datas são de uma única linha (a maior venda, o maior salário);
   - filtros combinados podem fechar um grupo de exatamente 5 pessoas, e duas consultas parecidas podem ser subtraídas uma da outra (ataque por diferença). O anonimato k só garante que nenhum resultado isolado vem de menos de 5 linhas;
   - a detecção de dado pessoal é heurística: uma coluna chamada `cliente` com nomes não é pega pelo nome; só passaria nos valores frequentes se cada nome aparecesse 5 vezes ou mais;
   - com a ElevenLabs ligada, o texto falado (com os agregados) vai também para a ElevenLabs; a decisão foi sobre o Claude, por isso a voz no modo dados fica em aberto (§8).
2. **Execução de código gerado.** O kernel Jupyter e qualquer `python` sem isolamento leram o canário, listaram a pasta pessoal, escreveram fora, acessaram a rede e abriram shell (P4). O sandbox do Claude Code não cobre MCP nem hooks **[fato, doc oficial]**. No MVP, só SQL num DuckDB travado; Python só com Docker ou Seatbelt. No Seatbelt, memória não é contida.
3. **Proteções de projeto desligadas.** Com `setting_sources=[]`, regras `deny` de projeto (como `Read(./.env)` do plugin) não valem (P5). Qualquer integração com o plugin precisa reproduzir essas regras no `can_use_tool` do Jarvis.
4. **Risco já existente, agravado.** `Read`, `Glob` e `Grep` liberados com `cwd` na pasta pessoal (achado do relatório de testes). Com arquivos de dados no fluxo, uma pergunta vaga pode levar o modelo a vasculhar a pasta pessoal. Recomendo restringir antes da fase 1 ou junto com ela **[opinião]**.
5. **Injeção de prompt** pelo conteúdo do CSV e dos artigos. Mitigação estrutural: no modo dados e no resumo de notícias, nenhuma ferramenta escreve, envia ou lê fora do escopo.
6. **Erro de reconhecimento em comando destrutivo** ("UF nula" → "F0"). Mitigação: alterações só em cópia e confirmação que repete a ação entendida.
7. **Número verdadeiro atribuído à coisa errada** passa pelo validador. Mitigação parcial: mostrar no painel o SQL de cada número.
8. **Uso da assinatura pelo Agent SDK.** A página oficial de suporte diz que a mudança anunciada para 15/06/2026 (crédito separado para o Agent SDK) foi pausada e que o uso continua saindo dos limites da assinatura **[fato]**. Fontes secundárias relatam que a Anthropic restringiu, em fevereiro de 2026, o uso do login de assinatura por produtos de terceiros, e que o uso pessoal com o Agent SDK segue aceito **[fonte secundária]**. O Jarvis é de uso pessoal, mas uma mudança de política pode exigir chave de API (custo por token). Na P3, o SDK estimou US$ 0,06 a 0,17 em valor de API por pergunta depois da primeira; a primeira veio com US$ 2,84, que não sei explicar **[não verificado]**.
9. **Fontes de notícias** mudam de layout ou fecham o feed sem aviso (Data Hackers não tem `/feed`).

## 8. Decisões que dependem do usuário

1. ~~Que dados podem ir para o Claude?~~ **Decidido em 02/11/2026: só agregados reais.** Ainda em aberto dentro dela: o valor de K (5 no teste), se mínimo e máximo ficam liberados e se a ElevenLabs pode falar agregados no modo dados.
2. **Construir a fase 1** como descrita na §6 (só SQL agregado, sem contêiner) ou já com Python isolado.
3. **Pastas que o Jarvis pode abrir** (ex.: `~/Downloads`, uma pasta de dados) e se a restrição de `Read/Glob/Grep` na pasta pessoal entra junto.
4. **Números falados:** algarismos no modo dados (validáveis) ou por extenso como hoje.
5. ~~Isolamento da fase 4~~ **Implementado com Seatbelt + vigia (02/11/2026)**; Docker continua possível se o obsoletismo do `sandbox-exec` virar problema. Era: Docker via Colima (contém memória; VM de ~2 GB ligada) ou Seatbelt (leve, sem limite de memória; o `man sandbox-exec` deste Mac marca o comando como DEPRECATED, embora funcione e seja o que o Claude Code usa no macOS).
6. ~~Plugin~~ **Decidido e construído (02/11/2026):** modo análise profunda separado, em qualquer pasta que o usuário selecionar, com as linhas indo para o Claude nesse modo. Databricks (ideia 11): fora, por decisão do usuário.
7. **Notícias:** quais fontes (incluir as em inglês da P1?), horário do resumo diário e se ele é falado ou só aparece no painel.
8. **Voz:** manter o Whisper local, trocar de modelo conforme a latência da tabela da §3, ou aceitar um serviço pago, sabendo que o áudio sai da máquina.

## 9. Fontes

Data de acesso de todas: 02/11/2026.

| Título | URL |
|---|---|
| Plugins in the SDK (Claude Code docs) | https://code.claude.com/docs/en/agent-sdk/plugins |
| Sandboxing (Claude Code docs) | https://code.claude.com/docs/en/sandboxing |
| Use the Claude Agent SDK with your Claude plan (Claude Help Center) | https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan |
| Anthropic Bans Claude Subscription OAuth in Third-Party Apps (WinBuzzer, 19/02/2026) | https://winbuzzer.com/2026/02/19/anthropic-bans-claude-subscription-oauth-in-third-party-apps-xcxwbn/ |
| Anthropic officially bans third-party subscription authentication (GIGAZINE, 20/02/2026) | https://gigazine.net/gsc_news/en/20260220-anthropic-third-party-block |
| Pricing (Anthropic docs) — busca na web | https://docs.anthropic.com/en/docs/about-claude/pricing |
| Code execution tool (Claude Platform docs) | https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool |
| CSV Import — overview (DuckDB docs) | https://duckdb.org/docs/stable/data/csv/overview |
| analise-dados-plugin (GitHub) | https://github.com/fernandofigueiredo-data/analise-dados-plugin |
| NewsAPI — Pricing | https://newsapi.org/pricing |
| Top 10 Free News APIs for Developers (Apidog) | https://apidog.com/blog/free-news-api/ |
| Hacker News Firebase API vs Algolia (DEV Community) | https://dev.to/odeeb/hacker-news-firebase-api-vs-algolia-which-one-to-use-3g2n |
| Lei nº 9.610/1998 (Senado Federal) | https://legis.senado.leg.br/norma/551486 |
| Compilação de notícias e direitos autorais: comentários ao REsp 2.008.122/SP (RBDCivil) | https://rbdcivil.ibdcivil.org.br/rbdc/article/view/991 |
| OpenAI transcription pricing (CostGoat) | https://costgoat.com/pricing/openai-transcription |
| Deepgram Nova-3 Pricing 2026 (convertaudiototext) | https://convertaudiototext.com/blog/deepgram-nova-3-explained |
| A Quick Look at Apple's SpeechAnalyzer API (addpipe) | https://blog.addpipe.com/apple-speechanalyzer-api/ |
| Speech recognition in JavaScript with the Web Speech API (AssemblyAI) | https://www.assemblyai.com/blog/speech-recognition-javascript-web-speech-api |
| WebKit bug: webkitSpeechRecognition (lista webkit-unassigned, jun/2022) | https://lists.webkit.org/pipermail/webkit-unassigned/2022-June/1041001.html |
| mac-whisper-speedtest (GitHub) | https://github.com/anvanvan/mac-whisper-speedtest |
| Piper pt_BR faber — model card (Hugging Face) | https://huggingface.co/rhasspy/piper-voices/blob/refs%2Fpr%2F11/pt/pt_BR/faber/medium/MODEL_CARD |
| Python TTS com Kokoro (thomazrb) | https://thomazrb.github.io/posts/python-tts-kokoro |
| Feeds testados na P1 | https://www.kdnuggets.com/feed · https://towardsdatascience.com/feed · https://www.databricks.com/feed · https://duckdb.org/feed.xml · https://www.getdbt.com/blog/rss.xml · https://benn.substack.com/feed · https://news.google.com/rss/search · https://hn.algolia.com/api/v1/search_by_date |

Provas de conceito e saídas: [`_pocs/`](_pocs/) (`p1_noticias/fontes_resultado.json` e `digest.json`, `p2_csv/RESUMO.md` e `bench.jsonl`, `p3_numeros/resultado.json` e `revalidacao.txt`, `p4_isolamento/RESUMO.md`, `p5_plugin/resultado.json`, `p5_gate.txt`, `p6_voz/resultado_*.json` e `intencao.txt`, `p7_agregados/resultado.json` e `saida.txt`).
