"""Palavra de ativação lida do texto transcrito. O Whisper escreve "Jarvis" de vários jeitos."""
import re

NAMES = r"jarvis|jarvi|jarves|jervis|jarbas|jarbes|jarviz|j[aá]rvis|jarvas|chaves|jervs"
GREETING = r"(?:ei|hey|hei|key|ai|oi|ok|okay|ol[aá]|e a[ií]|fala|a[ií]|[eé])"
# Nome no começo (com ou sem saudação), ou "ei Jarvis" em qualquer ponto da frase
WAKE = re.compile(rf"(?:^\W*(?:{GREETING}\W+)?(?:{NAMES})\b|\b{GREETING}\W+(?:{NAMES})\b)\W*", re.I)
STOP = re.compile(r"^\W*(?:para|pare|chega|cala a boca|sil[eê]ncio|stop|cancela|esquece)\W*$", re.I)
WINDOW_S = 10.0


def split_wake(text: str) -> tuple[bool, str, bool]:
    """(acordou?, o que veio depois do nome, foi no meio da frase?)."""
    m = WAKE.search(text)
    if not m:
        return False, "", False
    return True, text[m.end():].strip(" .,!?"), bool(text[:m.start()].strip(" .,!?"))


def is_stop(text: str) -> bool:
    return bool(STOP.match(text))
