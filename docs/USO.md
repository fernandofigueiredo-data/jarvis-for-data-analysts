# Uso do Jarvis

Como usar e configurar cada parte. Para instalar, veja o [README](../README.md#instalar); todas as variáveis estão no [`.env.example`](../.env.example).

## Opções da linha de comando

| Comando | O que faz |
|---|---|
| `uv run jarvis` | Janela nativa + sempre ouvindo "Ei Jarvis" |
| `uv run jarvis --mode ptt` | Só escuta enquanto você segura o Option direito |
| `uv run jarvis --mode off` | Sem microfone; conversa digitando no painel |
| `uv run jarvis --no-window` | Sem janela; painel em http://127.0.0.1:8787 |
| `uv run jarvis --text "abre o Chrome"` | Um turno pelo terminal (`--speak` para falar a resposta) |
| `uv run jarvis --writes` | Libera ações que mudam o mundo (terminal, escrever arquivos, enviar) |

## Você: nome e tratamento

`JARVIS_NOME` entra no prompt ("assistente pessoal de voz da Ana"). `JARVIS_TRATAMENTO` define como o Jarvis fala com você:
- `senhor` (padrão): "O tempo acabou, senhor."
- `senhora`: "O tempo acabou, senhora."
- `nenhum`: "O tempo acabou."

## Saudação e agenda

"Bom dia, Jarvis" (ou "boa tarde", "boa noite"; por voz não precisa do "Ei Jarvis") recebe a mesma saudação com o seu nome, "Bom dia, Ana.", ou, sem `JARVIS_NOME`, com o tratamento ("Bom dia, senhor."). Logo depois vêm os compromissos de hoje (fuso do Mac), em ordem, com horário e título, lidos do app Calendário: valem as contas sincronizadas nele (iCloud, Google, Exchange). Sem compromissos, ele diz isso; se o Calendário não responder, ele avisa que não conseguiu ler a agenda.

## Local e clima

O campo Local do rodapé e o clima vêm, nesta ordem:
1. de `JARVIS_LOCATION`, se você definir uma cidade;
2. da localização do Mac, pelo app auxiliar "Jarvis Localização" (`src/jarvis/mac/localizacao/`). O macOS só entrega a localização a um app com permissão, e o Python do Jarvis não é um: o app é compilado na primeira vez em `cache/JarvisLocal.app` (precisa das Command Line Tools do Xcode) e o macOS pede a permissão uma vez;
3. da localização do navegador, quando o painel está aberto num navegador e o Mac não respondeu;
4. do IP, que costuma apontar para a cidade do provedor: aí o campo mostra "(aprox.)".

O local é relido a cada 30 minutos. As coordenadas vão ao OpenStreetMap só para virar "Cidade/UF". `JARVIS_LOCAL_PRECISO=0` desliga os passos 2 e 3.

## Voz da ElevenLabs

Com `ELEVENLABS_API_KEY` (no `.env` ou no Keychain), o Jarvis fala com a ElevenLabs no lugar da voz do macOS. A voz padrão é a Adam, uma das vozes padrão, que funcionam no plano gratuito; troque com `JARVIS_ELEVEN_VOICE_ID`. Vozes da Voice Library só funcionam pela API em planos pagos. Se a ElevenLabs recusar a fala, o Jarvis usa a voz do macOS e o motivo aparece no feed ("ElevenLabs recusou a fala").

## Outras variáveis

As outras variáveis (modelo, voz, Whisper, pastas de dados) estão explicadas, uma por linha, no [`.env.example`](../.env.example).

## Notícias

Edite [`sources.json`](../sources.json). Use `"modo": "rss"` com `"rss": "<url do feed>"` quando o site tiver feed. Sem feed, use `"modo": "html"` com um `padrao_link` que case com o caminho dos artigos. O Jarvis busca as fontes a cada 20 minutos, mostra as novas manchetes no feed e responde "quais as notícias do Data Hackers?".

**Resumo diário.** Todo dia às 08:00 (`JARVIS_RESUMO_HORA`; vazio desliga; se o Mac estava desligado, sai ao ligar) o Jarvis fala as três notícias mais relevantes das últimas 36 horas, uma frase própria para cada, e põe os links no feed. A relevância vem de `JARVIS_NOTICIAS_TEMAS` (lista separada por vírgulas) e do glossário de dados. Repetidas entre fontes saem; se a resposta repetir um trecho de oito palavras ou mais da fonte, o feed avisa. O botão "Resumo de notícias" faz o mesmo a qualquer hora, e o "Briefing Executivo" junta agenda, as três notícias e os arquivos de dados novos.

## Dados (CSV)

"Jarvis, abre o arquivo vendas de outubro" procura um `.csv` ou `.tsv` em Downloads, Documentos e Mesa (até três níveis abaixo; troque com `JARVIS_PASTAS_DADOS`, pastas separadas por `:`). O arquivo pode estar no padrão do Excel brasileiro (cp1252, `;`, vírgula decimal, `R$ 1.234,56`, datas dd/mm/aaaa). Depois pergunte: "qual UF mais fatura?", "e por mês?", "quanto seria com 12% a mais?".

- **Só agregados vão para o Claude.** Ele não lê o arquivo nem escreve SQL: pede métricas, agrupamentos e filtros, e o Jarvis monta a consulta. Grupos com menos de 5 linhas são omitidos (`JARVIS_K_ANONIMATO`). Colunas com cara de dado pessoal (CPF, nome, e-mail, telefone) só aceitam contagem. O `Read`/`Grep` do Claude não abre `.csv`, `.tsv`, `.xlsx`, `.xls` nem `.parquet`.
- **Todo número sai de uma ferramenta.** As contas vêm do DuckDB ou de uma calculadora; um número da resposta que não aparece em nenhum resultado vira o aviso "Número sem origem nos dados" no feed.
- O arquivo original nunca é alterado; a leitura acontece numa conexão do DuckDB sem acesso a outros arquivos nem à rede.
- **Painel "Dados".** Abre sozinho com o arquivo e cada resultado: tabela, gráfico (linha para meses e anos, barras para categorias) e os cinco últimos resultados. Arraste um CSV para o painel (ou use o botão de envio) e o Jarvis o abre; o arquivo fica em `data/arquivos` (limite em `JARVIS_UPLOAD_MAX_MB`).
- **Número sem origem não é falado.** Uma frase com número que não saiu das ferramentas é trocada por "Esse número não está confirmado nos dados" e marcada na conversa.
- **Também:** "o que mudou no arquivo de outubro?" compara versões (linhas iguais, novas e removidas, colunas, totais, categorias); "anota que UF vazia conta como Não informada" guarda a decisão, que volta quando o arquivo é reaberto; "NPS é promotores menos detratores" entra no glossário, que ajuda o Whisper a ouvir o termo; "isso se sustenta?" revisa o último resultado (tamanho da base, participação × risco, sazonalidade, causa).

### Python isolado e monitores

- **Estatística e gráficos.** "A diferença entre loja e e-commerce é significativa?", "faz uma regressão", "mostra a distribuição": o Claude escreve Python (pandas, numpy, scipy, matplotlib) que roda no sandbox do macOS (Seatbelt), sem rede, sem ler outros arquivos e sem executar programas, com limites de 30 s de CPU, 60 s e 1,5 GB (`JARVIS_PY_CPU_S`, `JARVIS_PY_PRAZO_S`, `JARVIS_PY_MEM_MB`). O código vê o arquivo inteiro, mas ao Claude só volta o que passa por `resultado()`: textos só se forem colunas ou categorias com 5+ linhas, tabelas só com a coluna `n` (grupos com menos de 5 saem), listas soltas até 20 itens. `print` e mensagens de erro com conteúdo de célula ficam no Mac. Os gráficos aparecem no painel e não vão para o Claude.
- **Monitores de KPI.** "Me avisa se o faturamento diário de SP cair mais de 10% contra a média dos 7 dias anteriores." O Jarvis confere de hora em hora (`JARVIS_KPI_INTERVALO_MIN`), sempre na versão mais recente do arquivo, e fala o alerta uma vez por período, sem passar pelo Claude. O dia ou mês em curso fica de fora para não alarmar à toa. Os monitores aparecem no painel "Dados".

### Análise profunda (plugin analise-dados)

"Jarvis, faz uma análise profunda do arquivo vendas de setembro" (ou "...da pasta projeto churn") abre uma sessão separada do Claude com o plugin [analise-dados](https://github.com/fernandofigueiredo-data/analise-dados-plugin): ela prepara o projeto, sobe o Jupyter, abre o notebook no navegador (`JARVIS_ABRIR_NOTEBOOK=0` desliga), pergunta a pergunta de negócio e conduz a análise célula a célula, com validação e revisão crítica. Um arquivo vira um projeto novo em `~/Documents/Análises Jarvis/<nome>` (`JARVIS_PASTA_ANALISES`) com uma cópia em `dados/`; uma pasta escolhida vira o próprio projeto (o plugin cria `.venv`, `dados/`, `saidas/` e `.claude/` nela). Enquanto o modo está aberto, o que você diz vai para a análise; só as duas primeiras frases de cada resposta são faladas. "Sai do modo profundo" encerra e desliga o Jupyter.

- **Aqui as linhas do arquivo vão para o Claude** (o resultado de cada célula volta para ele): exceção autorizada à regra dos agregados, só para a pasta ou o arquivo que você escolheu.
- A sessão tem política própria: Jupyter, skills e subagentes do plugin liberados; terminal só para os scripts do plugin; escrita só dentro do projeto e nunca em `dados/`; sem internet. As regras do projeto do plugin (não ler o `.env`, não editar `dados/`) valem.
- Requer o plugin instalado no Claude Code (`claude plugin marketplace add fernandofigueiredo-data/analise-dados-plugin` e depois `claude plugin install analise-dados@analise-dados`; o `/instalar` oferece isso) ou `JARVIS_PLUGIN_ANALISE` apontando para ele.

## Apps

Edite [`apps.json`](../apps.json): `"chave": "Nome do App"`. Para nomes que o Whisper erra, use a forma longa com `heard_as`.
