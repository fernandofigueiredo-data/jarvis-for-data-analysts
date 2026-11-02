# Relatório de testes — J.A.R.V.I.S. Command Center

Data: 1º de novembro de 2026 · Escopo: daemon Python (`src/jarvis`) e painel React (`ui/`) · Inventário: [`INVENTARIO_TESTES.md`](INVENTARIO_TESTES.md)

## Resumo

Testei o sistema de ponta a ponta (daemon Python, WebSocket e painel React) com um inventário de 76 itens executado no Playwright, no Chromium e, nos grupos de interface, também no WebKit, que é o motor da janela nativa; somei cenários de reinício do daemon, falha da API e voz com áudio sintético. O Jarvis respondia, mas a resposta só ficava na tela enquanto a voz falava (cerca de 3 s, numa linha cortada), e os erros da API (modelo, login, limite de uso) eram descartados sem fala, texto ou aviso: as duas causas foram reproduzidas e corrigidas. Antes, 36 dos 73 itens medidos falhavam (4 bloqueantes, 28 funcionais, 4 cosméticos), entre eles 15 controles sem ação, a agenda que estourava o prazo de 20 s e dados de demonstração exibidos como reais. Depois das correções e de cinco lotes de melhorias de interface (painel de conversa, teclado, celular, contraste, movimento reduzido), os 76 itens passam, sem regressão entre os passos 6 e 8, e os 57 testes unitários passam. Ficaram sem teste o microfone e o alto-falante reais, a tecla Option, a janela nativa propriamente dita e as ações que alteram o Mac ou exigem `--writes`.

## Tabela de itens testados

Colunas: **Antes** = código original; **Após correções** = passo 6 (defeitos funcionais corrigidos); **Final** = passo 8 (com as melhorias de interface). "—" indica que o item não foi medido naquela rodada (o motivo está na observação). A severidade só aparece quando houve falha.

| ID | Item | Antes | Após correções | Final | Severidade | Observação |
|---|---|---|---|---|---|---|
| CAB-01 | Indicador "Status do sistema" | Passou | Passou | Passou |  | STATUS DO SISTEMA ÓTIMO |
| CAB-02 | Data e relógio | Passou | Passou | Passou |  | 20:33:44 -> 20:33:46 |
| CAB-03 | Campo "Pesquisar ou comandar…" | **Falhou** | Passou | Passou | Bloqueante | antes: resposta em 1,5 s, invisível 3 s depois da fala; depois: fica na Conversa |
| CAB-04 | Dica de atalho ⌘K | **Falhou** | Passou | Passou | Funcional | antes: dica ⌘K sem atalho; depois: ⌘K/Ctrl+K focam o campo |
| CAB-05 | Botão "Layout" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: alterna o Modo Foco |
| CAB-06 | Botão "Notificações" (ponto vermelho) | **Falhou** | Passou | Passou | Funcional | antes: sem ação e ponto vermelho fixo; depois: lista alertas, ponto só com novidade |
| CAB-07 | Botão "Configurações" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: mostra conexão, voz, cérebro, modelos |
| CAB-08 | Selo "Operador · Comandante" | Passou | Passou | Passou |  | elemento estático (não parece nem age como botão) |
| CAB-09 | Botão "Menu de seções" (só no celular; criado na fase de interface) | não existia | — (teste criado depois) | Passou |  | criado na fase de interface; abre as seções e leva ao cartão |
| LAT-01 | Navegação "Command Center" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: volta ao painel completo (sai do Modo Foco) |
| LAT-02 | Navegação "AI Core" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: rola até o cartão, destaca e foca |
| LAT-03 | Navegação "Agentes" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: rola até o cartão, destaca e foca |
| LAT-04 | Navegação "Tarefas" | **Falhou** | Passou | Passou | Funcional | removido: o daemon não tem tarefas para mostrar |
| LAT-05 | Navegação "Calendário" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: rola até a linha do tempo, destaca e foca |
| LAT-06 | Navegação "Memória" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: rola até o cartão, destaca e foca |
| LAT-07 | Navegação "Conversas" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: abre a Conversa com o histórico |
| LAT-08 | Navegação "Base de Conhecimento" | **Falhou** | Passou | Passou | Funcional | removido: sem funcionalidade no daemon |
| LAT-09 | Navegação "Ferramentas & Skills" | **Falhou** | Passou | Passou | Funcional | removido: sem funcionalidade no daemon |
| LAT-10 | Navegação "Workflows" | **Falhou** | Passou | Passou | Funcional | removido: sem funcionalidade no daemon |
| LAT-11 | Navegação "Notícias" | **Falhou** | Passou | Passou | Funcional | antes: sem ação; depois: rola até o feed, destaca e foca |
| LAT-12 | Contadores da navegação (3 / 12 / 18) | **Falhou** | Passou | Passou | Cosmético | antes: 3/12/18 inventados (turnos reais: 48); depois: sem contadores |
| LAT-13 | "Status de voz" (onda + fase) | Passou | Passou | Passou |  | fases vistas: ['Em espera', 'Falando', 'Pensando'] |
| LAT-14 | Microfone — clique rápido | **Falhou** | Passou | Passou | Funcional | antes: clique enviava ptt e nada acontecia; depois: aviso 'Voz desligada' / dica de segurar |
| LAT-15 | Microfone — segurar | **Falhou** | Passou | Passou | Funcional | antes: nenhum retorno sem microfone; depois: aviso no feed |
| LAT-16 | Microfone — teclado | Passou | Passou | Passou |  | enviou ['{"type":"ptt","down":true}', '{"type":"ptt","down":false}'] |
| LAT-17 | "Modo Foco" | Passou | Passou | Passou |  | títulos visíveis: 8 -> 1 -> 8 |
| PAI-01 | Visão geral do AI Core (6 componentes) | Passou | Passou | Passou |  | VISÃO GERAL DO AI CORE AI Core Ativo Memória 0 memórias Voz Desligada Agentes 0 ativos LLMs 1 c |
| PAI-02 | Globo 3D (WebGL) | Passou | Passou | Passou |  | canvas=True; chip='JARVIS'; erros=0 |
| PAI-03 | Legenda da fala no globo | Passou | Passou | Passou |  | resposta='Laranja.'; legendas exibidas=['Você: diga apenas a palavra laranja', 'Jarvis: Laranja |
| PAI-04 | Itens do feed com link (notícias) | Passou | Passou | Passou |  | a nova aba abre (navegação externa bloqueada de propósito no teste) |
| PAI-05 | "Ver toda a inteligência" / "Mostrar menos" | Passou | Passou | Passou |  | itens: 5 -> 22 -> 5 |
| PAI-06 | Agentes ativos | Passou | Passou | Passou |  | agente ativo visto: Tarefas |
| PAI-07 | Linha do tempo da missão | **Falhou** | Passou | Passou | Funcional | antes: Calendário leva 50 s e o app desistia em 20 s |
| PAI-08 | Comando rápido "Iniciar tarefa" | Passou | Passou | Passou |  | 1ª resposta em 1.6s: 'Qual é a tarefa, senhor?' / depois de responder 'comprar pão amanhã': 'In |
| PAI-09 | Comando rápido "Abrir calendário" | **Falhou** | Passou | Passou | Funcional | antes: 22,4 s; depois: ~3 s |
| PAI-10 | Comando rápido "Iniciar conversa por voz" | **Falhou** | Passou | Passou | Funcional | antes: fase presa em 'Ouvindo'; depois: volta à espera e avisa |
| PAI-11 | Comando rápido "Resumo de notícias" | Passou | Passou | Passou |  | 1ª resposta em 3.0s: 'Na Educadados, o destaque é se a certificação PL-300 vale a pena. No Data |
| PAI-12 | Monitor do sistema (CPU, RAM, Disco) | Passou | Passou | Passou |  | MONITOR DO SISTEMA 92% CPU 77% RAM 19% DISCO -> MONITOR DO SISTEMA 93% CPU 78% RAM 19% DISCO |
| PAI-13 | Insights de memória | Passou | Passou | Passou |  | INSIGHTS DE MEMÓRIA 0 Memórias 152 Turnos de sessão 89 Chamadas de ferramenta |
| PAI-14 | Status dos LLMs | Passou | Passou | Passou |  | STATUS DOS LLMS 1 conectado Claude Code Conectado OpenAI Não vinculado Gemini Não vinculado Gro |
| ROD-01 | Local | Passou | Passou | Passou |  | cidade detectada pelo IP (nome omitido aqui) |
| ROD-02 | Clima | **Falhou** | **Falhou** | Passou | Cosmético | antes: 'Quase limpo' cortado; depois: cabe até 'Parcialmente nublado' |
| ROD-03 | Rede | Passou | Passou | Passou |  | Excelente |
| ROD-04 | "Fale com o Jarvis" — abrir campo | Passou | Passou | Passou |  | campo de texto focado |
| ROD-05 | "Fale com o Jarvis" — Enter | **Falhou** | Passou | Passou | Bloqueante | antes: invisível 3 s depois da fala; depois: fica na Conversa |
| ROD-06 | Botão enviar (seta) | Passou | Passou | Passou |  | enviou ['{"type":"say","text":"que horas são?"}'] |
| ROD-07 | Esc no campo | Passou | Passou | Passou |  | voltou ao rótulo=True; enviou=[] |
| ROD-08 | "Briefing Executivo" | **Falhou** | Passou | Passou | Funcional | antes: 23 s; depois: 3–6 s |
| ROD-09 | Convite do "Fale com o Jarvis" em espera | **Falhou** | Passou | Passou | Funcional | antes: 'Estou ouvindo…' com a voz desligada; depois: 'Clique para digitar' |
| CNV-01 | Botão "Fechar conversa" e tecla Esc | não existia | — (teste criado depois) | Passou |  | fecha no X e no Esc |
| CNV-02 | Fechar enquanto a resposta chega | não existia | — (teste criado depois) | Passou | Funcional (achado na fase de interface) | no passo 6 a conversa reabria a cada pedaço da resposta; corrigido na fase de interface |
| JAR-01 | Pergunta geral | **Falhou** | Passou | Passou | Bloqueante | resposta continua visível 3 s depois da fala (CAB-03/ROD-05) |
| JAR-02 | Rota rápida | Passou | — (medido só no passo 8) | Passou |  | 'São 20 e 22.' em 0.00s (rota local) |
| JAR-03 | Pergunta com ferramenta | Passou | — (medido só no passo 8) | Passou |  | ferramentas=['Usando jarvis · news_latest']; resposta em 4.9s: 'Senhor, as manchetes mais recen |
| JAR-04 | Interrupção (barge-in) | Passou | — (medido só no passo 8) | Passou | Funcional (achado no passo 8) | passo 8: a resposta cortada aparecia depois da 2ª pergunta; corrigido |
| JAR-05 | Falha do modelo/API | **Falhou** | Passou | Passou | Bloqueante | antes: silêncio total; depois: resposta de falha + motivo no feed |
| JAR-06 | Histórico | **Falhou** | — (medido só no passo 8) | Passou | Funcional | depois: a Conversa abre com as perguntas de sessões anteriores |
| JAR-07 | Voz sem microfone (áudio sintético) | Passou | — (medido só no passo 8) | Passou |  | 5 frases sintetizadas (say -o, voz Luciana) → Whisper small + palavra de ativação: {'f1': "rota |
| API-01 | `GET /api/health` | Passou | Passou | Passou |  | 200 {'ok': True, 'brain': True, 'voice': 'off', 'tts': 'macOS (Luciana)', 'news': {'Educadados' |
| API-02 | `GET /api/conversations` (e `?q=`) | Passou | Passou | Passou |  | 200: 50 turnos; ?q=Austr: 20 |
| API-03 | `GET /api/news` (e `?source=`) | Passou | Passou | Passou |  | 200: 24 manchetes; Data Hackers: 8 |
| API-04 | WebSocket com origem estranha | Passou | Passou | Passou |  | recusado: server rejected WebSocket connection: HTTP 403 |
| API-05 | Snapshot inicial do WebSocket | Passou | Passou | Passou |  | 1ª mensagem type=snapshot chaves=['agents', 'feed', 'health', 'llms', 'memory', 'state', 'telem |
| API-06 | Mensagem malformada no WebSocket | **Falhou** | Passou | Passou | Funcional | antes: conexão derrubada; depois: ignorada |
| API-07 | Comando desconhecido | **Falhou** | Passou | Passou | Funcional | antes: caía junto com o API-06; depois: ignorado |
| API-08 | Arquivos estáticos | Passou | Passou | Passou |  | / 200; {'favicon.svg': 200, 'assets/index-DVxN0DFg.js': 200, 'assets/index-DOFUGeJ0.css': 200} |
| CON-01 | Painel sem daemon | Passou | Passou | Passou |  | status='STATUS DO SISTEMA OFFLINE' após 4.4s; aviso de demonstração visível=True; dados de demo |
| CON-02 | Reconexão | **Falhou** | Passou | Passou | Funcional | antes: 3.380 memórias, 'São Paulo, BR', agenda e LLMs falsos após reconectar; depois: nada |
| RES-01 | Desktop 1440×900 | Passou | Passou | Passou |  | sem rolagem horizontal; todos os controles visíveis |
| RES-02 | Janela nativa 1280×760 e mínima 900×600 | Passou | Passou | Passou |  | sem rolagem horizontal nos dois tamanhos |
| RES-03 | Tablet 768×1024 | Passou | Passou | Passou |  | sem rolagem horizontal |
| RES-04 | Celular 375×812 | **Falhou** | **Falhou** | Passou | Funcional | antes: sem microfone, navegação e Modo Foco no celular; depois: menu Seções e microfone no rodapé |
| ACE-01 | Navegação por teclado | **Falhou** | **Falhou** | Passou | Funcional | antes: 'Fale com o Jarvis' inalcançável; microfone e busca sem foco visível |
| ACE-02 | Rótulos acessíveis | Passou | Passou | Passou |  | 0 violações |
| ACE-03 | Contraste | **Falhou** | **Falhou** | Passou | Cosmético | antes: 17 textos < 4,5:1 (pior 2,49:1); depois: 0 |
| ACE-04 | Movimento reduzido | **Falhou** | **Falhou** | Passou | Cosmético | antes: 2 SVGs animados e globo girando; depois: parados |

## Causa raiz: por que o Jarvis "não respondia"

O cérebro funciona. Fora do painel, `uv run jarvis --text "qual a capital da Austrália?"` respondeu "A capital da Austrália é Camberra, senhor." em 3,9 s, e pelo WebSocket a resposta chegou em 1,9 s. O banco real (`data/jarvis.db`, lido só para contagem, sem abrir conteúdo) tem 6 perguntas e 6 respostas do Claude, nenhuma pergunta sem resposta. O defeito estava no caminho entre a resposta e o usuário, em duas causas independentes:

**1. A interface apagava a resposta (bloqueante, reproduzido).** O painel só mostrava a resposta enquanto a fase não era "em espera": a legenda do globo usava `last && phase !== 'idle'` e o rodapé `phase !== 'idle' && last ? last.text : …`. Não havia histórico (o item "Conversas" não fazia nada). A resposta ficava na tela só durante a fala, numa linha cortada, e sumia. Medição com Playwright, perguntando pelo rodapé:

```
[ 0.26s] fase='PENSANDO' | rodapé='qual a capital da Austrália?'
[ 2.20s] fase='FALANDO'  | rodapé='Canberra, e não Sydney como muita gente supõe.'
[ 4.95s] fase='EM ESPERA' | rodapé='Estou ouvindo…'
[ 5.20s] fase='EM ESPERA' | globo=''            ← a resposta sumiu
```

Para quem digita (modo `--mode off`), está com o som baixo ou desvia o olhar por 3 segundos, o Jarvis parece não ter respondido. Três textos enganosos agravavam isso: o rodapé dizia "Estou ouvindo…" mesmo com o microfone desligado; o microfone dizia "Toque para falar", mas um toque gera menos de 0,3 s de áudio, que o daemon descarta em silêncio; e "Iniciar conversa por voz" deixava a fase presa em "Ouvindo…" nos modos sem escuta contínua.

**2. O cérebro descartava os erros da API (bloqueante, reproduzido).** `Brain.ask` só lia o texto que chega em *stream* (`StreamEvent`). Quando a chamada falha (modelo inexistente, login expirado, limite de uso, sobrecarga), o Claude Code não manda nada em *stream*: o texto do erro vem só numa `AssistantMessage` com `error` preenchido e num `ResultMessage` com `is_error=True`. A resposta ficava vazia, nada era falado nem exibido, e o log dizia apenas "erro no turno: success" (o campo impresso era o `subtype`). Reprodução com `JARVIS_MODEL=claude-modelo-inexistente`:

```
AssistantMessage error='model_not_found' textos=["There's an issue with the selected model (claude-modelo-inexistente)…"]
ResultMessage subtype=success is_error=True api_status=404 result="There's an issue with the selected model…"
texto vindo por stream (o que o Jarvis usa): ''
log do daemon:   erro no turno: success
WebSocket:       fases=['thinking', 'idle']; resposta=nenhuma; aviso no feed=nenhum
```

Depois da correção, o mesmo cenário produz `fases=['thinking','speaking','idle']`, a resposta "Infelizmente o cérebro não respondeu, senhor." (falada e exibida) e o aviso "O Claude não respondeu — There's an issue with the selected model…" no feed; o log passa a registrar `erro no turno: success 404 There's an issue…`.

**O que é comprovado e o que é hipótese.** Os dois mecanismos foram reproduzidos e corrigidos, com evidência acima. Qual deles o usuário viveu é hipótese: como o banco mostra respostas para todas as perguntas registradas, o mais provável é a causa 1. Uma falha de API nunca deixa registro, porque a pergunta sem resposta não é gravada e o daemon não grava log em arquivo (`config.LOG_FILE` existe, mas nada escreve nele).

## Correções feitas

Em ordem de severidade. Cada uma foi retestada logo depois (passo 6) e de novo no inventário final (passo 8).

| # | Severidade | Defeito | Correção | Arquivos |
|---|---|---|---|---|
| 1 | Bloqueante | Resposta sumia da tela ao fim da fala; sem histórico | Painel **Conversa** que fica aberto: mostra a resposta em *stream*, guarda a sessão e, quando o painel é servido pelo daemon, carrega as conversas anteriores de `/api/conversations`; leitor de tela anuncia só a resposta final (`aria-live`) | `ui/src/components/Conversation.tsx` (novo), `ui/src/store.ts`, `ui/src/ws.ts`, `ui/src/components/Footer.tsx`, `ui/src/components/Header.tsx` |
| 2 | Bloqueante | Erro da API engolido (silêncio total) | `BrainError` com o texto do Claude Code; o turno fala "Infelizmente o cérebro não respondeu", publica o motivo no feed e o log registra status HTTP e mensagem; `jarvis --text` imprime o motivo | `src/jarvis/brain/agent.py`, `src/jarvis/app.py`, `src/jarvis/cli.py` |
| 3 | Funcional | Após conectar, dados de demonstração (3.380 memórias, "São Paulo, BR", agenda e LLMs falsos) ficavam na tela como reais | O painel zera o estado ao conectar; o daemon publica CPU/RAM/disco e a saúde logo no início | `ui/src/store.ts`, `ui/src/ws.ts`, `src/jarvis/app.py` |
| 4 | Funcional | Agenda: a consulta ao Calendário leva ~50 s neste Mac (três calendários somam 44 s) e o app desistia em 20 s: linha do tempo sempre vazia, "Abrir calendário" em 22 s, Briefing em 23 s, telemetria parada 20 s a cada 5 min | Leitura numa thread própria com prazo de 150 s e cache; publica a linha do tempo a cada minuto e relê o Calendário a cada 10 min; a ferramenta responde do cache (só no 1º minuto após ligar espera até 15 s) | `src/jarvis/agenda.py`, `src/jarvis/brain/tools.py`, `src/jarvis/app.py` |
| 5 | Funcional | 15 controles sem ação: ⌘K, Layout, Notificações, Configurações e os 11 itens da navegação | ⌘K/Ctrl+K focam o campo; Layout alterna o Modo Foco; Notificações lista alertas e dicas do feed; Configurações mostra conexão, endereço, cérebro, voz e modelos e diz como mudar; 7 itens levam ao cartão correspondente (rolagem, destaque e foco) ou abrem a conversa; 4 itens foram **removidos** (Tarefas, Base de Conhecimento, Ferramentas & Skills, Workflows) porque o daemon não tem nada disso para mostrar | `ui/src/components/Header.tsx`, `ui/src/components/Sidebar.tsx`, `ui/src/components/Panels.tsx`, `ui/src/components/ui.tsx`, `ui/src/index.css` |
| 6 | Funcional | "Iniciar conversa por voz" deixava a fase presa em "Ouvindo…" nos modos `ptt` e `off` | Só arma a escuta no modo `wake`; nos outros, avisa no feed e volta à espera | `src/jarvis/app.py` |
| 7 | Funcional | Microfone do painel sem retorno: "Toque para falar" (um toque é descartado) e, sem microfone, nada acontecia | Rótulo "Segure para falar" (ou "Voz desligada (--mode off)"), dica ao soltar rápido demais e aviso do daemon quando não há microfone | `ui/src/components/Sidebar.tsx`, `src/jarvis/app.py` |
| 8 | Funcional | Rodapé dizia "Estou ouvindo…" com a voz desligada | Convite conforme o modo ("Diga “Ei Jarvis”…", "Segure o Option direito…", "Clique para digitar") | `ui/src/components/Footer.tsx` |
| 9 | Funcional | Status do Claude ficava em "Conectando"/"Não vinculado" para sempre depois de uma falha | Volta a "Ativo" no primeiro turno bem-sucedido; a saúde é publicada logo após conectar | `src/jarvis/app.py` |
| 10 | Funcional | Texto não-JSON no WebSocket derrubava a conexão (exceção não tratada) | Mensagem malformada é ignorada; `say` com texto não textual é recusado | `src/jarvis/server.py`, `src/jarvis/app.py` |
| 11 | Funcional | `npm run preview` (porta 4173, script do `package.json`) era recusado pelo WebSocket e o painel ficava preso na demonstração | Origens 4173 liberadas, como a 5173 do `npm run dev` | `src/jarvis/server.py` |
| 12 | Funcional (achado no passo 8) | Numa interrupção (2ª pergunta durante a 1ª), o fim da resposta cortada chegava depois da nova pergunta e aparecia embaixo dela na conversa | O turno novo espera o turno cortado fechar antes de publicar a pergunta (sem atraso: o cérebro já serializa os turnos) | `src/jarvis/app.py` |
| 13 | Cosmético | Contadores inventados na navegação (3, 12, 18) e ponto vermelho fixo no sino | Contadores removidos; o ponto só aparece com alerta não visto | `ui/src/components/Sidebar.tsx`, `ui/src/components/Header.tsx` |
| 14 | Cosmético | Comandos rápidos apareciam na conversa como fala do usuário com o prompt interno ("Faça meu briefing… use agenda_today, timer_list e news_latest…") | Conversa e histórico mostram o rótulo do botão; o Claude continua recebendo o prompt completo | `src/jarvis/app.py` |

Testes de regressão novos (57 testes no total, todos passando). Rodados contra o código original, os que cobrem as correções falham; só `test_foreign_origin_is_refused` passa nos dois, porque protege um comportamento que já existia:
`tests/test_brain_errors.py` (erro de API vira `BrainError`), `tests/test_agenda.py` (cache, "carregando" e prazo), `tests/test_server_ws.py` (mensagem malformada e origem estranha), `tests/test_app_turn.py` (aviso de falha e volta do status, botão de voz sem escuta, ordem da conversa numa interrupção — comprovado que este falha sem a correção).

## Melhorias de interface aplicadas

Feitas depois das correções, em cinco lotes, com o inventário de acessibilidade/responsividade rodado após cada lote e uma revisão visual a 1280×760 (tamanho da janela nativa) e 375×812. A identidade visual (vidro, ciano, HUD, globo) foi mantida; as mudanças são de usabilidade.

| Lote | Melhoria | Problema que resolve |
|---|---|---|
| 1 | Anel de foco visível para teclado em todos os controles (`:focus-visible`); campos dentro de cápsulas ganham o anel na cápsula inteira | Microfone (`outline-none`) e campo de busca não mostravam onde estava o foco |
| 1 | "Fale com o Jarvis" virou botão de verdade (Tab, Enter/Espaço); depois de enviar ou de Esc o foco volta para ele | A cápsula era uma `div` com clique: inalcançável pelo teclado |
| 1 | Notícias do feed viraram links (`<a target="_blank">`) | Itens eram `li` com `onClick`: sem teclado, sem semântica de link |
| 2 | No celular (< 768 px): menu "Seções" no cabeçalho e microfone ao lado do "Fale com o Jarvis" | A barra lateral some no celular e levava junto microfone, navegação e Modo Foco |
| 2 | Chip do clima quebra em até duas linhas e ganha mais largura; no celular ocupa uma linha própria | "Parcialmente nublado" virava "Parcial…" |
| 3 | Movimento reduzido: `MotionConfig reducedMotion="user"`, SVGs do reator e da constelação sem animação, globo 3D parado (a cor ainda acompanha a fase), rolagem e destaque sem transição | Com "Reduzir movimento" ligado no macOS, animações infinitas continuavam. Agora, com a preferência ligada, 0,00 % dos pixels do globo mudam em 1,5 s; sem ela, 9,36 % |
| 4 | Textos informativos de `slate-500` para `slate-400` e tamanho mínimo de 10 px (status, chips, rótulos) | 17 a 22 textos abaixo do contraste AA, o pior a 2,49:1 ("Não vinculado"); textos de 8,5–9,5 px |
| 4 | Estados: "Lendo a agenda do Calendário…" × "Nada agendado para hoje"; "Jarvis está pensando…/consultando uma ferramenta…" na conversa; dicas (`title`) nos comandos rápidos, inclusive que gravar tarefas exige `--writes` | Carregando era confundido com vazio; espera sem retorno; "Iniciar tarefa" terminava em recusa sem aviso prévio |
| 4 | Painéis flutuantes (conversa, notificações, configurações, menu) com fundo quase opaco e posicionamento num invólucro próprio | O texto dos cartões de trás atravessava o vidro; e como `.glass` (fora das camadas do Tailwind) força `position: relative`, o painel entrava no fluxo e espremia a grade a 1280×760 (achado na revisão visual) |
| 4 | Rótulo "EM ESPERA" dos agentes não quebra; a onda decorativa é que cede espaço | Com 10 px o rótulo quebrava em duas linhas a 1280 px |
| 4 | A conversa abre só quando começa uma pergunta nova | Ela reabria a cada pedaço da resposta, então não dava para fechá-la enquanto o Jarvis falava |
| 5 | `tabIndex={0}` explícito em botões e links | Na janela nativa (WebKit), o Tab do macOS com "Navegação pelo teclado" desligada (o padrão) só passava pelos 7 controles que já tinham `tabindex` (os do framer-motion); agora passa pelos 20, como no Chromium |

## Ferramentas

- **webapp-testing**: a skill carregou, mas veio só com o `SKILL.md`; os auxiliares `scripts/with_server.py` e `examples/` não existem na instalação. Segui o método da skill (Playwright em Python, reconhecimento antes da ação, console e rede capturados) com Playwright 1.64.1 direto e subi os servidores por conta própria. Playwright, Chromium headless, WebKit e axe-core 4.10.3 foram instalados num ambiente isolado na pasta temporária da sessão, sem tocar nas dependências do projeto.
- **ui-ux-pro-max**: disponível e usada na fase de melhorias (diretrizes de foco, movimento reduzido, toque, contraste e as específicas de React, Three.js e Tailwind).
- O axe-core não julga contraste de texto sobre gradiente/vidro (marca como "precisa revisão"), por isso deu "0 violações" mesmo com texto a 2,49:1. O executor mede o contraste por conta própria, compondo as camadas de fundo.

## Itens não testados e o motivo

- **Microfone real** (VAD, "Ei Jarvis" falado, segurar o botão com áudio de verdade): não liguei o microfone para não disparar o pedido de permissão do macOS durante o trabalho. Coberto em parte: o caminho Whisper → palavra de ativação → rota foi testado com áudio sintetizado (JAR-07) e o protocolo de *push-to-talk* com o daemon em `--mode off`.
- **Option direito** (CGEventTap): exige a permissão de Monitoramento de Entrada.
- **Janela nativa** (pywebview/WKWebView): não abri a janela. Testei no Chromium e repeti os grupos de interface no WebKit do Playwright, que é o motor da janela nativa. Não verifiquei se o pywebview abre os links das notícias (`target="_blank"`) no navegador do sistema.
- **Voz do macOS em alto-falante**: troquei o `say` e o `afplay` por *shims* silenciosos que registram o texto e esperam o tempo da fala (195 palavras/min), para não falar alto no Mac durante os testes; a voz Luciana existe e gera áudio (`say -o`).
- **ElevenLabs**: sem chave configurada.
- **Modo escrita** (`--writes`) e ações que mudam o Mac pela rota rápida (abrir/fechar apps, volume, mudo, modo escuro, bloquear tela, Todoist): não executei, por segurança; verifiquei o roteamento (testes unitários) e a recusa no modo leitura.
- **Agenda com compromissos reais**: o Calendário não tinha eventos hoje; a formatação com eventos está coberta por teste unitário.
- **Falha passageira da API seguida de sucesso**: coberta por teste unitário (`test_failed_turn_is_reported_and_status_recovers`); não há como provocá-la no serviço real.
- **Abrir a notícia no navegador**: a nova aba abre; a navegação externa foi bloqueada de propósito no teste.
- **Painel pelo `npm run dev` (5173) ou `npm run preview` (4173)**: testei o build servido pelo próprio daemon. Pelo servidor do Vite, por desenho, as conversas de sessões anteriores não carregam (a API não libera CORS); a liberação da origem 4173 foi verificada com conexões WebSocket de teste (`http://127.0.0.1:4173` e `http://localhost:4173` aceitas; origem estranha continua com 403), sem abrir o painel por esse servidor.

Os testes usaram um banco e um cache de teste (`JARVIS_DATA_DIR`/`JARVIS_CACHE_DIR` na pasta temporária). O `data/jarvis.db` real só foi aberto em modo leitura para contagens.

## Como repetir

```bash
JARVIS_DATA_DIR=/tmp/jarvis-teste uv run jarvis --no-window --mode off
uv run --with playwright --with websockets python tests/e2e/inventario_ui.py --out resultado.json
uv run --with playwright python tests/e2e/cenarios_daemon.py conexao --cmd "uv run jarvis --no-window --mode off"
uv run pytest
```

(Na primeira vez: `uv run --with playwright playwright install chromium`. O `--axe` aceita o caminho de um `axe.min.js` para os itens ACE-02/03. O roteiro de conexão usa o `JARVIS_DATA_DIR` do ambiente, então exporte-o antes para não gravar no banco real. Sem um `say` falso no `PATH`, o Jarvis fala as respostas no alto-falante durante os testes.)

## Sugestões fora do escopo

- **Log em arquivo**: gravar a saída do daemon em `~/Library/Logs/Jarvis.log` (a constante já existe). Sem isso, nenhuma falha passada pode ser diagnosticada.
- **Agenda via EventKit** (`pyobjc-framework-EventKit`) em vez de AppleScript: milissegundos em vez de ~50 s; exige a permissão "Calendários".
- **Modo do daemon no protocolo**: hoje a interface deduz o modo de voz pelo texto de `health.voice.detail`; um campo próprio (`mode`, `writes`) evitaria esse acoplamento e permitiria desabilitar "Iniciar tarefa" e "Iniciar conversa por voz" quando não se aplicam.
- **Timers no painel**: o daemon já emite `timers`, mas a interface ignora.
- **Feed**: separar "Usando ferramenta…" das notícias; numa conversa com várias ferramentas, as notícias saem das cinco primeiras linhas.
- **Privacidade do cérebro**: `Read`, `Glob` e `Grep` estão liberados com `cwd` na pasta pessoal; numa pergunta genérica ("o que é o Command Center do Jarvis?") ele vasculhou arquivos locais. Vale restringir o `cwd` ou essas ferramentas.
- **CSS em camadas**: mover `.glass`, `.tile`, `.icon-btn` para `@layer components`. Hoje vencem os utilitários do Tailwind, o que anula `rounded-none`, `border-y-0` e `border-l-0` da barra lateral; mudaria o visual, por isso não foi feito.
- **Interrupção**: marcar na conversa a resposta cortada (por exemplo com "…").
- **CI**: rodar `tests/e2e/inventario_ui.py` num job com o daemon em `--mode off`.
