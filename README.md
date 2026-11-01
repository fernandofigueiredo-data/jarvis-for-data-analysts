# J.A.R.V.I.S.

Assistente pessoal de voz para o Mac, em português. Diga **"Ei Jarvis"** (ou segure o **Option direito**) e fale. Comandos simples do Mac são resolvidos na hora, sem IA. O resto vai para o Claude, que usa o seu login do Claude Code e não precisa de chave de API. Um painel "Command Center" mostra tudo em tempo real.

## Rodar

Pré-requisitos: [uv](https://docs.astral.sh/uv/), Node 20+ e o Claude Code instalado e logado (`claude`).

```bash
uv sync
cd ui && npm install && npm run build && cd ..
uv run jarvis
```

Na primeira vez:

1. O Whisper baixa o modelo `small`, uns 460 MB.
2. O macOS pede **Microfone**. Aceite.
3. Para o push-to-talk (Option direito), adicione o Terminal (ou o app em que você roda o Jarvis) em **Ajustes do Sistema › Privacidade e Segurança › Monitoramento de Entrada**. Depois feche e reabra o Terminal.
4. Na primeira ação em um app (fechar app, modo escuro), o macOS pede **Automação**. Aceite.

### Opções

| Comando | O que faz |
|---|---|
| `uv run jarvis` | Janela nativa + sempre ouvindo "Ei Jarvis" |
| `uv run jarvis --mode ptt` | Só escuta enquanto você segura o Option direito |
| `uv run jarvis --mode off` | Sem microfone; conversa digitando no painel |
| `uv run jarvis --no-window` | Sem janela; painel em http://127.0.0.1:8787 |
| `uv run jarvis --text "abre o Chrome"` | Um turno pelo terminal (`--speak` para falar a resposta) |
| `uv run jarvis --writes` | Libera ações que mudam o mundo (terminal, escrever arquivos, enviar) |

Variáveis em `.env` (todas opcionais): `JARVIS_MODEL` (padrão `claude-sonnet-5-5`), `JARVIS_EFFORT` (`low`), `JARVIS_WHISPER_MODEL` (`small`), `JARVIS_VOICE` (`Luciana`), `JARVIS_LOCATION` (cidade do clima; sem ela, a cidade sai do IP) e `ELEVENLABS_API_KEY` (troca a voz do macOS pela ElevenLabs).

## Notícias

Edite [`sources.json`](sources.json). Use `"modo": "rss"` com `"rss": "<url do feed>"` quando o site tiver feed. Sem feed, use `"modo": "html"` com um `padrao_link` que case com o caminho dos artigos. O Jarvis busca as fontes a cada 20 minutos, mostra as novas manchetes no feed e responde "quais as notícias do Data Hackers?".

## Apps

Edite [`apps.json`](apps.json): `"chave": "Nome do App"`. Para nomes que o Whisper erra, use a forma longa com `heard_as`.

## Segurança

- Por padrão o Jarvis só **lê**: as ferramentas de terminal e escrita nem existem na sessão do Claude. Ações locais e reversíveis (abrir apps, volume, timers) sempre funcionam.
- `setting_sources=[]` impede que regras do seu `~/.claude/settings.json` passem por cima desse bloqueio.
- O servidor escuta só em `127.0.0.1`, e o WebSocket só aceita o próprio painel como origem.

## Como funciona

```
mic → VAD → Whisper (pt) → "Ei Jarvis"/Option → rota rápida (regex) → AppleScript
                                              └→ Claude Agent SDK → ferramentas mac/jarvis → fala frase a frase
```

- `src/jarvis/app.py`: orquestrador (voz, turnos, barge-in, timers, eventos do painel)
- `src/jarvis/router.py`: rota rápida em português
- `src/jarvis/brain/`: sessão do Claude, persona, bloqueio de permissões e ferramentas in-process
- `src/jarvis/news.py`, `telemetry.py`, `agenda.py`, `memory.py`: dados do painel
- `ui/`: painel em React + Three.js

## Créditos

Ideias de dois projetos abertos:

- [adewaskar/jarvis](https://github.com/adewaskar/jarvis) (MIT): Claude Agent SDK como cérebro, bloqueio de ferramentas por verbo, persona curta, fala em streaming e barge-in.
- [henryklunaris/hey-jev](https://github.com/henryklunaris/hey-jev): VAD por energia, palavra de ativação no texto do Whisper, ações em AppleScript, timers e Keychain. As ideias foram reimplementadas, sem copiar o código.

O visual do painel se inspira no "Command Center" de [jarvis.institute](https://jarvis.institute/).
