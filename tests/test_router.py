import pytest

from jarvis.router import route


@pytest.mark.parametrize("text,name,args", [
    ("Abre o Chrome", "app_open", {"app": "chrome"}),
    ("abre o vs code", "app_open", {"app": "vscode"}),
    ("Jarvis, fecha o WhatsApp, por favor", "app_quit", {"app": "whatsapp"}),
    ("abre o zap", "app_open", {"app": "whatsapp"}),
    ("vai pro Notion", "app_focus", {"app": "notion"}),
    ("aumenta o volume", "volume_up", {}),
    ("abaixa o som", "volume_down", {}),
    ("volume em 30", "volume_set", {}),
    ("muta", "mute", {}),
    ("próxima música", "media_next", {}),
    ("pausa", "media_pause", {}),
    ("liga o modo escuro", "dark_on", {}),
    ("bloqueia a tela", "lock", {}),
    ("que horas são?", "time", {}),
    ("cancela o timer", "timer_cancel", {}),
    ("quanto tempo falta?", "timer_check", {}),
])
def test_single(text, name, args):
    routes = route(text)
    assert routes and len(routes) == 1
    assert routes[0].name == name
    for k, v in args.items():
        assert routes[0].args[k] == v


def test_timer_set():
    r = route("coloca um timer de vinte e cinco minutos")
    assert r and r[0].name == "timer_set" and r[0].args["secs"] == 1500


def test_reminder():
    r = route("me lembra daqui a 20 minutos de ligar pra minha mãe")
    assert r and r[0].args == {"secs": 1200, "label": "ligar pra minha mãe"}


def test_compound():
    r = route("abre o Chrome e aumenta o volume")
    assert r and [x.name for x in r] == ["app_open", "volume_up"]


def test_mute_speaks_first():
    assert route("silencia")[0].speak_first


@pytest.mark.parametrize("text", [
    "qual a capital da Austrália?",
    "abre o arquivo do relatório de vendas",
    "quais as notícias de hoje?",
    "me lembra de comprar pão",  # sem duração: vai para o Claude
    "",
])
def test_falls_through_to_claude(text):
    assert route(text) is None
