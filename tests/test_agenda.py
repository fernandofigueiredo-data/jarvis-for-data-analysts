import subprocess
from datetime import date, datetime, timedelta

import pytest

from jarvis import agenda


@pytest.fixture
def cache(monkeypatch):
    monkeypatch.setattr(agenda, "_looping", True)
    yield lambda raw: (monkeypatch.setattr(agenda, "_cache", (date.today(), raw)), agenda._ready.set())
    agenda._ready.clear()


def test_statuses_come_from_cache(cache):
    now = datetime.now().astimezone()
    at = lambda minutes: (now + timedelta(minutes=minutes)).isoformat()  # noqa: E731
    cache([{"title": "Passou", "start": at(-120), "end": at(-60), "allDay": False},
           {"title": "Agora", "start": at(-5), "end": at(30), "allDay": False},
           {"title": "Depois", "start": at(95), "end": at(120), "allDay": False}])
    events = agenda.today()
    assert [e["status"] for e in events[:2]] == ["Concluído", "Agora"]
    assert events[2]["status"].startswith("Em 1h3")


def test_none_while_first_read_runs(cache):
    assert agenda.today(wait=0) is None


def test_fetch_timeout_is_none(monkeypatch):
    def slow(*_a, **_k):
        raise subprocess.TimeoutExpired("osascript", 1)
    monkeypatch.setattr(agenda.subprocess, "run", slow)
    assert agenda.fetch(timeout=1) is None


def test_resumo_em_ordem_com_horario_e_titulo(cache):
    hoje = datetime.now().astimezone().replace(second=0, microsecond=0)
    at = lambda h, m=0: hoje.replace(hour=h, minute=m).isoformat()  # noqa: E731
    cache([{"title": "Dentista", "start": at(14, 30), "end": at(15), "allDay": False},
           {"title": "Daily", "start": at(9), "end": at(9, 15), "allDay": False}])
    assert agenda.resumo_hoje() == "Hoje você tem: 09:00, Daily; 14:30, Dentista."


def test_resumo_sem_compromissos(cache):
    cache([])
    assert agenda.resumo_hoje() == "Não há compromissos na sua agenda hoje."


def test_resumo_agenda_inacessivel(cache):
    assert agenda.resumo_hoje(wait=0) == "Não consegui acessar sua agenda agora."
