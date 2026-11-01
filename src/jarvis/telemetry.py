"""Sinais do sistema para o painel: CPU/RAM/disco, rede, clima e quais modelos estão disponíveis."""
import socket
import time

import httpx
import psutil

from jarvis import config
from jarvis.keychain import get_secret

WEATHER_CODES = {0: "Céu limpo", 1: "Quase limpo", 2: "Parcialmente nublado", 3: "Nublado", 45: "Neblina",
                 48: "Neblina", 51: "Garoa", 53: "Garoa", 55: "Garoa forte", 61: "Chuva fraca", 63: "Chuva",
                 65: "Chuva forte", 80: "Pancadas", 81: "Pancadas", 82: "Temporal", 95: "Trovoadas",
                 96: "Trovoadas", 99: "Trovoadas"}
_place: dict | None = None
_weather: tuple[float, dict] | None = None


def system() -> dict:
    return {"cpu": round(psutil.cpu_percent(interval=None)), "ram": round(psutil.virtual_memory().percent),
            "disk": round(psutil.disk_usage("/").percent)}


def network() -> str:
    t = time.time()
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2).close()
    except OSError:
        return "Offline"
    ms = (time.time() - t) * 1000
    return "Excelente" if ms < 60 else "Boa" if ms < 200 else "Fraca"


def place() -> dict:
    """Cidade e coordenadas: de JARVIS_LOCATION (geocodificada) ou, sem ela, aproximada pelo IP."""
    global _place
    if _place:
        return _place
    try:
        if config.LOCATION:
            r = httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                          params={"name": config.LOCATION, "count": 1, "language": "pt"}, timeout=10).json()
            g = r["results"][0]
            _place = {"name": g["name"], "lat": g["latitude"], "lon": g["longitude"]}
        else:
            r = httpx.get("https://get.geojs.io/v1/ip/geo.json", timeout=10).json()
            _place = {"name": r.get("city", ""), "lat": float(r["latitude"]), "lon": float(r["longitude"])}
    except Exception:
        _place = {"name": "", "lat": None, "lon": None}
    return _place


def weather() -> dict | None:
    global _weather
    if _weather and time.time() - _weather[0] < 15 * 60:
        return _weather[1]
    p = place()
    if p["lat"] is None:
        return None
    try:
        r = httpx.get("https://api.open-meteo.com/v1/forecast",
                      params={"latitude": p["lat"], "longitude": p["lon"], "current": "temperature_2m,weather_code"},
                      timeout=10).json()["current"]
        w = {"tempC": round(r["temperature_2m"]), "desc": WEATHER_CODES.get(r["weather_code"], "")}
        _weather = (time.time(), w)
        return w
    except Exception:
        return None


def ollama_up() -> bool:
    try:
        return httpx.get("http://127.0.0.1:11434/api/tags", timeout=1).status_code == 200
    except Exception:
        return False


def llms(claude_connected: bool) -> list[dict]:
    keyed = {"OpenAI": "OPENAI_API_KEY", "Gemini": "GEMINI_API_KEY", "Groq": "GROQ_API_KEY",
             "OpenRouter": "OPENROUTER_API_KEY", "ElevenLabs": "ELEVENLABS_API_KEY"}
    out = [{"name": "Claude Code", "status": "connected" if claude_connected else "not_linked"}]
    out += [{"name": n, "status": "connected" if get_secret(k) else "not_linked"} for n, k in keyed.items()]
    out.append({"name": "Ollama", "status": "connected" if ollama_up() else "not_linked"})
    return out
