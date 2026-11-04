"""Frases curtas ditas quando uma ferramenta começa, para o silêncio de alguns segundos não parecer travamento."""
import random

from jarvis import config

WORKING = ["Pesquisando.", "Um instante, senhor.", "Consultando.", "Verificando.", "Buscando.", "Processando."]
ATTENTION = ["Sim, senhor?", "Senhor?", "Pois não.", "Estou ouvindo."]
NEWS = ["Consultando as fontes.", "Verificando as manchetes."]


def trat(frase: str) -> str:
    """As falas são escritas com "senhor"; aqui viram o tratamento configurado (JARVIS_TRATAMENTO)."""
    if config.TRATAMENTO == "senhora":
        return frase.replace("senhor", "senhora").replace("Senhor", "Senhora")
    if config.TRATAMENTO == "nenhum":
        frase = frase.replace(", senhor", "").replace("Senhor, ", "").replace("Senhor?", "").strip()
        return frase[:1].upper() + frase[1:]
    return frase


def working(tool: str) -> str:
    return trat(random.choice(NEWS if "news" in tool else WORKING))


def attention() -> str:
    return random.choice([f for f in map(trat, ATTENTION) if f])
