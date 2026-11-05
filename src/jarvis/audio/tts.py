"""Fala. O texto chega em pedaços e é falado frase a frase, então ele começa a falar enquanto o Claude ainda escreve.

A fila é uma lista com um único consumidor, e não uma cadeia de promessas: uma lista dá para esvaziar
no meio (barge-in) sem deixar nada pendurado. Ideia do adewaskar/jarvis (MIT).
"""
import hashlib
import re
import subprocess
import threading
from collections import deque
from collections.abc import Callable

import httpx

from jarvis import config
from jarvis.events import bus
from jarvis.keychain import get_secret

# Fim de frase só com espaço depois: no fim do pedaço, "R$ 50." pode ainda virar "R$ 50.657,14" no próximo.
# A última frase da resposta sai pelo flush().
SENTENCE = re.compile(r"^(.+?[.!?;:…])(?=\s)", re.S)
# Voz padrão (premade) da ElevenLabs, multilíngue: funciona no plano gratuito. Vozes da Voice Library dão
# 402 paid_plan_required pela API no plano gratuito. JARVIS_ELEVEN_VOICE_ID troca.
ELEVEN_DEFAULT_VOICE = "pNInz6obpgDQGcFmaJgB"


def clean(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>\[\]|]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Speaker:
    def __init__(self) -> None:
        self.queue: deque[str] = deque()
        self.buffer = ""
        self.proc: subprocess.Popen | None = None
        self.cond = threading.Condition()
        self.busy = False
        self.on_start: Callable[[], None] = lambda: None
        self.on_stop: Callable[[], None] = lambda: None
        # Filtro de cada frase do streaming antes de ir para a fila (ex.: número sem origem nos dados)
        self.guard: Callable[[str], str] | None = None
        self.eleven_key = get_secret("ELEVENLABS_API_KEY")
        self.voice_id = config.ELEVEN_VOICE_ID or ELEVEN_DEFAULT_VOICE
        self.eleven_errors: set[str] = set()
        threading.Thread(target=self._pump, daemon=True, name="tts").start()

    @property
    def engine(self) -> str:
        return "ElevenLabs" if self.eleven_key else f"macOS ({config.TTS_VOICE})"

    @property
    def speaking(self) -> bool:
        return self.busy or bool(self.queue)

    def push(self, delta: str) -> None:
        """Texto em streaming: frases completas vão para a fila, o resto espera."""
        self.buffer += delta
        while m := SENTENCE.match(self.buffer.lstrip()):
            self.buffer = self.buffer.lstrip()[m.end():]
            self._enqueue(m[1])

    def say(self, text: str, first: bool = False) -> None:
        with self.cond:
            if first:
                self.queue.appendleft(clean(text))
            else:
                self.queue.append(clean(text))
            self.cond.notify()

    def flush(self) -> None:
        if self.buffer.strip():
            self._enqueue(self.buffer)
        self.buffer = ""

    def wait(self) -> None:
        with self.cond:
            self.cond.wait_for(lambda: not self.queue and not self.busy)

    def cancel(self) -> None:
        with self.cond:
            self.queue.clear()
            self.buffer = ""
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()

    def _enqueue(self, text: str) -> None:
        text = clean(text)
        if text and self.guard:
            text = self.guard(text)
        if text:
            self.say(text)

    def _pump(self) -> None:
        while True:
            with self.cond:
                self.cond.wait_for(lambda: bool(self.queue))
                text = self.queue.popleft()
                was_idle = not self.busy
                self.busy = True
            if was_idle:
                self.on_start()
            try:
                self._play(text)
            except Exception as exc:
                print(f"  fala falhou: {exc}")
            with self.cond:
                if not self.queue:
                    self.busy = False
                    self.cond.notify_all()
                    idle = True
                else:
                    idle = False
            if idle:
                self.on_stop()

    def _play(self, text: str) -> None:
        if self.eleven_key:
            try:
                path = self._eleven(text)
                self._run(["afplay", str(path)])
                return
            except Exception as exc:
                print(f"  ElevenLabs falhou, usando a voz do macOS: {exc}")
                if str(exc) not in self.eleven_errors:  # avisa no painel uma vez: a voz mudou e por quê
                    self.eleven_errors.add(str(exc))
                    bus.feed_item("ElevenLabs recusou a fala", "warn", f"{exc} · usando a voz do macOS"[:160])
        self._run(["say", "-v", config.TTS_VOICE, "-r", "195", text])

    def _run(self, cmd: list[str]) -> None:
        self.proc = subprocess.Popen(cmd)
        self.proc.wait()

    def _eleven(self, text: str):
        """Gera uma vez e guarda em disco: frases fixas ("Pesquisando.") saem instantâneas na próxima."""
        cache = config.CACHE_DIR / "tts"
        cache.mkdir(exist_ok=True)
        path = cache / (hashlib.sha1(f"{self.voice_id}|{text}".encode()).hexdigest() + ".mp3")
        if not path.exists():
            r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
                           params={"output_format": "mp3_44100_128"},
                           headers={"xi-api-key": self.eleven_key},
                           json={"text": text, "model_id": "eleven_flash_v2_5", "language_code": "pt"}, timeout=30)
            if r.status_code != 200:  # o corpo diz o motivo (ex.: voice_not_found para um ID fora da conta)
                raise RuntimeError(f"HTTP {r.status_code} para a voz {self.voice_id}: {r.text[:200]}")
            path.write_bytes(r.content)
        return path


_speaker: Speaker | None = None


def speaker() -> Speaker:
    global _speaker
    if _speaker is None:
        _speaker = Speaker()
    return _speaker


def speak_blocking(text: str) -> None:
    s = speaker()
    s.say(text)
    s.wait()
