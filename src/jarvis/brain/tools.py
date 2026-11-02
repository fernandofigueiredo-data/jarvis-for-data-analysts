"""Ferramentas in-process que o Claude pode chamar: o Mac ("mac") e o próprio Jarvis ("jarvis")."""
import asyncio
import json
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from jarvis import agenda, dados, news, telemetry
from jarvis.events import bus
from jarvis.mac import actions as mac
from jarvis.mac.timers import say_duration, timers
from jarvis.memory import memory


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _err(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


async def _run(fn, *args) -> dict[str, Any]:
    try:
        return _ok(await asyncio.to_thread(fn, *args))
    except KeyError as exc:
        return _err(f"App desconhecido: {exc}. Apps disponíveis: {', '.join(mac.APPS)}")
    except Exception as exc:
        return _err(str(exc))


APP = {"type": "object", "properties": {"app": {"type": "string", "enum": list(mac.APPS),
                                                "description": "chave do app em apps.json"}},
       "required": ["app"]}


@tool("list_apps", "Lista os apps que o Jarvis sabe controlar (chave e nome).", {})
async def list_apps(_args):
    return _ok(json.dumps({k: a.name for k, a in mac.APPS.items()}, ensure_ascii=False))


@tool("open_app", "Abre um app do Mac.", APP)
async def open_app(args):
    return await _run(mac.open_app, args["app"])


@tool("quit_app", "Fecha um app do Mac.", APP)
async def quit_app(args):
    return await _run(mac.quit_app, args["app"])


@tool("focus_app", "Traz um app para a frente.", APP)
async def focus_app(args):
    return await _run(mac.focus_app, args["app"])


@tool("hide_app", "Oculta um app.", APP)
async def hide_app(args):
    return await _run(mac.hide_app, args["app"])


@tool("set_volume", "Define o volume do Mac (0 a 100) ou muda relativo com delta.",
      {"type": "object", "properties": {"level": {"type": "integer"}, "delta": {"type": "integer"}}})
async def set_volume(args):
    if "level" in args:
        return await _run(mac.set_volume, args["level"])
    return await _run(mac.volume_step, args.get("delta", 15))


@tool("mute", "Liga (on=true) ou desliga o mudo.", {"on": bool})
async def mute(args):
    return await _run(mac.mute, args["on"])


@tool("media", "Controla a música (Spotify se aberto, senão Música).",
      {"type": "object", "properties": {"action": {"type": "string", "enum": ["play", "pause", "next", "previous"]}},
       "required": ["action"]})
async def media(args):
    return await _run(mac.media, args["action"])


@tool("dark_mode", "Modo escuro: on, off ou toggle.",
      {"type": "object", "properties": {"mode": {"type": "string", "enum": ["on", "off", "toggle"]}}, "required": ["mode"]})
async def dark_mode(args):
    return await _run(mac.dark_mode, {"on": True, "off": False, "toggle": None}[args["mode"]])


@tool("lock_screen", "Bloqueia a tela do Mac.", {})
async def lock_screen(_args):
    return await _run(mac.lock_screen)


@tool("open_url", "Abre um site no navegador (browser opcional: chrome ou safari).",
      {"type": "object", "properties": {"url": {"type": "string"}, "browser": {"type": "string", "enum": ["chrome", "safari"]}},
       "required": ["url"]})
async def open_url(args):
    url = args["url"] if args["url"].startswith("http") else "https://" + args["url"]
    return await _run(mac.open_url, url, args.get("browser"))


@tool("timer_set", "Cria um timer ou lembrete. label só para lembretes (o que lembrar).",
      {"type": "object", "properties": {"seconds": {"type": "integer"}, "label": {"type": "string"}}, "required": ["seconds"]})
async def timer_set(args):
    timers.add(int(args["seconds"]), args.get("label"))
    return _ok(f"Timer de {say_duration(args['seconds'])} criado.")


@tool("timer_list", "Lista timers e lembretes ativos com o tempo restante.", {})
async def timer_list(_args):
    items = timers.snapshot()
    if not items:
        return _ok("Nenhum timer ativo.")
    return _ok("\n".join(f"{t['label'] or 'timer'}: faltam {say_duration(t['left'])}" for t in items))


@tool("timer_cancel", "Cancela o timer mais recente, ou todos.", {"all": bool})
async def timer_cancel(args):
    return _ok(f"{timers.cancel(bool(args.get('all')))} timer(s) cancelado(s).")


MAC_TOOLS = [list_apps, open_app, quit_app, focus_app, hide_app, set_volume, mute, media, dark_mode,
             lock_screen, open_url, timer_set, timer_list, timer_cancel]


@tool("news_latest", "Últimas manchetes das fontes que o usuário acompanha (Educadados, Data Hackers). "
      "source filtra pelo nome da fonte; refresh=true busca agora antes de responder.",
      {"type": "object", "properties": {"source": {"type": "string"}, "n": {"type": "integer"},
                                        "refresh": {"type": "boolean"}}})
async def news_latest(args):
    print(f"  news_latest {args}", flush=True)
    if args.get("refresh") or not memory.latest_news(n=1):
        await asyncio.to_thread(news.refresh)
    n = int(args.get("n") or 5)
    if args.get("source"):
        grouped = {args["source"]: memory.latest_news(args["source"], n)}
    else:  # sem filtro: as mais recentes de CADA fonte, para nenhuma sumir atrás de outra
        grouped = {src["nome"]: memory.latest_news(src["nome"], n) for src in news.load_sources()}
    grouped = {k: [{"title": i["title"], "url": i["url"]} for i in v] for k, v in grouped.items() if v}
    if not grouped:
        return _ok("Nenhuma notícia encontrada para essa fonte.")
    return _ok(json.dumps(grouped, ensure_ascii=False))


@tool("news_article", "Baixa e devolve o texto de um artigo para resumir.", {"url": str})
async def news_article(args):
    try:
        return _ok(await asyncio.to_thread(news.article_text, args["url"]) or "Não consegui extrair o texto.")
    except Exception as exc:
        return _err(str(exc))


@tool("agenda_today", "Compromissos de hoje do app Calendário.", {})
async def agenda_today(_args):
    events = await asyncio.to_thread(agenda.today, 15)
    if events is None:
        return _ok("A agenda ainda está sendo lida do Calendário. Diga isso e sugira perguntar de novo em um minuto.")
    return _ok(json.dumps(events, ensure_ascii=False) if events else "Nenhum compromisso hoje.")


@tool("weather_now", "Cidade atual do usuário e o clima agora (temperatura e condição).", {})
async def weather_now(_args):
    place = await asyncio.to_thread(telemetry.place)
    w = await asyncio.to_thread(telemetry.weather)
    if not w:
        return _err("Clima indisponível agora.")
    return _ok(json.dumps({"cidade": place["name"], **w}, ensure_ascii=False))


@tool("remember", "Guarda um fato sobre o usuário para lembrar em conversas futuras.", {"text": str})
async def remember(args):
    memory.remember(args["text"])
    return _ok("Guardado.")


@tool("recall", "Lista os fatos guardados sobre o usuário.", {})
async def recall(_args):
    items = memory.memories()
    return _ok("\n".join(items) if items else "Nada guardado ainda.")


JARVIS_TOOLS = [news_latest, news_article, agenda_today, weather_now, remember, recall]


async def _dados(fn, *args) -> dict[str, Any]:
    try:
        return _ok(await asyncio.to_thread(fn, *args))
    except dados.Recusa as exc:
        return _err(str(exc))


@tool("abrir_arquivo", "Abre um CSV das pastas de dados do usuário (Downloads, Documentos, Mesa) pelo nome falado "
      "ou caminho. Devolve linhas, colunas, tipos e alertas de qualidade, sem valores individuais.",
      {"nome": str})
async def abrir_arquivo(args):
    print(f"  abrir_arquivo {args}", flush=True)
    out = await _dados(dados.sessao.abrir, args["nome"])
    if not out.get("is_error") and dados.sessao.arquivo:
        bus.feed_item(f"Arquivo aberto: {dados.sessao.arquivo.name}", "info", "Dados")
    return out


@tool("perfil_arquivo", "Perfil do arquivo aberto: linhas, colunas, tipos, nulos, estatísticas e alertas.", {})
async def perfil_arquivo(_args):
    return await _dados(dados.sessao.perfil)


_FILTRO = {"type": "object", "properties": {
    "coluna": {"type": "string"},
    "op": {"type": "string", "enum": sorted(dados.OPERADORES)},
    "valor": {"description": "número, texto ou data AAAA-MM-DD; lista para 'in' e [início, fim] para 'entre'"}},
    "required": ["coluna", "op", "valor"]}


@tool("agregar", "Única forma de obter números do arquivo aberto. Calcula métricas agrupadas; grupos com menos de "
      "K linhas são omitidos. Em 'por', uma coluna de data aceita período: 'data_venda:mes' (ano, trimestre, mes, "
      "dia_semana, dia). Colunas de dado pessoal (CPF, nome, e-mail) só aceitam contagem e distintos.",
      {"type": "object", "properties": {
          "metricas": {"type": "array", "items": {"type": "object", "properties": {
              "funcao": {"type": "string", "enum": list(dados.METRICAS)},
              "coluna": {"type": "string", "description": "omita em contagem para contar linhas"}},
              "required": ["funcao"]}},
          "por": {"type": "array", "items": {"type": "string"}},
          "filtros": {"type": "array", "items": _FILTRO},
          "ordenar": {"type": "string", "description": "nome de uma coluna do resultado; '-' na frente para decrescente"},
          "limite": {"type": "integer"}},
       "required": ["metricas"]})
async def agregar(args):
    return await _dados(dados.sessao.agregar, args)


@tool("calcular", "Calculadora para variações, projeções e razões entre números já obtidos. Use ponto decimal: "
      "'1765072.7 * 1.125'. Nunca faça conta de cabeça.", {"expressao": str})
async def calcular(args):
    return await _dados(dados.sessao.calcular, args["expressao"])


DADOS_TOOLS = [abrir_arquivo, perfil_arquivo, agregar, calcular]


def servers() -> dict[str, Any]:
    return {
        "mac": create_sdk_mcp_server("mac", tools=MAC_TOOLS),
        "jarvis": create_sdk_mcp_server("jarvis", tools=JARVIS_TOOLS),
        "dados": create_sdk_mcp_server("dados", tools=DADOS_TOOLS),
    }
