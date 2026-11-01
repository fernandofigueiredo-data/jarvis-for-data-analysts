import pytest

from jarvis.wake import is_stop, split_wake


@pytest.mark.parametrize("text,rest", [
    ("Ei Jarvis, abre o Chrome.", "abre o Chrome"),
    ("Jarvis, que horas são?", "que horas são"),
    ("Oi Jarbas", ""),
    ("Ok, Jarvis. Quais as notícias?", "Quais as notícias"),
])
def test_wake(text, rest):
    woke, after, mid = split_wake(text)
    assert woke and after == rest and not mid


def test_no_wake():
    assert not split_wake("vou ver o filme do homem de ferro")[0]


def test_mid_sentence():
    woke, after, mid = split_wake("aí eu falei ei Jarvis abre o Spotify")
    assert woke and mid and after == "abre o Spotify"


def test_stop():
    assert is_stop("Para.") and is_stop("chega") and not is_stop("para de tocar a música e abre o chrome")


def test_whisper_hears_key():
    assert split_wake("Key Jarvis, coloca um timer de 25 minutos.")[1] == "coloca um timer de 25 minutos"
