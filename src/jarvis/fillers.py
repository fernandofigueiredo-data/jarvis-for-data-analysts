"""Frases curtas ditas quando uma ferramenta começa, para o silêncio de alguns segundos não parecer travamento."""
import random

WORKING = ["Pesquisando.", "Um instante, senhor.", "Consultando.", "Verificando.", "Buscando.", "Processando."]
ATTENTION = ["Sim, senhor?", "Senhor?", "Pois não.", "Estou ouvindo."]
NEWS = ["Consultando as fontes.", "Verificando as manchetes."]


def working(tool: str) -> str:
    return random.choice(NEWS if "news" in tool else WORKING)


def attention() -> str:
    return random.choice(ATTENTION)
