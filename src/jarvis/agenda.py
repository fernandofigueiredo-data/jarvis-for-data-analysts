"""Compromissos de hoje lidos do app Calendário (iCloud, Google etc. que estiverem sincronizados nele).

A consulta por AppleScript é lenta em calendários grandes (quase um minuto em alguns Macs), então ela roda
numa thread própria e o resto do Jarvis lê o último resultado guardado.
"""
import json
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import date, datetime

JXA = """
const app = Application('Calendar');
const start = new Date(); start.setHours(0,0,0,0);
const end = new Date(start); end.setDate(end.getDate() + 1);
const out = [];
for (const cal of app.calendars()) {
  let evs = [];
  try { evs = cal.events.whose({_and: [{startDate: {_greaterThanEquals: start}}, {startDate: {_lessThan: end}}]})(); }
  catch (e) { continue; }
  for (const ev of evs) {
    out.push({title: ev.summary(), start: ev.startDate().toISOString(), end: ev.endDate().toISOString(),
              allDay: ev.alldayEvent(), calendar: cal.name()});
  }
}
JSON.stringify(out);
"""
FETCH_TIMEOUT_S = 150
REFRESH_S = 10 * 60

_cache: tuple[date, list[dict]] | None = None  # (dia da leitura, eventos crus)
_ready = threading.Event()
_looping = False


def fetch(timeout: float = FETCH_TIMEOUT_S) -> list[dict] | None:
    """Eventos crus de hoje, ou None se o Calendário não respondeu."""
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode:
        return None
    return json.loads(r.stdout) if r.stdout.strip() else []


def refresh() -> bool:
    global _cache
    raw = fetch()
    if raw is None:
        return False
    _cache = (date.today(), raw)
    _ready.set()
    return True


def today(wait: float = 0) -> list[dict] | None:
    """[{time, title, status, start, end}] de hoje, ordenado. None enquanto a primeira leitura não terminou."""
    if not _looping and not _ready.is_set():
        refresh()  # sem o loop do daemon (jarvis --text): lê agora mesmo
    if not _ready.wait(wait) or _cache is None or _cache[0] != date.today():
        return None
    now = datetime.now().astimezone()
    events = []
    for ev in _cache[1]:
        start = datetime.fromisoformat(ev["start"].replace("Z", "+00:00")).astimezone()
        end = datetime.fromisoformat(ev["end"].replace("Z", "+00:00")).astimezone()
        if end <= now:
            status = "Concluído"
        elif start <= now:
            status = "Agora"
        else:
            mins = int((start - now).total_seconds() // 60)
            status = f"Em {mins} min" if mins < 60 else f"Em {mins // 60}h{mins % 60:02d}"
        events.append({"time": "Dia todo" if ev["allDay"] else start.strftime("%H:%M"), "title": ev["title"],
                       "status": status, "start": start.isoformat(), "end": end.isoformat()})
    return sorted(events, key=lambda e: e["start"])


def resumo_hoje(wait: float = 15) -> str:
    """Compromissos de hoje (fuso do Mac) numa frase falável: horário e título, em ordem cronológica."""
    events = today(wait)
    if events is None:
        return "Não consegui acessar sua agenda agora."
    tz = datetime.now().astimezone().tzinfo
    hoje = datetime.now(tz).date()
    itens = []
    for ev in events:  # today() já vem ordenado pelo início
        start = datetime.fromisoformat(ev["start"]).astimezone(tz)
        if ev["time"] == "Dia todo":
            itens.append(f"o dia todo, {ev['title']}")
        elif start.date() == hoje:
            itens.append(f"{start:%H:%M}, {ev['title']}")
    if not itens:
        return "Não há compromissos na sua agenda hoje."
    return "Hoje você tem: " + "; ".join(itens) + "."


def start_loop(on_update: Callable[[list[dict]], None]) -> None:
    """Relê o Calendário a cada 10 min (e na virada do dia) e publica a cada minuto, para o "Em 5 min" andar."""
    global _looping
    _looping = True

    def loop() -> None:
        last = 0.0
        while True:
            if time.time() - last > REFRESH_S or (_cache and _cache[0] != date.today()):
                last = time.time()
                if not refresh():
                    print("  agenda: o Calendário não respondeu")
            events = today()
            if events is not None:
                on_update(events)
            time.sleep(60)
    threading.Thread(target=loop, daemon=True, name="agenda").start()
