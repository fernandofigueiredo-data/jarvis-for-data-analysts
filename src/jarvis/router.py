"""Rota rápida: comandos simples do Mac resolvidos localmente, sem LLM, em milissegundos.

Só responde quando a frase INTEIRA casa com um padrão conhecido. Qualquer dúvida devolve None
e a frase segue para o Claude, que tem as mesmas ações como ferramentas.
"""
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from jarvis.mac import actions as mac
from jarvis.mac.timers import parse_duration, parse_reminder, say_duration, timers


@dataclass
class Route:
    name: str
    run: Callable[[], str]
    speak_first: bool = False  # mutar/bloquear: fala antes, senão ele se cala sozinho
    reply: str | None = None  # resposta fixa dita antes de rodar (com speak_first)
    args: dict = field(default_factory=dict)


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s.:/-]", " ", t)
    t = re.sub(r"\b(por favor|jarvis|ai|ei|ok|oi)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip(" .")


_ALIASES = [(normalize(alias), key) for alias, key in mac.ALIASES]
APP_RX = "|".join(re.escape(a) for a, _ in _ALIASES if a)
ART = r"(?:(?:o|a|os|as|do|da|no|na|pro|pra|para o|para a)\s+)?"
ADVERB = r"(?:\s+(?:agora|ai|pra mim|para mim))?"


def app_key(spoken: str) -> str | None:
    spoken = spoken.strip()
    return next((k for a, k in _ALIASES if a == spoken), None)


VERBS = {
    "open": r"(?:abr[ae]|abrir|inici[ae]|iniciar|lanc[ae]|execut[ae]|executar|liga|ligar)",
    "quit": r"(?:fech[ae]|fechar|encerr[ae]|encerrar|mat[ae]|sai[ar]? d[oa]|sair d[oa])",
    "focus": r"(?:vai pr[oa]|vai para|v[aá] para|mostr[ae]|troca para|troca pr[oa]|muda para|muda pr[oa])",
    "hide": r"(?:escond[ae]|ocult[ae]|esconder)",
}
LEVEL_WORDS = {"zero": 0, "dez": 10, "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
               "metade": 50, "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90, "cem": 100,
               "maximo": 100, "minimo": 10}


def _app_route(t: str) -> Route | None:
    for verb, rx in VERBS.items():
        m = re.fullmatch(rf"{rx}\s+{ART}(?:app\s+|aplicativo\s+)?({APP_RX}){ADVERB}", t)
        if m and (key := app_key(m[1])):
            fn = {"open": mac.open_app, "quit": mac.quit_app, "focus": mac.focus_app, "hide": mac.hide_app}[verb]
            return Route(f"app_{verb}", lambda fn=fn, key=key: fn(key), args={"app": key})
    return None


def _volume_route(t: str) -> Route | None:
    if re.fullmatch(r"(?:aumenta|sobe|aumentar|subir|mais)\s+(?:o\s+)?(?:volume|som)(?:\s+um pouco)?", t):
        return Route("volume_up", lambda: mac.volume_step(15))
    if re.fullmatch(r"(?:abaixa|diminui|baixa|abaixar|diminuir|menos)\s+(?:o\s+)?(?:volume|som)(?:\s+um pouco)?", t):
        return Route("volume_down", lambda: mac.volume_step(-15))
    m = re.fullmatch(r"(?:coloca\s+|poe\s+|deixa\s+)?(?:o\s+)?volume\s+(?:em|para|no|pra|a)\s+(\d{1,3}|\w+)(?:\s*%|\s+por\s*cento)?", t)
    if m:
        level = int(m[1]) if m[1].isdigit() else LEVEL_WORDS.get(m[1])
        if level is not None:
            return Route("volume_set", lambda: mac.set_volume(level), speak_first=level == 0, reply="Silêncio.")
    if re.fullmatch(r"(?:muta|mutar|silencia|silenciar|tira o som|desliga o som)(?:\s+o\s+(?:som|mac|audio))?", t):
        return Route("mute", lambda: mac.mute(True), speak_first=True, reply="Silenciando.")
    if re.fullmatch(r"(?:desmuta|desmutar|tira do mudo|liga o som|volta o som)", t):
        return Route("unmute", lambda: mac.mute(False))
    return None


def _media_route(t: str) -> Route | None:
    table = [
        (r"(?:toca|tocar|play|continua|continuar|solta)(?:\s+a)?(?:\s+musica)?", "play"),
        (r"(?:pausa|pausar|pause|para a musica|parar a musica)(?:\s+a\s+musica)?", "pause"),
        (r"(?:proxima|pula|pular|passa)(?:\s+(?:musica|faixa|essa))?", "next"),
        (r"(?:volta|voltar|anterior)(?:\s+(?:a\s+)?(?:musica|faixa))?(?:\s+anterior)?", "previous"),
    ]
    for rx, action in table:
        if re.fullmatch(rx, t):
            return Route(f"media_{action}", lambda action=action: mac.media(action))
    return None


def _system_route(t: str) -> Route | None:
    if re.fullmatch(r"(?:liga|ativa|ligar|ativar|coloca|poe)\s+(?:o\s+)?modo escuro|modo escuro", t):
        return Route("dark_on", lambda: mac.dark_mode(True))
    if re.fullmatch(r"(?:desliga|desativa|desligar|tira)\s+(?:o\s+)?modo escuro|(?:liga\s+(?:o\s+)?)?modo claro", t):
        return Route("dark_off", lambda: mac.dark_mode(False))
    if re.fullmatch(r"(?:bloqueia|bloquear|trava|travar)\s+(?:a\s+tela|o\s+mac|o\s+computador)", t):
        return Route("lock", mac.lock_screen, speak_first=True, reply="Bloqueando.")
    return None


def _timer_route(t: str, original: str) -> Route | None:
    if re.search(r"\b(timer|temporizador|cronometro|alarme)\b", t) and re.search(r"\b(cancela|cancelar|para|parar|desliga|apaga)\b", t):
        all_ = bool(re.search(r"\btodos\b", t))

        def cancel() -> str:
            n = timers.cancel(all_)
            return "Não há timer rodando." if n == 0 else ("Timers cancelados." if n > 1 else "Timer cancelado.")
        return Route("timer_cancel", cancel)
    if re.fullmatch(r"(?:quanto tempo (?:falta|resta)|quanto falta)(?:\s+(?:no|do|pro)\s+(?:timer|temporizador|lembrete))?", t):
        def check() -> str:
            items = timers.snapshot()
            return f"Faltam {say_duration(items[0]['left'])}." if items else "Não há timer rodando."
        return Route("timer_check", check)
    reminder = re.search(r"\blembr", t)
    if reminder or re.search(r"\b(timer|temporizador|cronometro)\b", t):
        secs = parse_duration(original)
        if not secs:
            return None  # sem duração clara, o Claude pergunta
        label = parse_reminder(original) if reminder else None
        if reminder and not label:
            return None

        def set_timer() -> str:
            timers.add(secs, label)
            return f"Lembrete em {say_duration(secs)}." if label else f"Timer de {say_duration(secs)} iniciado."
        return Route("timer_set", set_timer, args={"secs": secs, "label": label})
    return None


def _misc_route(t: str, original: str) -> Route | None:
    if re.fullmatch(r"(?:que horas sao|que hora e|me diz as horas|horas)", t):
        now = datetime.now()
        return Route("time", lambda: f"São {now.hour} e {now.minute:02d}." if now.minute else f"São {now.hour} horas.")
    m = re.fullmatch(rf"(?:abr[ae]|entra em|vai para|vai no)\s+(?:o\s+site\s+)?(\S+\.\S+)(?:\s+no\s+({APP_RX}))?", t)
    if m and (url := mac.find_url(original)):
        browser = app_key(m[2]) if m[2] else None
        return Route("open_url", lambda: mac.open_url(url, browser))
    return None


def route_one(text: str) -> Route | None:
    t = normalize(text)
    if not t:
        return None
    for fn in (_app_route, _volume_route, _media_route, _system_route):
        if r := fn(t):
            return r
    return _timer_route(t, text) or _misc_route(t, text)


def route(text: str) -> list[Route] | None:
    """Uma ou duas rotas ("abre o Chrome e aumenta o volume"), ou None se algo não for reconhecido."""
    if r := route_one(text):
        return [r]
    parts = re.split(r"\s+e\s+(?:depois\s+)?", text, maxsplit=1)
    if len(parts) == 2:
        routes = [route_one(p) for p in parts]
        if all(routes):
            return routes  # type: ignore[return-value]
    return None
