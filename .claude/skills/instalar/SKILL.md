---
name: instalar
description: Instala e configura o Jarvis neste Mac, do zero até o ícone no Dock. Confere os pré-requisitos, pergunta nome, tratamento, cidade e preferências, grava o .env, compila o painel, roda os testes, testa o login do Claude, cria o Jarvis.app e guia as permissões do macOS. Use quando a pessoa pedir para instalar, configurar, preparar ou "fazer funcionar" o Jarvis, ou logo depois de clonar o repositório.
---

# Instalar o Jarvis

Você vai deixar o Jarvis funcionando no Mac de quem clonou este repositório. Siga os passos em ordem. Depois de cada passo, diga em uma linha o que ficou pronto. Se um passo falhar, pare, mostre o erro e a correção, e só siga quando ele passar.

Regras:
- Rode tudo a partir da raiz do repositório.
- Não use `sudo` e não instale nada no sistema (Homebrew, uv, Node) sem a pessoa aceitar. Mostre o comando e pergunte.
- Nunca leia arquivos de dados da pessoa (CSV, planilhas). Para testar, use `exemplos/vendas_exemplo.csv`, que é sintético.
- Não rode `uv run jarvis` sem argumentos no seu terminal: ele fica aberto até ser encerrado. A primeira execução acontece pelo ícone do Dock (passo 8).
- Faça as perguntas do passo 2 com a ferramenta de perguntas, em um bloco só, oferecendo os padrões como primeira opção.

## 1. Pré-requisitos

Confira tudo de uma vez e mostre uma tabela com ✅ e ❌:

| Item | Como conferir | Se faltar |
|---|---|---|
| macOS | `sw_vers -productVersion` | O Jarvis só roda no macOS. Pare aqui. |
| uv | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` ou `brew install uv` |
| Node 20+ | `node --version` | `brew install node` ou o instalador de https://nodejs.org |
| Claude Code logado | `claude --version` (o login é testado no passo 5) | Rode `claude` num terminal e faça o `/login` |
| Voz Luciana (pt-BR) | `say -v '?' \| grep -i luciana` | Ajustes do Sistema › Acessibilidade › Conteúdo Falado › Voz do Sistema › Gerenciar Vozes › Português (Brasil) › Luciana. Sem ela, o Jarvis fala com a voz padrão. |
| Memória | `sysctl -n hw.memsize` | Só informa a escolha do Whisper no passo 2 |
| Command Line Tools do Xcode | `xcode-select -p && which swiftc` | `xcode-select --install`. Sem elas, o Local do painel vem só do IP (aproximado). |

## 2. Perguntas e `.env`

Se já existir um `.env`, mostre os valores atuais de `JARVIS_NOME`, `JARVIS_TRATAMENTO`, `JARVIS_LOCATION`, `JARVIS_WHISPER_MODEL` e `JARVIS_NOTICIAS_TEMAS`. Pergunte se a pessoa quer mantê-los. Se mantiver, pule para o passo 3.

Pergunte:
1. **Nome**, que entra no prompt ("assistente pessoal de voz da Ana"). Pode ficar vazio.
2. **Tratamento**: senhor (padrão, no estilo do JARVIS dos filmes), senhora ou nenhum.
3. **Cidade do clima**: vazio detecta pela localização do Mac (pede permissão no passo 8) e, sem ela, pelo IP. Se a pessoa não quiser que o Jarvis use a localização, grave `JARVIS_LOCAL_PRECISO=0`.
4. **Modelo do Whisper**: `small` é o padrão (~460 MB). Com 16 GB de RAM ou mais, ofereça `medium`, que erra menos e é mais lento. Com 8 GB, recomende `small`.
5. **Temas de notícias** que sobem no resumo diário: ofereça o padrão do `.env.example`.
6. **Pastas de dados**: o padrão é Downloads, Documentos e Mesa.

Copie o `.env.example` para `.env`, se ele ainda não existir, e preencha só as linhas respondidas. Mantenha o resto do arquivo. Mostre o trecho que mudou.

## 3. Dependências e painel

```bash
uv sync
cd ui && npm ci && npm run build && cd ..
```

## 4. Testes

```bash
uv run pytest -q --ignore=tests/e2e
```

Todos devem passar. Se algum falhar, mostre o nome do teste e as últimas linhas do erro antes de seguir.

## 5. Login do Claude, sem microfone

```bash
uv run jarvis --text "diga apenas: tudo pronto"
```

Tem que voltar uma frase curta. Se vier erro de login ou de modelo, peça para a pessoa rodar `claude` num terminal, fazer o `/login` e repetir. Esse turno usa um pouco do limite da assinatura do Claude.

## 6. Plugin de análise profunda (opcional)

Explique em uma frase: o plugin `analise-dados` conduz análises completas em Jupyter quando a pessoa pede "faz uma análise profunda do arquivo X". Pergunte se ela quer instalar. Se sim:

```bash
claude plugin marketplace add fernandofigueiredo-data/analise-dados-plugin
claude plugin install analise-dados@analise-dados
```

## 7. Ícone no Dock

```bash
scripts/criar_app.sh
```

O script cria `~/Applications/Jarvis.app`, que abre o Jarvis no Terminal a partir desta pasta. Diga à pessoa:
- abra o Finder, aperte ⌘⇧H, entre em **Aplicativos** e arraste o **Jarvis** para o Dock;
- se ela mover a pasta do repositório depois, precisa rodar o script de novo.

## 8. Permissões e primeira execução

O Jarvis roda dentro do Terminal, então as permissões são do **Terminal**. Explique as três e abra cada painel:

| Permissão | Para quê | Abrir |
|---|---|---|
| Microfone | ouvir "Ei Jarvis" | `open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"` |
| Monitoramento de Entrada | segurar o Option direito para falar | `open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"` |
| Automação | abrir e fechar apps, modo escuro | o macOS pergunta sozinho na primeira ação; aceitar |

O Microfone também é pedido sozinho na primeira vez. Depois de liberar o Monitoramento de Entrada, é preciso fechar e reabrir o Terminal.

**Localização** (pule se `JARVIS_LOCATION` estiver preenchida ou `JARVIS_LOCAL_PRECISO=0`): ela é do app auxiliar "Jarvis Localização", não do Terminal. Peça a permissão agora, para ela não surgir de surpresa na primeira abertura:

```bash
uv run python -c "from jarvis.mac import location; print(location.current(wait=120))"
```

Avise antes: o macOS vai mostrar "Jarvis Localização gostaria de usar a sua localização"; clique em Permitir. Volta `{'lat': ..., 'lon': ..., 'acc': ...}` quando deu certo e `None` se foi negado ou não houve resposta (o Local fica pelo IP, com "(aprox.)"; dá para liberar depois em Ajustes › Privacidade e Segurança › Serviços de Localização). Não mostre as coordenadas na conversa: diga só se deu certo.

Peça para a pessoa clicar no Jarvis do Dock. Na primeira vez, o Whisper baixa o modelo, e isso leva de um a dois minutos. Quando a janela abrir, sugira três testes:
- "Bom dia, Jarvis." (saudação com a agenda de hoje)
- "Ei Jarvis, abre o Safari."
- "Ei Jarvis, quais as notícias de hoje?"
- Arrastar `exemplos/vendas_exemplo.csv` para o painel e perguntar "qual UF mais fatura?".

## 9. Resumo final

Termine com:
- o que foi configurado;
- o que ficou pendente (voz Luciana, plugin, permissões não confirmadas, localização);
- os comandos do dia a dia: o ícone do Dock, `uv run jarvis --mode off` para usar sem microfone e `/diagnostico` se algo parar de funcionar.
