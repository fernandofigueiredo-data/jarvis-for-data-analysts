"""Sinais do sistema para o painel: CPU/RAM/disco, rede, clima e quais modelos estão disponíveis."""
import socket
import time

import httpx
import psutil

from jarvis import config
from jarvis.keychain import get_secret
from jarvis.mac import location

WEATHER_CODES = {0: "Céu limpo", 1: "Quase limpo", 2: "Parcialmente nublado", 3: "Nublado", 45: "Neblina",
                 48: "Neblina", 51: "Garoa", 53: "Garoa", 55: "Garoa forte", 61: "Chuva fraca", 63: "Chuva",
                 65: "Chuva forte", 80: "Pancadas", 81: "Pancadas", 82: "Temporal", 95: "Trovoadas",
                 96: "Trovoadas", 99: "Trovoadas"}
_place: dict | None = None
_place_ts = 0.0
PLACE_TTL_S = 30 * 60
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


def reverse_geocode(lat: float, lon: float) -> str:
    """Coordenadas -> "Cidade/UF" (no Brasil) ou "Cidade, País", pelo OpenStreetMap. Vazio se falhar."""
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/reverse",
                      params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 10, "accept-language": "pt-BR"},
                      headers={"User-Agent": "Jarvis/0.1 (assistente local para macOS)"}, timeout=10).json()
        a = r["address"]
    except Exception:
        return ""
    city = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or a.get("county") or ""
    uf = a.get("ISO3166-2-lvl4", "").removeprefix("BR-") if a.get("country_code") == "br" else ""
    if not city:
        return ""
    return f"{city}/{uf}" if uf else f"{city}, {a.get('country', '')}".rstrip(", ")


def set_precise(lat: float, lon: float) -> dict | None:
    """Posição precisa (do Mac ou do navegador do painel). Troca o local aproximado e refaz o clima.
    None quando nada mudou (mesma cidade) ou a geocodificação reversa falhou."""
    global _place, _weather, _place_ts
    if _place and not _place.get("approx") and _place["lat"] is not None \
            and abs(_place["lat"] - lat) < 0.01 and abs(_place["lon"] - lon) < 0.01:
        _place_ts = time.time()
        return None  # mesmo lugar: não consulta de novo
    name = reverse_geocode(lat, lon)
    if not name:
        return None
    _place = {"name": name, "lat": lat, "lon": lon, "approx": False}
    _place_ts = time.time()
    _weather = None
    return _place


def place() -> dict:
    """Cidade e coordenadas, nesta ordem: JARVIS_LOCATION; a localização do Mac (app auxiliar, com a permissão de
    Serviços de Localização) ou a do navegador do painel; e, sem nenhuma delas, o IP (aproximada). Relida a cada 30 min."""
    global _place, _place_ts
    if _place and (config.LOCATION or time.time() - _place_ts < PLACE_TTL_S):
        return _place
    try:
        if config.LOCATION:
            r = httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                          params={"name": config.LOCATION, "count": 1, "language": "pt"}, timeout=10).json()
            g = r["results"][0]
            _place = {"name": g["name"], "lat": g["latitude"], "lon": g["longitude"], "approx": False}
            return _place
        if config.LOCAL_PRECISO and (fix := location.current()) and (set_precise(fix["lat"], fix["lon"]) or (_place and not _place["approx"])):
            return _place
        if _place and not _place["approx"]:
            _place_ts = time.time()  # o Mac não respondeu agora: a última posição precisa vale mais que o IP
            return _place
        r = httpx.get("https://get.geojs.io/v1/ip/geo.json", timeout=10).json()
        lat, lon = float(r["latitude"]), float(r["longitude"])
        # o IP aponta para a central do provedor, não para a casa: o painel mostra como aproximado
        _place = {"name": reverse_geocode(lat, lon) or r.get("city", ""), "lat": lat, "lon": lon, "approx": True}
        _place_ts = time.time()
    except Exception:
        _place = {"name": "", "lat": None, "lon": None, "approx": True}
        _place_ts = time.time() - PLACE_TTL_S + 60  # sem rede: tenta de novo em um minuto
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
