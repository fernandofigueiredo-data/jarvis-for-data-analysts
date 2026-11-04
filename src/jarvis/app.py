"""O orquestrador: liga microfone, rota rápida, cérebro, fala, timers, notícias e o painel."""
import asyncio
import queue
import subprocess
import threading
import time
from pathlib import Path

import psutil
import uvicorn

from jarvis import agenda, config, dados, fillers, kpis, news, profundo, router, telemetry
from jarvis.audio.recorder import Recorder
from jarvis.audio.stt import stt
from jarvis.audio.tts import speaker
from jarvis.brain.agent import Brain
from jarvis.events import bus
from jarvis.mac.timers import Timer, timers
from jarvis.memory import memory
from jarvis.wake import WINDOW_S, is_stop, split_wake

CHIME = "/System/Library/Sounds/Tink.aiff"
UNCONFIRMED = "Esse número não está confirmado nos dados."
ALARM = "/System/Library/Sounds/Glass.aiff"
AGENTS = [("coding", "Agente de Código"), ("research", "Agente de Pesquisa"), ("memory", "Agente de Memória"),
          ("browser", "Agente de Navegação"), ("task", "Agente de Tarefas"), ("system", "Agente de Sistema")]
# id do botão do painel -> (o que aparece na conversa, o que o Claude recebe)
QUICK = {
    "briefing": ("Briefing executivo", "Faça meu briefing de analista de hoje: use agenda_today, timer_list, "
                                       "news_digest (as 3 mais relevantes, uma frase sua para cada) e arquivos_recentes "
                                       "(arquivos de dados novos). No máximo cinco frases faladas."),
    "news": ("Resumo de notícias", "Faça o resumo de notícias de dados: use news_digest e fale as 3 mais relevantes, "
                                   "uma frase sua para cada, sem repetir a descrição do feed. Diga que os links estão no feed."),
    "agenda": ("O que tenho na agenda hoje?", "O que tenho na agenda hoje?"),
    "new_task": ("Iniciar tarefa", "Quero criar uma tarefa. Pergunte o que é, em uma frase."),
}


def digest_due(agora: time.struct_time, horario: str, ultimo_dia: int) -> bool:
    """Já passou do horário hoje e o resumo de hoje ainda não saiu."""
    try:
        h, m = (int(x) for x in horario.split(":"))
    except ValueError:
        return False
    hoje = int(time.strftime("%Y%m%d", agora))
    return ultimo_dia != hoje and (agora.tm_hour, agora.tm_min) >= (h, m)


def agent_for(tool: str) -> str:
    t = tool.lower()
    if any(k in t for k in ("websearch", "webfetch", "news", "search", "fetch", "mcp__dados__")):
        return "research"
    if any(k in t for k in ("open_url", "chrome", "browser", "playwright")):
        return "browser"
    if any(k in t for k in ("remember", "recall")):
        return "memory"
    if any(k in t for k in ("timer", "todoist", "task", "agenda", "calendar")):
        return "task"
    if any(k in t for k in ("bash", "write", "edit", "read", "glob", "grep")):
        return "coding"
    return "system"


class Jarvis:
    def __init__(self, mode: str = "wake") -> None:
        self.mode = mode
        self.loop = asyncio.new_event_loop()
        self.brain = Brain()
        self.brain_ready = False
        self.speaker = speaker()
        self.recorder: Recorder | None = None
        self.turn: asyncio.Future | None = None
        self.armed_until = 0.0
        self.agent_seen: dict[str, float] = {}
        self.phase = "idle"
        self.speaker.on_start = self._speaking_started
        self.speaker.on_stop = self._speaking_stopped

    # ------------------------------------------------------------------ estado para o painel
    def set_phase(self, phase: str) -> None:
        self.phase = phase
        level = self.recorder.level if self.recorder else 0.0
        bus.emit({"type": "state", "phase": phase, "level": level})

    def idle_phase(self) -> str:
        return "listening" if self.armed_until > time.time() else "idle"

    def _speaking_started(self) -> None:
        if self.recorder:
            self.recorder.guard = True
        self.set_phase("speaking")

    def _speaking_stopped(self) -> None:
        if self.recorder:
            self.recorder.guard = False
        if not self.busy:
            self.set_phase(self.idle_phase())

    @property
    def busy(self) -> bool:
        return self.turn is not None and not self.turn.done()

    def publish_health(self) -> None:
        stats = memory.stats()
        active = sum(1 for t in self.agent_seen.values() if time.time() - t < 10)
        llms = telemetry.llms(self.brain_ready)
        connected = sum(1 for p in llms if p["status"] == "connected")
        voice_ok = stt.ready.is_set() or self.mode == "off"
        bus.emit({"type": "health", "components": {
            "core": {"status": "ok" if self.brain_ready else "warn", "detail": "Ativo" if self.brain_ready else "Conectando"},
            "memory": {"status": "ok", "detail": f"{stats['memories']} memórias"},
            "voice": {"status": "ok" if voice_ok else "warn",
                      "detail": {"wake": "Ouvindo", "ptt": "Segure Option", "off": "Desligada"}[self.mode]
                      if voice_ok else "Carregando"},
            "agents": {"status": "ok", "detail": f"{active} ativos"},
            "llms": {"status": "ok" if connected else "warn", "detail": f"{connected} conectados"},
            "system": {"status": "ok", "detail": "Ótimo"},
        }})
        bus.emit({"type": "llms", "providers": llms})
        bus.emit({"type": "memory", **stats})
        self.publish_agents()

    def publish_agents(self) -> None:
        """Também no uso de cada ferramenta: o cartão acende enquanto ele trabalha, não no próximo ciclo de 10 s."""
        bus.emit({"type": "agents", "agents": [
            {"id": k, "name": n, "status": "active" if time.time() - self.agent_seen.get(k, 0) < 10 else "standby"}
            for k, n in AGENTS]})

    async def telemetry_loop(self) -> None:
        psutil.cpu_percent(interval=None)
        tick = 0
        while True:
            payload = {"type": "telemetry", **await asyncio.to_thread(telemetry.system), **getattr(self, "_net", {})}
            if tick == 0:
                bus.emit(payload)  # CPU/RAM/disco já; saúde, rede e clima podem levar alguns segundos
            if tick % 5 == 0:
                await asyncio.to_thread(self.publish_health)
            if tick % 15 == 0:  # rede e clima são mais caros: a cada 30 s
                place = await asyncio.to_thread(telemetry.place)
                self._net = {"network": await asyncio.to_thread(telemetry.network),
                             "weather": await asyncio.to_thread(telemetry.weather), "location": place["name"]}
                payload |= self._net
            bus.emit(payload)
            tick += 1
            await asyncio.sleep(2)

    async def digest_loop(self) -> None:
        """Resumo diário de notícias no horário configurado; se o Mac estava desligado no horário, sai ao ligar."""
        if not config.DIGEST_TIME:
            return
        await asyncio.sleep(90)  # deixa a primeira coleta de notícias terminar
        while True:
            if digest_due(time.localtime(), config.DIGEST_TIME, memory.counter("resumo_diario_dia")) and not self.busy:
                memory.set_counter("resumo_diario_dia", int(time.strftime("%Y%m%d")))
                self.submit(QUICK["news"][1], shown="Resumo diário de notícias")
            await asyncio.sleep(60)

    async def kpi_loop(self) -> None:
        """Confere os monitores de KPI; alerta novo é falado e vai para o feed. Tudo local, sem o Claude."""
        from jarvis.brain.tools import painel_kpis
        painel_kpis()  # o painel mostra os monitores (e a última conferência) desde o início
        await asyncio.sleep(120)
        while True:
            if memory.kpis():
                try:
                    for alerta in await asyncio.to_thread(kpis.conferir_todos):
                        print(f"  alerta de KPI: {alerta['texto']}")
                        bus.feed_item(f"Alerta: {alerta['nome']}", "warn", alerta["texto"][:160])
                        self.speaker.say(fillers.trat("Senhor, ") + f"{alerta['texto']}.")
                except Exception as exc:
                    print(f"  monitor de KPIs falhou: {exc}")
                painel_kpis()
            await asyncio.sleep(config.KPI_INTERVALO_S)

    async def level_loop(self) -> None:
        """Nível do microfone ~10x por segundo, só enquanto alguém estaria olhando a onda."""
        while True:
            await asyncio.sleep(0.1)
            if self.recorder and (self.recorder.held or self.phase in ("listening", "speaking")):
                bus.emit({"type": "state", "phase": self.phase,
                          "level": 0.5 if self.phase == "speaking" else self.recorder.level})

    # ------------------------------------------------------------------ um turno
    async def handle(self, text: str, shown: str | None = None) -> None:
        """`shown` é o que aparece na conversa quando o texto enviado ao Claude é um prompt interno."""
        text = text.strip()
        if not text:
            return
        print(f"\n> {text}")
        bus.emit({"type": "transcript", "role": "user", "text": shown or text, "final": True})
        memory.add_turn("user", shown or text)
        self.armed_until = 0
        routes = router.route(text)
        if routes:
            await self._fast(routes)
        elif profundo.estado.ativo and profundo.SAIR.search(text):
            await self._sair_profundo()
        elif profundo.estado.ativo:
            await self._ask_profundo(text)
        else:
            await self._ask(text)

    async def _ask_profundo(self, text: str) -> None:
        """Turno na sessão do plugin: a resposta inteira vai para a conversa; só o resumo é falado."""
        sessao = profundo.estado.sessao
        assert sessao
        self.set_phase("thinking")
        filled = False

        def on_tool(name: str) -> None:
            nonlocal filled
            self.agent_seen["coding"] = time.time()
            self.publish_agents()
            if self.phase != "speaking":
                self.set_phase("tooling")
            if not filled:
                filled = True
                self.speaker.say(fillers.working(name))
            bus.feed_item(f"Análise profunda · {name.replace('mcp__plugin_analise-dados_jupyter__', 'jupyter · ')}", "live", "Jarvis")

        try:
            answer = await sessao.ask(text, on_tool)
        except Exception as exc:
            print(f"  [profundo] falhou: {exc}")
            answer = fillers.trat("Infelizmente a análise profunda não respondeu, senhor.")
            bus.feed_item("A análise profunda não respondeu", "warn", str(exc)[:160])
        self.speaker.say(profundo.falado(answer))
        memory.add_turn("assistant", answer)
        bus.emit({"type": "transcript", "role": "assistant", "text": answer, "final": True})
        if config.ABRIR_NOTEBOOK and not sessao.notebook_aberto and (url := sessao.jupyter_url()):
            sessao.notebook_aberto = True
            await asyncio.to_thread(subprocess.run, ["open", url], capture_output=True)
            bus.feed_item("Notebook aberto no navegador", "info", sessao.projeto.name)
        if not self.speaker.speaking:
            self.set_phase(self.idle_phase())

    async def _sair_profundo(self) -> None:
        sessao, profundo.estado.sessao = profundo.estado.sessao, None
        profundo.estado.pendente = None
        assert sessao
        await sessao.stop()
        line = f"Análise profunda encerrada. O notebook fica salvo em {sessao.projeto.name.replace('_', ' ')}."
        memory.add_turn("assistant", line)
        bus.emit({"type": "transcript", "role": "assistant", "text": line, "final": True})
        bus.feed_item("Análise profunda encerrada", "info", str(sessao.projeto).replace(str(Path.home()), "~"))
        self.speaker.say(line)

    async def _fast(self, routes: list[router.Route]) -> None:
        self.set_phase("tooling")
        replies = []
        for r in routes:
            self.agent_seen["task" if r.name.startswith("timer") else "system"] = time.time()
            self.publish_agents()
            try:
                if r.speak_first and r.reply:
                    self.speaker.say(r.reply)
                    await asyncio.to_thread(self.speaker.wait)
                    await asyncio.to_thread(r.run)
                else:
                    replies.append(await asyncio.to_thread(r.run))
            except Exception as exc:
                print(f"  ação {r.name} falhou: {exc}")
                replies.append("Infelizmente isso falhou.")
        line = " ".join(x for x in replies if x)
        print(f"  [rota rápida: {', '.join(r.name for r in routes)}] {line}")
        if line:
            memory.add_turn("assistant", line)
            bus.emit({"type": "transcript", "role": "assistant", "text": line, "final": True})
            self.speaker.say(line)
        else:
            self.set_phase(self.idle_phase())

    async def _ask(self, text: str) -> None:
        self.set_phase("thinking")
        filled = False
        parts: list[str] = []

        def on_text(delta: str) -> None:
            parts.append(delta)
            self.speaker.push(delta)
            bus.emit({"type": "transcript", "role": "assistant", "text": "".join(parts), "final": False})

        def on_tool(name: str) -> None:
            nonlocal filled
            self.agent_seen[agent_for(name)] = time.time()
            self.publish_agents()
            if self.phase != "speaking":
                self.set_phase("tooling")
            if not filled and not parts:
                filled = True
                self.speaker.say(fillers.working(name))
            if not name.startswith("mcp__mac__") and name not in ("ToolSearch",):
                bus.feed_item(f"Usando {name.replace('mcp__', '').replace('__', ' · ')}", "live", "Jarvis")

        def guard(frase: str) -> str:
            # Frase com número sobre os dados que não saiu de nenhuma ferramenta não é falada
            return UNCONFIRMED if dados.sessao.conferir_frase(frase, text) else frase

        self.speaker.guard = guard
        news.digest_textos = []
        try:
            answer = await self.brain.ask(text, on_text, on_tool)
            self.brain_ready = True
        except Exception as exc:
            print(f"  cérebro falhou: {exc}")
            answer = fillers.trat("Infelizmente o cérebro não respondeu, senhor.")
            self.speaker.say(answer)
            self.brain_ready = False
            bus.feed_item("O Claude não respondeu", "warn", str(exc)[:160])
        self.speaker.flush()
        self.speaker.guard = None
        # Todo número sobre os dados tem de ter saído de uma ferramenta; o que não saiu vira aviso no feed e na conversa
        if sem_origem := dados.sessao.conferir_turno(answer, text):
            print(f"  números sem origem: {sem_origem}")
            bus.feed_item("Número sem origem nos dados", "warn", ", ".join(sem_origem)[:160])
            answer += f"\n\n⚠ Sem origem nos dados (não falado): {', '.join(sem_origem)}"
        # Resumo de notícia é com palavras próprias: trecho longo igual à fonte vira aviso (direito autoral)
        if news.digest_textos and (copias := news.copia_longa(answer, news.digest_textos)):
            print(f"  resumo copiou a fonte: {copias[:2]}")
            bus.feed_item("O resumo repetiu um trecho da fonte", "warn", copias[0][:160])
        if answer:
            memory.add_turn("assistant", answer)
            bus.emit({"type": "transcript", "role": "assistant", "text": answer, "final": True})
        if not self.speaker.speaking:
            self.set_phase(self.idle_phase())

    def submit(self, text: str, shown: str | None = None) -> None:
        """De qualquer thread: começa um turno, interrompendo o anterior se houver."""
        def start() -> None:
            self.turn = asyncio.ensure_future(self._run_turn(text, shown, self.turn))
        self.loop.call_soon_threadsafe(start)

    async def _run_turn(self, text: str, shown: str | None = None, prev: asyncio.Future | None = None) -> None:
        await self.interrupt()
        if prev and not prev.done():
            # O turno cortado publica o fim da resposta dele antes de a nova pergunta entrar na conversa.
            # Não atrasa nada: o cérebro só aceita a próxima pergunta depois de fechar a anterior.
            await asyncio.wait({prev}, timeout=10)
        await self.handle(text, shown)
        # a ferramenta analise_profunda deixa o primeiro pedido da sessão nova para depois deste turno
        if pendente := profundo.estado.pendente:
            profundo.estado.pendente = None
            await self.handle(pendente, shown="Análise profunda: preparando o projeto")

    async def interrupt(self) -> None:
        """Barge-in: corta a fala e a geração."""
        self.speaker.cancel()
        await self.brain.cancel()
        if profundo.estado.sessao:
            await profundo.estado.sessao.cancel()

    # ------------------------------------------------------------------ comandos do painel
    async def on_client(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "say" and isinstance(msg.get("text"), str) and msg["text"].strip():
            self.submit(msg["text"])
        elif kind == "command":
            if quick := QUICK.get(msg.get("id", "")):
                self.submit(quick[1], shown=quick[0])
            elif msg.get("id") == "voice":
                self.arm()
        elif kind == "ptt" and not self.recorder:
            if msg.get("down"):
                self.voice_unavailable()
        elif kind == "ptt":
            if msg.get("down"):
                await self.interrupt()
                self.recorder.press()
                self.set_phase("listening")
            else:
                audio = self.recorder.release()
                threading.Thread(target=self._ptt_turn, args=(audio,), daemon=True).start()

    # ------------------------------------------------------------------ voz
    def arm(self) -> None:
        if not (self.recorder and self.recorder.listening):
            # Sem escuta contínua (modo ptt/off) ninguém fecharia a janela e a fase ficaria em "ouvindo"
            self.voice_unavailable()
            return
        self.armed_until = time.time() + WINDOW_S
        subprocess.Popen(["afplay", CHIME])
        self.set_phase("listening")

    def voice_unavailable(self) -> None:
        """Pedido de voz que este modo não atende: avisa no painel em vez de ficar calado."""
        if self.mode == "off":
            bus.feed_item("Voz desligada", "tip", "O Jarvis foi aberto com --mode off: digite no rodapé ou reabra sem essa opção")
        elif self.recorder is None:
            bus.feed_item("Microfone indisponível", "warn", "Libere em Privacidade e Segurança › Microfone e reabra o Jarvis")
        else:
            bus.feed_item("Segure para falar", "tip", "Modo push-to-talk: segure o Option direito ou o botão do microfone")
        if not self.busy and not self.speaker.speaking:
            self.set_phase(self.idle_phase())

    def _ptt_turn(self, audio) -> None:
        if len(audio) < config.SAMPLE_RATE * 0.3:
            self.set_phase(self.idle_phase())
            return
        self.set_phase("thinking")
        text, ms = stt.transcribe(audio)
        print(f"  (stt {ms} ms)")
        if text:
            self.submit(text)
        else:
            self.set_phase(self.idle_phase())

    def wake_loop(self) -> None:
        assert self.recorder
        while True:
            try:
                audio = self.recorder.segments.get(timeout=1)
            except queue.Empty:
                if self.armed_until and time.time() > self.armed_until:
                    self.armed_until = 0
                    if not self.busy and not self.speaker.speaking:
                        self.set_phase("idle")
                continue
            try:
                self._wake_turn(audio)
            except Exception as exc:  # uma frase ruim nunca pode matar a escuta
                print(f"  escuta falhou: {exc}")

    def _wake_turn(self, audio) -> None:
        text, ms = stt.transcribe(audio, prompt=False)
        if not text:
            return
        talking = self.busy or self.speaker.speaking
        woke, rest, mid = split_wake(text)
        if talking:
            # Enquanto ele fala, só o nome dele ou "para" interrompe: o eco da própria voz não tem "Jarvis"
            if woke or is_stop(text):
                print(f"  (interrompido por: {text!r})")
                asyncio.run_coroutine_threadsafe(self.interrupt(), self.loop).result(timeout=5)
                if rest and not is_stop(rest):
                    self.submit(rest)
                else:
                    self.arm()
            return
        if woke:
            if rest:
                if mid and not router.route(rest):
                    print(f"  (nome no meio da frase, ignorado: {text!r})")
                    return
                self.submit(rest)
            else:
                self.speaker.say(fillers.attention())
                self.arm()
        elif self.armed_until > time.time():
            self.submit(text)
        else:
            print(f"  (não era comigo: {text!r} · {ms} ms)")

    def start_ptt_key(self) -> None:
        """Option direito segurado = falar (precisa de permissão de Monitoramento de Entrada)."""
        from jarvis.mac.hotkey import watch_right_option

        def press() -> None:
            if self.recorder and not self.recorder.held:
                asyncio.run_coroutine_threadsafe(self.on_client({"type": "ptt", "down": True}), self.loop)

        def release() -> None:
            if self.recorder and self.recorder.held:
                asyncio.run_coroutine_threadsafe(self.on_client({"type": "ptt", "down": False}), self.loop)

        if not watch_right_option(press, release):
            print("  push-to-talk indisponível: dê permissão em Ajustes › Privacidade e Segurança › "
                  "Monitoramento de Entrada (e Acessibilidade) para o app que roda o Jarvis")
            bus.feed_item("Option direito sem permissão", "warn",
                          "Libere em Privacidade e Segurança › Monitoramento de Entrada")

    # ------------------------------------------------------------------ timers
    def timer_done(self, t: Timer) -> None:
        subprocess.run(["afplay", ALARM])
        line = fillers.trat(f"Senhor, lembrete: {t.label}." if t.label else "O tempo acabou, senhor.")
        bus.feed_item(t.label or "Timer finalizado", "warn", "Timer")
        self.speaker.say(line)

    # ------------------------------------------------------------------ partida
    async def _boot(self) -> None:
        bus.bind(asyncio.get_running_loop())
        server = uvicorn.Server(uvicorn.Config(__import__("jarvis.server", fromlist=["x"]).create_app(self),
                                               host=config.HOST, port=config.PORT, log_level="warning"))
        asyncio.create_task(server.serve())
        asyncio.create_task(self.telemetry_loop())
        asyncio.create_task(self.level_loop())
        asyncio.create_task(self.digest_loop())
        asyncio.create_task(self.kpi_loop())
        timers.on_done = self.timer_done
        timers.on_change = lambda: bus.emit({"type": "timers", "timers": timers.snapshot()})
        timers.start()
        news.start_loop()
        agenda.start_loop(lambda events: bus.emit({"type": "timeline", "events": events}))
        self.set_phase("idle")
        print(f"[jarvis] painel em http://{config.HOST}:{config.PORT} · modelo {config.MODEL} · "
              f"escrita {'LIGADA' if config.ALLOW_WRITES else 'desligada'} · voz {self.speaker.engine}")
        try:
            await self.brain.start()
            self.brain_ready = True
            print("[jarvis] cérebro conectado")
        except Exception as exc:
            print(f"[jarvis] cérebro não conectou: {exc}")
            bus.feed_item("Claude Code não conectou", "warn", str(exc)[:120])
        await asyncio.to_thread(self.publish_health)  # o painel não espera o próximo ciclo para saber

    def start_background(self) -> None:
        def run_loop() -> None:
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._boot())
            self.loop.run_forever()
        threading.Thread(target=run_loop, daemon=True, name="loop").start()

        def voice() -> None:
            if self.mode == "off":
                return
            print("[jarvis] carregando o Whisper…")
            stt.load()
            self.start_ptt_key()
            try:
                self.recorder = Recorder()
                self.recorder.listening = self.mode == "wake"
                self.recorder.sync()
            except Exception as exc:
                print(f"[jarvis] microfone indisponível: {exc}")
                bus.feed_item("Microfone indisponível", "warn",
                              "Libere em Privacidade e Segurança › Microfone e reabra o Jarvis")
                return
            print(f"[jarvis] voz pronta ({'diga “Ei Jarvis”' if self.mode == 'wake' else 'segure o Option direito'})")
            bus.feed_item("Voz pronta", "info", "Diga “Ei Jarvis”" if self.mode == "wake" else "Segure o Option direito")
            if self.mode == "wake":
                self.wake_loop()
        threading.Thread(target=voice, daemon=True, name="voice").start()


def run(mode: str = "wake", window: bool = True) -> None:
    jarvis = Jarvis(mode)
    jarvis.start_background()
    if window:
        from jarvis.window import open_window
        open_window(f"http://{config.HOST}:{config.PORT}")
        print("[jarvis] janela fechada; continuo ouvindo. Ctrl+C para sair.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\n[jarvis] até logo.")
