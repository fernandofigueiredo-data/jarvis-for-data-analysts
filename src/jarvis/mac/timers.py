"""Timers e lembretes, com duração falada em português ("vinte e cinco minutos", "uma hora e meia")."""
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

NUMBERS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "três": 3, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "noventa": 90,
}
UNITS = {"s": 1, "seg": 1, "segs": 1, "segundo": 1, "segundos": 1,
         "m": 60, "min": 60, "mins": 60, "minuto": 60, "minutos": 60,
         "h": 3600, "hr": 3600, "hrs": 3600, "hora": 3600, "horas": 3600}
DURATION = re.compile(r"(\d+(?:[.,]\d+)?)\s*(horas?|hrs?|h|minutos?|mins?|m|segundos?|segs?|s)\b(\s+e\s+mei[ao])?")


def _digits(text: str) -> str:
    """'vinte e cinco minutos' -> '25 minutos', 'meia hora' -> '30 minutos'."""
    t = text.lower()
    t = re.sub(r"\bmeia hora\b", "30 minutos", t)
    t = re.sub(r"\bum minuto e meio\b", "90 segundos", t)
    words = t.replace("-", " ").split()
    out, i = [], 0
    while i < len(words):
        w = words[i].strip(",.!?")
        if w in NUMBERS:
            n = NUMBERS[w]
            # "vinte e cinco": dezena + "e" + unidade
            if n >= 20 and i + 2 < len(words) and words[i + 1] == "e" and NUMBERS.get(words[i + 2].strip(",.!?"), 99) < 10:
                n, i = n + NUMBERS[words[i + 2].strip(",.!?")], i + 2
            out.append(str(n))
        else:
            out.append(words[i])
        i += 1
    return " ".join(out)


def parse_duration(text: str) -> int | None:
    total = 0.0
    for num, unit, half in DURATION.findall(_digits(text)):
        secs = UNITS[unit]
        total += float(num.replace(",", ".")) * secs + (secs / 2 if half else 0)
    return int(total) or None


DURATION_PHRASE = re.compile(r"\s*\b(?:daqui a|daqui|em|dentro de|por|após|depois de)?\s*" + DURATION.pattern)


def parse_reminder(text: str) -> str | None:
    """'me lembra daqui a 20 minutos de ligar pra mãe' -> 'ligar pra mãe'."""
    t = _digits(text)
    m = re.search(r"\blembr\w*\s+(?:-?me\s+)?(.*)$", t)
    if not m:
        return None
    rest = DURATION_PHRASE.sub(" ", m[1])
    rest = re.sub(r"^\s*(?:de|que|para|pra)\s+", "", rest.strip())
    rest = re.sub(r"\s+(?:daqui|em|por favor)$", "", rest).strip(" .,!?")
    return rest or None


def say_duration(secs: float) -> str:
    secs = max(0, int(round(secs)))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    parts = [f"{n} {u}{'' if n == 1 else 's'}" for n, u in ((h, "hora"), (m, "minuto"), (s, "segundo")) if n]
    if h or m >= 10:
        parts = parts[:2] if h else parts[:1]
    return " e ".join(parts) or "nenhum tempo"


@dataclass
class Timer:
    end: float
    secs: int
    label: str | None = None
    id: str = field(default_factory=lambda: str(time.time_ns()))


class Timers:
    def __init__(self) -> None:
        self._items: list[Timer] = []
        self._lock = threading.Lock()
        self.on_done: Callable[[Timer], None] = lambda t: None
        self.on_change: Callable[[], None] = lambda: None

    def add(self, secs: int, label: str | None = None) -> Timer:
        t = Timer(time.time() + secs, secs, label)
        with self._lock:
            self._items.append(t)
            self._items.sort(key=lambda x: x.end)
        self.on_change()
        return t

    def snapshot(self) -> list[dict]:
        now = time.time()
        with self._lock:
            return [{"id": t.id, "label": t.label, "left": max(0, t.end - now), "secs": t.secs} for t in self._items]

    def cancel(self, all_: bool = False) -> int:
        with self._lock:
            if not self._items:
                return 0
            if all_:
                n = len(self._items)
                self._items.clear()
            else:
                self._items.remove(max(self._items, key=lambda t: t.end - t.secs))  # o criado por último
                n = 1
        self.on_change()
        return n

    def start(self) -> None:
        def loop() -> None:
            while True:
                time.sleep(0.25)
                with self._lock:
                    due = [t for t in self._items if t.end <= time.time()]
                    for t in due:
                        self._items.remove(t)
                for t in due:
                    try:
                        self.on_done(t)
                    except Exception as exc:
                        print(f"  aviso de timer falhou: {exc}")
                if due:
                    self.on_change()
        threading.Thread(target=loop, daemon=True, name="timers").start()


timers = Timers()
