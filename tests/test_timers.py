import pytest

from jarvis.mac.timers import parse_duration, parse_reminder, say_duration


@pytest.mark.parametrize("text,secs", [
    ("vinte e cinco minutos", 1500),
    ("meia hora", 1800),
    ("uma hora e meia", 5400),
    ("5 min", 300),
    ("dois minutos e meio", 150),
    ("1 hora e 10 minutos", 4200),
    ("trinta segundos", 30),
    ("sem tempo nenhum", None),
])
def test_parse_duration(text, secs):
    assert parse_duration(text) == secs


def test_parse_reminder_both_orders():
    assert parse_reminder("me lembra de tirar o bolo do forno em 40 minutos") == "tirar o bolo do forno"
    assert parse_reminder("me lembra daqui a 10 minutos de ligar pro João") == "ligar pro joão"


def test_say_duration():
    assert say_duration(90) == "1 minuto e 30 segundos"
    assert say_duration(3900) == "1 hora e 5 minutos"
