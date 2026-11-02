"""Ferramentas in-process que o Claude pode chamar: o Mac ("mac") e o próprio Jarvis ("jarvis")."""
import asyncio
import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from jarvis import agenda, dados, kpis, news, profundo, telemetry
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


@tool("news_latest", "Últimas manchetes das fontes que o usuário acompanha (sources.json). "
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


@tool("news_digest", "Resumo diário de notícias de dados: as novas das últimas horas, sem repetidas, ordenadas pelos "
      "temas do usuário. Traz título, fonte, link e a descrição do feed, que é só base: resuma com palavras suas e "
      "nunca repita a descrição.", {"type": "object", "properties": {"horas": {"type": "number"}, "n": {"type": "integer"}}})
async def news_digest(args):
    itens = await asyncio.to_thread(news.digest, float(args.get("horas") or 36), int(args.get("n") or 8))
    if not itens:
        return _ok("Nenhuma notícia nova na janela.")
    news.digest_textos = [x for i in itens for x in (i["title"], i["resumo"])]  # base da checagem de cópia
    for i in reversed(itens[:5]):  # os links ficam no feed do painel; a fala só resume
        bus.feed_item(i["title"], "news", i["source"], i["url"])
    return _ok(json.dumps([{"titulo": i["title"], "fonte": i["source"], "link": i["url"],
                            "descricao_do_feed": i["resumo"][:300], "temas": i["temas"]} for i in itens], ensure_ascii=False))


JARVIS_TOOLS = [news_latest, news_article, news_digest, agenda_today, weather_now, remember, recall]


async def _dados(fn, *args, painel: bool = False) -> dict[str, Any]:
    try:
        out = _ok(await asyncio.to_thread(fn, *args))
    except dados.Recusa as exc:
        return _err(str(exc))
    if painel:  # o painel mostra o mesmo que o Claude viu: perfil seguro e agregados
        bus.emit({"type": "data", **dados.sessao.painel()})
    return out


@tool("abrir_arquivo", "Abre um CSV das pastas de dados do usuário (Downloads, Documentos, Mesa) pelo nome falado "
      "ou caminho. Devolve linhas, colunas, tipos e alertas de qualidade, sem valores individuais.",
      {"nome": str})
async def abrir_arquivo(args):
    print(f"  abrir_arquivo {args}", flush=True)
    out = await _dados(dados.sessao.abrir, args["nome"], painel=True)
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
    return await _dados(dados.sessao.agregar, args, painel=True)


@tool("calcular", "Calculadora para variações, projeções e razões entre números já obtidos. Use ponto decimal: "
      "'1765072.7 * 1.125'. Nunca faça conta de cabeça.", {"expressao": str})
async def calcular(args):
    return await _dados(dados.sessao.calcular, args["expressao"])


@tool("glossario_salvar", "Guarda (ou corrige) um termo do glossário de dados do usuário: sigla, coluna ou métrica com a "
      "definição dele. O termo também ajuda a transcrição de voz a acertar a palavra.", {"termo": str, "definicao": str})
async def glossario_salvar(args):
    memory.glossario_salvar(args["termo"], args["definicao"])
    return _ok("Guardado.")


@tool("glossario", "Termos do glossário de dados do usuário com as definições dele. Consulte antes de interpretar uma "
      "métrica ou sigla que ele usa.", {})
async def glossario(_args):
    itens = memory.glossario()
    return _ok("\n".join(f"{t}: {d}" for t, d in itens) if itens else "Glossário vazio.")


@tool("comparar_arquivo", "Compara o arquivo aberto com outra versão dele (pelo nome): linhas iguais, novas e removidas, "
      "colunas novas, totais numéricos, período das datas e categorias que mudaram. Só agregados.", {"nome": str})
async def comparar_arquivo(args):
    return await _dados(dados.sessao.comparar, args["nome"])


@tool("executar_python", "Roda Python isolado (sem rede, sem outros arquivos) sobre o arquivo aberto, já carregado em "
      "`df` (pandas). Use só para o que agregar não faz: testes estatísticos (scipy.stats), correlação, regressão, "
      "distribuições e gráficos. Devolva números com resultado(nome, valor) e gráficos com grafico(titulo) depois de "
      "desenhar com matplotlib (o gráfico aparece no painel). print não volta. Só agregados voltam: textos só se forem "
      "colunas ou categorias com 5+ linhas; toda tabela precisa de uma coluna n (tamanho do grupo); listas soltas param "
      "em 20 itens. Limites: 30 s de CPU, 60 s, 1,5 GB.", {"codigo": str})
async def executar_python(args):
    print(f"  executar_python ({len(args['codigo'])} caracteres)", flush=True)
    return await _dados(dados.sessao.python, args["codigo"], painel=True)


@tool("decisao_anotar", "Anota uma decisão de tratamento de um arquivo (ex.: 'UF nula fica como Não informada'). Ela "
      "volta da próxima vez que o arquivo for aberto. Sem 'arquivo', vale para o arquivo aberto; se a decisão é "
      "sobre outro arquivo (a outra versão de uma comparação), passe o nome dele.",
      {"type": "object", "properties": {"texto": {"type": "string"}, "arquivo": {"type": "string"}}, "required": ["texto"]})
async def decisao_anotar(args):
    if args.get("arquivo"):
        achados = await asyncio.to_thread(dados.localizar, args["arquivo"])
        if not achados:
            return _err("Não achei esse arquivo nas pastas permitidas.")
        nome = achados[0].name
    elif dados.sessao.arquivo:
        nome = dados.sessao.arquivo.name
    else:
        return _err("Nenhum arquivo aberto; diga de qual arquivo é a decisão.")
    memory.decisao_anotar(nome, args["texto"])
    return _ok(f"Anotado em {nome}.")


@tool("arquivos_recentes", "Arquivos de dados criados ou alterados nas últimas horas nas pastas do usuário (só nome, "
      "pasta, tamanho e idade).", {"type": "object", "properties": {"horas": {"type": "number"}}})
async def arquivos_recentes(args):
    itens = await asyncio.to_thread(dados.recentes, float(args.get("horas") or 48))
    return _ok(json.dumps(itens, ensure_ascii=False) if itens else "Nenhum arquivo novo.")


def painel_kpis() -> None:
    bus.emit({"type": "kpis", "itens": [{"nome": k["nome"], "arquivo": k["arquivo"], "ultimo": k["ultimo"]}
                                        for k in kpis.listar()]})


@tool("kpi_criar", "Cria (ou substitui) um monitor de KPI que o Jarvis confere sozinho de hora em hora e avisa falando "
      "quando a regra dispara, sem passar pelo Claude. Regras: queda_pct/alta_pct comparam o último período com a média "
      "dos 'janela' anteriores (exige 'por' com período de data, ex. 'data_venda:dia'); abaixo/acima comparam o último "
      "valor com um limite. O período em curso fica de fora por padrão.",
      {"type": "object", "properties": {
          "nome": {"type": "string", "description": "nome curto, ex.: 'Faturamento diário de SP'"},
          "arquivo": {"type": "string", "description": "nome do arquivo; vale sempre a versão mais recente"},
          "metrica": {"type": "object", "properties": {"funcao": {"type": "string", "enum": list(dados.METRICAS)},
                                                       "coluna": {"type": "string"}}, "required": ["funcao"]},
          "por": {"type": "array", "items": {"type": "string"}},
          "filtros": {"type": "array", "items": _FILTRO},
          "regra": {"type": "object", "properties": {
              "tipo": {"type": "string", "enum": sorted(kpis.TIPOS)}, "valor": {"type": "number"},
              "janela": {"type": "integer"}, "ignorar_periodo_aberto": {"type": "boolean"}},
              "required": ["tipo", "valor"]}},
       "required": ["nome", "arquivo", "metrica", "regra"]})
async def kpi_criar(args):
    try:
        atual = await asyncio.to_thread(kpis.criar, args)
    except dados.Recusa as exc:
        return _err(str(exc))
    except Exception as exc:
        print(f"  kpi_criar falhou: {exc}")
        return _err(f"não consegui calcular a métrica ({type(exc).__name__})")
    painel_kpis()
    # os números do monitor entram na base do validador, como os do agregar
    return _ok(dados.sessao.registrar({"criado": args["nome"], "agora": atual}))


@tool("kpi_listar", "Monitores de KPI ativos, com a regra e a última conferência.", {})
async def kpi_listar(_args):
    itens = kpis.listar()
    return _ok(json.dumps(itens, ensure_ascii=False, default=str) if itens else "Nenhum monitor ativo.")


@tool("kpi_remover", "Desliga um monitor de KPI pelo nome.", {"nome": str})
async def kpi_remover(args):
    ok = memory.kpi_remover(args["nome"])
    painel_kpis()
    return _ok("Removido.") if ok else _err("Não há monitor com esse nome.")


@tool("kpi_conferir", "Confere agora todos os monitores e devolve o estado de cada um.", {})
async def kpi_conferir(_args):
    itens = []
    for k in kpis.listar():
        try:
            r = await asyncio.to_thread(kpis.avaliar, k)
        except Exception as exc:
            r = {"texto": f"{k['nome']}: não consegui conferir ({type(exc).__name__})", "disparou": False}
        itens.append({"nome": k["nome"], "texto": r["texto"], "disparou": r["disparou"], "valor": r.get("valor"),
                      "base": r.get("base"), "variacao_pct": r.get("variacao_pct")})
    return _ok(dados.sessao.registrar(itens) if itens else "Nenhum monitor ativo.")


@tool("analise_profunda", "Abre o modo análise profunda: uma sessão com o plugin analise-dados (notebook Jupyter, "
      "análise guiada, revisão crítica, relatório e painel). Use quando ele pedir análise profunda, notebook ou para "
      "analisar a fundo. 'arquivo': um CSV das pastas de dados (vira um projeto novo, com cópia em dados/); 'pasta': "
      "a pasta de um projeto que ele escolheu. Sem nenhum dos dois, usa o arquivo aberto. Neste modo as linhas do "
      "arquivo vão para a análise (exceção que ele autorizou).",
      {"type": "object", "properties": {"arquivo": {"type": "string"}, "pasta": {"type": "string"}}})
async def analise_profunda(args):
    plugin = profundo.plugin_path()
    if plugin is None:
        return _err("O plugin analise-dados não está instalado no Claude Code.")
    if profundo.estado.ativo:
        return _err(f"O modo profundo já está aberto em {profundo.estado.sessao.projeto}.")
    arquivo = None
    if not args.get("pasta"):
        if args.get("arquivo"):
            achados = await asyncio.to_thread(dados.localizar, args["arquivo"])
            if not achados:
                return _err("Não achei esse arquivo nas pastas de dados.")
            arquivo = achados[0]
        elif dados.sessao.arquivo:
            arquivo = dados.sessao.arquivo
        else:
            return _err("Diga qual arquivo ou pasta analisar.")
    try:
        projeto, origem = await asyncio.to_thread(profundo.preparar, args.get("pasta"), arquivo)
    except ValueError as exc:
        return _err(str(exc))
    profundo.estado.sessao = profundo.Profundo(projeto, plugin)
    profundo.estado.pendente = "/analise-dados:analise"
    bus.feed_item(f"Análise profunda: {projeto.name}", "info", str(projeto).replace(str(Path.home()), "~"))
    return _ok(f"Modo profundo vai começar em {projeto} ({origem}). Assim que esta resposta terminar, o plugin prepara "
               "a pasta (.venv, dados/, saidas/, .claude/), sobe o Jupyter e o notebook abre no navegador; daí em diante "
               "o que ele disser vai para a análise, até ele dizer 'sair do modo profundo'. Diga isso em uma frase.")


DADOS_TOOLS = [abrir_arquivo, perfil_arquivo, agregar, calcular, executar_python, comparar_arquivo, decisao_anotar,
               arquivos_recentes, glossario_salvar, glossario, kpi_criar, kpi_listar, kpi_remover, kpi_conferir,
               analise_profunda]


def servers() -> dict[str, Any]:
    return {
        "mac": create_sdk_mcp_server("mac", tools=MAC_TOOLS),
        "jarvis": create_sdk_mcp_server("jarvis", tools=JARVIS_TOOLS),
        "dados": create_sdk_mcp_server("dados", tools=DADOS_TOOLS),
    }
