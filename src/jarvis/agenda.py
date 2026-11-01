"""Compromissos de hoje lidos do app Calendário (iCloud, Google etc. que estiverem sincronizados nele)."""
import json
import subprocess
from datetime import datetime

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


def today(timeout: float = 20) -> list[dict]:
    """[{time, title, status, start, end}] de hoje, ordenado. Vazio se o Calendário não responder."""
    try:
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return []
    if r.returncode or not r.stdout.strip():
        return []
    now = datetime.now().astimezone()
    events = []
    for ev in json.loads(r.stdout):
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
