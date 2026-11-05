import asyncio

import pytest

from jarvis import app as app_module
from jarvis.brain.agent import BrainError
from jarvis.events import bus
from jarvis.memory import Memory


class QuietSpeaker:
    speaking = False

    def say(self, _text):
        pass

    def push(self, _delta):
        pass

    def flush(self):
        pass

    def cancel(self):
        pass


class FlakyBrain:
    """Falha uma vez (limite de uso, sobrecarga) e depois responde."""

    def __init__(self):
        self.calls = 0

    async def ask(self, _text, on_text, on_tool):
        self.calls += 1
        if self.calls == 1:
            raise BrainError("Claude AI usage limit reached")
        on_text("Canberra.")
        return "Canberra."


@pytest.mark.asyncio
async def test_failed_turn_is_reported_and_status_recovers(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "memory", Memory(tmp_path / "t.db"))
    j = app_module.Jarvis("off")
    j.speaker, j.brain, j.brain_ready = QuietSpeaker(), FlakyBrain(), True

    await j._ask("qual a capital da Austrália?")
    assert not j.brain_ready
    assert bus.feed[0]["title"] == "O Claude não respondeu" and "usage limit" in bus.feed[0]["subtitle"]

    await j._ask("qual a capital da Austrália?")
    assert j.brain_ready


class SlowBrain:
    """Fica escrevendo até ser interrompido, como uma resposta longa cortada por outra pergunta."""

    def __init__(self):
        self.stop = asyncio.Event()
        self.busy = False

    async def ask(self, text, on_text, on_tool):
        if "longa" in text:
            self.busy = True
            on_text("Resposta longa")
            await self.stop.wait()
            self.busy = False
            return "Resposta longa"
        on_text("Curta.")
        return "Curta."

    async def cancel(self):
        if self.busy:  # como o Brain: só interrompe uma resposta em andamento
            self.stop.set()


@pytest.mark.asyncio
async def test_interrupted_answer_closes_before_the_next_question(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "memory", Memory(tmp_path / "t.db"))
    seen = []
    monkeypatch.setattr(app_module.bus, "emit", lambda ev: seen.append(ev))
    j = app_module.Jarvis("off")
    j.speaker, j.brain = QuietSpeaker(), SlowBrain()
    first = asyncio.ensure_future(j._run_turn("explique de forma longa"))
    await asyncio.sleep(0.05)
    await j._run_turn("e agora?", None, first)
    finals = [(e["role"], e["text"]) for e in seen if e["type"] == "transcript" and e["final"]]
    assert finals == [("user", "explique de forma longa"), ("assistant", "Resposta longa"),
                      ("user", "e agora?"), ("assistant", "Curta.")]


def test_voice_button_without_listening_does_not_stick(monkeypatch):
    j = app_module.Jarvis("off")
    j.speaker = QuietSpeaker()
    j.arm()
    assert j.armed_until == 0 and j.phase == "idle"
    assert bus.feed[0]["title"] == "Voz desligada"


@pytest.mark.parametrize("heard", ["Bom dia, Jarvis.", "boa noite jarvis"])
def test_spoken_greeting_wakes_without_ei_jarvis(monkeypatch, heard):
    """O nome vem no fim ("bom dia, Jarvis"): a frase inteira vira o pedido, sem precisar do "Ei Jarvis"."""
    j = app_module.Jarvis("off")
    j.speaker = QuietSpeaker()
    sent = []
    monkeypatch.setattr(j, "submit", sent.append)
    monkeypatch.setattr(app_module.stt, "transcribe", lambda _audio, prompt=False: (heard, 5))
    j._wake_turn(b"")
    assert sent == [heard]
