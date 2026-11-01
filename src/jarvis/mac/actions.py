"""Ações nativas do Mac, cada uma um one-liner de AppleScript ou shell."""
import json
import re
import subprocess
import time
from dataclasses import dataclass

from jarvis import config


@dataclass(frozen=True)
class App:
    key: str
    name: str  # nome em /Applications
    say: str  # como o Jarvis fala o nome


def load_apps() -> dict[str, App]:
    raw = json.loads(config.APPS_FILE.read_text(encoding="utf-8"))
    out = {}
    for key, v in raw.items():
        if isinstance(v, str):
            out[key] = App(key, v, v)
        else:
            out[key] = App(key, v["app"], v.get("say", v["app"]))
    return out


def load_aliases() -> list[tuple[str, str]]:
    """(como pode ser ouvido, chave do app), do mais longo para o mais curto, para casar o mais específico primeiro."""
    raw = json.loads(config.APPS_FILE.read_text(encoding="utf-8"))
    pairs = []
    for key, v in raw.items():
        names = {key, v if isinstance(v, str) else v["app"]}
        if isinstance(v, dict):
            names |= {v.get("say", v["app"]), *v.get("heard_as", [])}
        pairs += [(n.lower(), key) for n in names]
    return sorted(set(pairs), key=lambda p: -len(p[0]))


APPS = load_apps()
ALIASES = load_aliases()


class ActionError(RuntimeError):
    pass


def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode:
        raise ActionError(r.stderr.strip() or "AppleScript falhou")
    return r.stdout.strip()


def sh(*cmd: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise ActionError(r.stderr.strip() or f"comando falhou: {' '.join(cmd)}")


def app_running(name: str) -> bool:
    return osa(f'application "{name}" is running') == "true"


def open_app(key: str, wait: float = 5.0) -> str:
    """Abre e espera o app subir, para uma ação seguinte não chegar cedo demais."""
    app = APPS[key]
    sh("open", "-a", app.name)
    t = time.time()
    while time.time() - t < wait and not app_running(app.name):
        time.sleep(0.2)
    return f"{app.say} aberto."


def quit_app(key: str) -> str:
    app = APPS[key]
    if not app_running(app.name):
        return f"{app.say} já estava fechado."
    osa(f'tell application "{app.name}" to quit')
    return f"{app.say} fechado."


def _process(key: str) -> str:
    # Pelo bundle id, porque o nome do processo difere (VS Code roda como "Code")
    bid = osa(f'id of application "{APPS[key].name}"')
    return f'(first application process whose bundle identifier is "{bid}")'


def hide_app(key: str) -> str:
    osa(f'tell application "System Events" to set visible of {_process(key)} to false')
    return f"{APPS[key].say} oculto."


def focus_app(key: str) -> str:
    osa(f'tell application "{APPS[key].name}" to activate')
    return f"{APPS[key].say} em primeiro plano."


def volume() -> int:
    return int(osa("output volume of (get volume settings)"))


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    osa(f"set volume output volume {level}")
    return f"Volume em {level} por cento."


def volume_step(delta: int) -> str:
    return set_volume(volume() + delta)


def mute(on: bool = True) -> str:
    osa(f"set volume output muted {'true' if on else 'false'}")
    return "Som desligado." if on else "Som de volta."


def dark_mode(on: bool | None) -> str:
    value = "not dark mode" if on is None else ("true" if on else "false")
    osa(f'tell application "System Events" to tell appearance preferences to set dark mode to {value}')
    return "Modo escuro alternado." if on is None else ("Modo escuro ligado." if on else "Modo claro ligado.")


def lock_screen() -> str:
    osa('tell application "System Events" to keystroke "q" using {control down, command down}')
    return "Tela bloqueada."


def sleep_mac() -> str:
    sh("pmset", "sleepnow")
    return "Boa noite."


def _player() -> str:
    """Spotify se estiver aberto, senão o app Música."""
    for name in ("Spotify", "Music"):
        try:
            if app_running(name):
                return name
        except ActionError:
            continue
    return "Music"


def media(action: str) -> str:
    player = _player()
    if action == "play":
        osa(f'tell application "{player}" to play')
        return "Tocando."
    if action == "pause":
        osa(f'tell application "{player}" to pause')
        return "Pausado."
    if action == "next":
        osa(f'tell application "{player}" to next track')
        return "Próxima faixa."
    if action == "previous":
        # no meio da música um "anterior" só reinicia a faixa, então aperta duas vezes
        osa(f'tell application "{player}"\nif player position > 3 then\nprevious track\ndelay 0.3\nend if\nprevious track\nend tell')
        return "Faixa anterior."
    raise ActionError(f"ação de mídia desconhecida: {action}")


URL_RX = re.compile(r"\b((?:[\w-]+\.)+(?:com\.br|com|org\.br|org|net|io|ai|dev|tv|app|me|br|gov\.br|edu)(?:/\S*)?)", re.I)


def find_url(text: str) -> str | None:
    t = re.sub(r"\s+ponto\s+", ".", text, flags=re.I)
    m = URL_RX.search(t)
    return "https://" + m[1].lower().rstrip(".,!?") if m else None


def open_url(url: str, browser_key: str | None = None) -> str:
    if browser_key:
        sh("open", "-a", APPS[browser_key].name, url)
    else:
        sh("open", url)
    site = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return f"Abrindo {site}."
