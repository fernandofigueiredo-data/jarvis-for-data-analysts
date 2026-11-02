# Inventário de testes — J.A.R.V.I.S. Command Center

Checklist de tudo o que o sistema oferece, montado a partir do código (`src/jarvis`, `ui/src`) e da interface rodando
(`uv run jarvis --no-window --mode off`, painel em http://127.0.0.1:8787). Cada item tem um ID usado no
executor automático (`tests/e2e/inventario_ui.py`) e no `RELATORIO_TESTES.md`, onde estão os resultados antes e
depois das correções.

Tipos: **C** = controle clicável/digitável · **E** = exibição de dados · **F** = fluxo de ponta a ponta · **S** = servidor.

## Cabeçalho

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| CAB-01 | E | Indicador "Status do sistema" | Abrir com o daemon ligado | Mostra o estado real (ÓTIMO/ATENÇÃO/DEGRADADO); OFFLINE só sem daemon |
| CAB-02 | E | Data e relógio | Observar por 2 s | Data por extenso e hora avançando a cada segundo |
| CAB-03 | C/F | Campo "Pesquisar ou comandar…" | Digitar pergunta + Enter | Envia `say` ao daemon e a resposta fica legível na tela |
| CAB-04 | C | Dica de atalho ⌘K | Pressionar ⌘K / Ctrl+K | Foca o campo de comando |
| CAB-05 | C | Botão "Layout" | Clicar | Abre/alterna algo ou não existe |
| CAB-06 | C | Botão "Notificações" (ponto vermelho) | Clicar | Mostra notificações; ponto só quando houver novidade |
| CAB-07 | C | Botão "Configurações" | Clicar | Mostra as configurações em uso |
| CAB-08 | E | Selo "Operador · Comandante" | Observar | Elemento estático, sem aparência de botão |
| CAB-09 | C | Botão "Menu de seções" (só no celular; criado na fase de interface) | Abrir e escolher "Notícias" | Abre a navegação, fecha ao escolher e leva ao cartão |

## Barra lateral

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| LAT-01 | C | Navegação "Command Center" | Clicar | Mostra o painel completo |
| LAT-02 | C | Navegação "AI Core" | Clicar | Leva ao conteúdo correspondente |
| LAT-03 | C | Navegação "Agentes" | Clicar | Leva ao conteúdo correspondente |
| LAT-04 | C | Navegação "Tarefas" | Clicar | Leva ao conteúdo correspondente |
| LAT-05 | C | Navegação "Calendário" | Clicar | Leva ao conteúdo correspondente |
| LAT-06 | C | Navegação "Memória" | Clicar | Leva ao conteúdo correspondente |
| LAT-07 | C | Navegação "Conversas" | Clicar | Leva ao histórico de conversas |
| LAT-08 | C | Navegação "Base de Conhecimento" | Clicar | Leva ao conteúdo correspondente |
| LAT-09 | C | Navegação "Ferramentas & Skills" | Clicar | Leva ao conteúdo correspondente |
| LAT-10 | C | Navegação "Workflows" | Clicar | Leva ao conteúdo correspondente |
| LAT-11 | C | Navegação "Notícias" | Clicar | Leva às notícias |
| LAT-12 | E | Contadores da navegação (3 / 12 / 18) | Comparar com o daemon | Números reais ou nenhum número |
| LAT-13 | E | "Status de voz" (onda + fase) | Fazer uma pergunta | Acompanha as fases (pensando, falando, em espera) |
| LAT-14 | C | Microfone — clique rápido | Clicar uma vez | Faz o que o rótulo promete ("Toque para falar") |
| LAT-15 | C | Microfone — segurar | Segurar 1,2 s e soltar | Envia `ptt` down/up; sem microfone, avisa |
| LAT-16 | C | Microfone — teclado | Tab até ele, segurar Espaço | Mesmo efeito de segurar o mouse |
| LAT-17 | C | "Modo Foco" | Clicar duas vezes | Esconde/mostra os painéis secundários |

## Painéis centrais

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| PAI-01 | E | Visão geral do AI Core (6 componentes) | Abrir | Status vindo do daemon (core, memória, voz, agentes, LLMs, sistema) |
| PAI-02 | E | Globo 3D (WebGL) | Abrir | Renderiza sem erro de console; chip com a fase atual |
| PAI-03 | E | Legenda da fala no globo | Fazer uma pergunta | Mostra a pergunta e a resposta |
| PAI-04 | C | Itens do feed com link (notícias) | Clicar numa notícia | Abre o artigo em nova aba |
| PAI-05 | C | "Ver toda a inteligência" / "Mostrar menos" | Clicar duas vezes | Expande e recolhe a lista |
| PAI-06 | E | Agentes ativos | Pergunta que usa ferramenta | Agente correspondente fica "Ativo" |
| PAI-07 | E | Linha do tempo da missão | Abrir | Compromissos de hoje do Calendário (ou vazio real) |
| PAI-08 | C/F | Comando rápido "Iniciar tarefa" | Clicar | Jarvis pergunta a tarefa e conclui o fluxo |
| PAI-09 | C/F | Comando rápido "Abrir calendário" | Clicar | Jarvis lê a agenda do dia em tempo de conversa |
| PAI-10 | C/F | Comando rápido "Iniciar conversa por voz" | Clicar | Arma a escuta e volta ao normal; sem microfone, avisa |
| PAI-11 | C/F | Comando rápido "Resumo de notícias" | Clicar | Jarvis resume as manchetes |
| PAI-12 | E | Monitor do sistema (CPU, RAM, Disco) | Observar 4 s | Valores reais atualizando |
| PAI-13 | E | Insights de memória | Fazer perguntas | Contadores vindos do banco |
| PAI-14 | E | Status dos LLMs | Abrir | Provedores com estado real |

## Rodapé

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| ROD-01 | E | Local | Abrir | Cidade (config ou IP) |
| ROD-02 | E | Clima | Abrir | Temperatura e condição legíveis |
| ROD-03 | E | Rede | Abrir | Qualidade da conexão |
| ROD-04 | C | "Fale com o Jarvis" — abrir campo | Clicar | Vira campo de texto com foco |
| ROD-05 | C/F | "Fale com o Jarvis" — Enter | Digitar pergunta + Enter | Resposta aparece e continua legível depois da fala |
| ROD-06 | C | Botão enviar (seta) | Digitar + clicar na seta | Envia a pergunta |
| ROD-07 | C | Esc no campo | Digitar + Esc | Cancela e volta ao rótulo |
| ROD-08 | C/F | "Briefing Executivo" | Clicar | Jarvis faz o briefing (agenda, timers, notícias) |
| ROD-09 | E | Convite do "Fale com o Jarvis" em espera | Abrir com a voz desligada | Não diz "Estou ouvindo" quando o microfone não está ligado |

## Painel "Conversa" (criado na correção do JAR-01)

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| CNV-01 | C | Botão "Fechar conversa" e tecla Esc | Abrir pela navegação e fechar de cada jeito | Fecha nos dois casos |
| CNV-02 | F | Fechar enquanto a resposta chega | Perguntar e fechar logo em seguida | A resposta termina e o painel continua fechado |

## Jarvis (conversa) — caso à parte

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| JAR-01 | F | Pergunta geral | "qual a capital da Austrália?" | Resposta correta, visível e consultável depois |
| JAR-02 | F | Rota rápida | "que horas são?" | Resposta local imediata |
| JAR-03 | F | Pergunta com ferramenta | "quais as notícias do Data Hackers?" | Usa `news_latest` e resume |
| JAR-04 | F | Interrupção (barge-in) | 2ª pergunta durante a 1ª | A 2ª é respondida |
| JAR-05 | F | Falha do modelo/API | Daemon com modelo inválido | Usuário recebe uma mensagem de erro, não silêncio |
| JAR-06 | F | Histórico | Consultar conversas | Perguntas e respostas acessíveis |
| JAR-07 | F | Voz sem microfone (áudio sintético) | Whisper + "Ei Jarvis" | Transcreve, reconhece o nome e roteia |

## Servidor e API

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| API-01 | S | `GET /api/health` | Requisição | 200 com estado do cérebro, voz, TTS e notícias |
| API-02 | S | `GET /api/conversations` (e `?q=`) | Requisição | 200 com turnos |
| API-03 | S | `GET /api/news` (e `?source=`) | Requisição | 200 com manchetes |
| API-04 | S | WebSocket com origem estranha | Conectar | Recusado (403) |
| API-05 | S | Snapshot inicial do WebSocket | Conectar | Estado completo na 1ª mensagem |
| API-06 | S | Mensagem malformada no WebSocket | Enviar texto não-JSON | Ignorada sem derrubar a conexão |
| API-07 | S | Comando desconhecido | `command` com id inválido | Ignorado sem erro |
| API-08 | S | Arquivos estáticos | index, JS, CSS, favicon | 200 |

## Conexão e modo demonstração

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| CON-01 | F | Painel sem daemon | Abrir com o daemon parado | OFFLINE e aviso claro de demonstração |
| CON-02 | F | Reconexão | Subir o daemon com o painel aberto | Reconecta sozinho e troca os dados de demonstração pelos reais |

## Responsividade e acessibilidade

| ID | Tipo | Item | Ação | Resultado esperado |
|---|---|---|---|---|
| RES-01 | E | Desktop 1440×900 | Abrir | Sem rolagem horizontal nem sobreposição |
| RES-02 | E | Janela nativa 1280×760 e mínima 900×600 | Abrir | Sem rolagem horizontal; tudo legível |
| RES-03 | E | Tablet 768×1024 | Abrir | Sem rolagem horizontal |
| RES-04 | E | Celular 375×812 | Abrir | Sem rolagem horizontal; microfone, Modo Foco e navegação acessíveis |
| ACE-01 | C | Navegação por teclado | Tab por toda a página | Todos os controles alcançáveis e com foco visível |
| ACE-02 | E | Rótulos acessíveis | Auditoria (axe-core) | Sem botões/campos sem nome |
| ACE-03 | E | Contraste | Auditoria (axe-core) | Texto com contraste mínimo AA |
| ACE-04 | E | Movimento reduzido | `prefers-reduced-motion` | Animações contínuas desligadas |
