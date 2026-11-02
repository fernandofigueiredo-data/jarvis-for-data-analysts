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
