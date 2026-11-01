"""Barramento de eventos: qualquer thread emite, cada cliente do painel recebe por uma fila asyncio."""
import asyncio
import threading
import time
from typing import Any

Event = dict[str, Any]


class Bus:
    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[Event]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self.last: dict[str, Event] = {}  # último evento de cada tipo, para montar o snapshot
        self.feed: list[Event] = []

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=500)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        self._subs.discard(q)

    def emit(self, event: Event) -> None:
        """Seguro de chamar de qualquer thread."""
        with self._lock:
            if event["type"] == "feed":
                self.feed = [event["item"], *self.feed][:30]
            elif event["type"] != "transcript":
                self.last[event["type"]] = event
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._fanout, event)

    def _fanout(self, event: Event) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # cliente lento perde eventos, nunca trava o resto

    def feed_item(self, title: str, kind: str = "info", subtitle: str = "", url: str | None = None) -> None:
        item = {"id": f"{time.time_ns()}", "title": title, "subtitle": subtitle, "kind": kind, "ts": time.time()}
        if url:
            item["url"] = url
        self.emit({"type": "feed", "item": item})

    def snapshot(self) -> Event:
        with self._lock:
            snap: Event = {"type": "snapshot", "feed": list(self.feed)}
            for k, ev in self.last.items():
                snap[k] = {key: v for key, v in ev.items() if key != "type"}
        return snap


bus = Bus()
