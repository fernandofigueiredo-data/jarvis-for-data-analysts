"""Python gerado pelo Claude, rodando isolado no Seatbelt do macOS, para o que o SQL não faz (testes, regressão, gráficos).

Isolamento (prova de conceito em _pocs/p4_isolamento): `deny default`; lê só o Python do Jarvis, o Parquet do arquivo
aberto e a própria pasta de trabalho; escreve só nela; sem rede e sem executar outros programas. O Seatbelt não
limita memória (o macOS recusa RLIMIT_AS), então um vigia mede o processo e o mata acima do limite; CPU fica no
RLIMIT_CPU e o relógio no vigia.

Só agregados para o Claude (decisão de 02/11/2026): o código vê os dados inteiros, mas a saída de texto fica no Mac.
Volta só o que passar por resultado(), com textos limitados a nomes de colunas, categorias com ≥ K linhas, datas e
números, e com teto de quantidade, para nenhuma tabela crua sair por engano.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import psutil

from jarvis import config

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
OMITIDO = "‹omitido›"
MAX_NUMEROS = 300
MAX_ITENS = 20  # lista solta (quantis, histograma); tabela (lista de registros) segue a regra da contagem
CONTAGEM = ("n", "linhas", "contagem", "count", "qtd", "tamanho")
CHAVE = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")  # chaves em snake_case escritas pelo código, não vindas dos dados
DATA = re.compile(r"^\d{4}-\d{2}(-\d{2})?([ T]\d{2}:\d{2}(:\d{2})?)?$")
NUMERO = re.compile(r"^-?\d+([.,]\d+)?%?$")

PERFIL = """(version 1)
(deny default)
(import "system.sb")
(allow process-exec (literal "{exe}") (literal "{exe_real}"))
(allow file-read*
  (subpath "/System") (subpath "/usr/lib") (subpath "/usr/share") (subpath "/private/var/db/dyld")
  (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random")
  (subpath "{base}") (subpath "{venv}") (subpath "{dados}") (subpath "{mpl}") (subpath "{work}"))
(allow file-read-metadata)
(allow file-write* (subpath "{work}") (literal "/dev/null"))
(allow sysctl-read)
"""

HARNESS = r'''
import json, os, re, resource, sys, traceback
resource.setrlimit(resource.RLIMIT_CPU, ({cpu}, {cpu}))
AQUI = os.path.dirname(os.path.abspath(__file__))
saida = {{"resultados": {{}}, "graficos": [], "erro": None}}

def _simples(v):
    import numpy as np, pandas as pd
    if isinstance(v, pd.DataFrame):
        return _simples(v.reset_index().to_dict("records") if not isinstance(v.index, pd.RangeIndex) else v.to_dict("records"))
    if isinstance(v, pd.Series):
        if isinstance(v.index, pd.RangeIndex):  # índice 0, 1, 2…: são linhas, não grupos
            return [_simples(x) for x in v]
        return {{str(k): _simples(x) for k, x in v.items()}}
    if isinstance(v, dict):
        return {{str(k): _simples(x) for k, x in v.items()}}
    if isinstance(v, (list, tuple, set, np.ndarray)):
        return [_simples(x) for x in v]
    if isinstance(v, np.generic):
        return v.item()
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    return str(v)

def resultado(nome, valor):
    """Único caminho de volta para o Claude. Use agregados: médias, testes, coeficientes, tabelas por grupo."""
    saida["resultados"][str(nome)] = _simples(valor)

def grafico(titulo=None, fig=None):
    """Salva a figura atual do matplotlib; ela aparece no painel do Jarvis (não vai para o Claude)."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, ScalarFormatter
    f = fig or plt.gcf()
    br = FuncFormatter(lambda v, _: f"{{v:,.0f}}".replace(",", ".") if abs(v) >= 1000 else f"{{v:g}}".replace(".", ","))
    for ax in f.axes:  # milhar e decimal em pt-BR no lugar do "1e6"
        for eixo in (ax.xaxis, ax.yaxis):
            if isinstance(eixo.get_major_formatter(), ScalarFormatter):
                eixo.set_major_formatter(br)
        if titulo and not ax.get_title():
            ax.set_title(titulo, loc="left", fontsize=10, color="#334155")
    nome = f"grafico_{{len(saida['graficos'])}}.png"
    f.savefig(os.path.join(AQUI, nome), dpi=110, bbox_inches="tight")
    plt.close(f)
    saida["graficos"].append({{"arquivo": nome, "titulo": titulo}})

try:
    import numpy as np, pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    # estilo do painel: série única em #0891b2 (validada contra fundo claro e escuro), grade discreta, sem moldura
    matplotlib.rcParams.update({{
        "axes.prop_cycle": matplotlib.cycler(color=["#0891b2", "#7c3aed", "#d97706", "#059669", "#db2777"]),
        "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#cbd5e1",
        "axes.grid": True, "grid.color": "#e2e8f0", "grid.linewidth": 0.8, "axes.axisbelow": True,
        "font.size": 9, "axes.labelcolor": "#475569", "xtick.color": "#475569", "ytick.color": "#475569",
        "figure.figsize": (6.4, 3.6), "lines.linewidth": 2, "axes.formatter.useoffset": False,
    }})
    df = pd.read_parquet({parquet!r})
    codigo = open(os.path.join(AQUI, "codigo.py"), encoding="utf-8").read()
    exec(compile(codigo, "codigo.py", "exec"), {{"df": df, "pd": pd, "np": np, "resultado": resultado,
                                                 "grafico": grafico, "__name__": "__main__"}})
except BaseException as e:
    linha = next((f.lineno for f in reversed(traceback.extract_tb(e.__traceback__)) if f.filename == "codigo.py"), None)
    # a mensagem pode citar o conteúdo de uma célula ("could not convert string 'Ana'"): o que está entre aspas sai
    msg = re.sub(r"'[^']*'|\"[^\"]*\"", "'…'", str(e))[:200]
    saida["erro"] = {{"tipo": type(e).__name__, "linha": linha, "mensagem": msg}}
with open(os.path.join(AQUI, "saida.json"), "w", encoding="utf-8") as f:
    json.dump(saida, f, default=str)
'''


class Limites:
    def __init__(self) -> None:
        self.numeros = 0
        self.omitidos = 0
        self.cortados = 0
        self.recusas: list[str] = []


def sanear(v, rotulos: set[str], lim: Limites):
    """O que pode voltar ao Claude: números (com teto), textos conhecidos, chaves em snake_case."""
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        lim.numeros += 1
        if lim.numeros > MAX_NUMEROS:
            lim.cortados += 1
            return OMITIDO
        return round(v, 6) if isinstance(v, float) else v
    if isinstance(v, str):
        if v in rotulos or DATA.match(v) or NUMERO.match(v):
            return v
        lim.omitidos += 1
        return OMITIDO
    if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
        return _tabela(v, rotulos, lim)
    if isinstance(v, list):
        if len(v) > MAX_ITENS:
            lim.cortados += len(v) - MAX_ITENS
        return [sanear(x, rotulos, lim) for x in v[:MAX_ITENS]]
    if isinstance(v, dict):
        out = {}
        for i, (k, x) in enumerate(v.items()):
            if i >= MAX_ITENS:
                lim.cortados += len(v) - MAX_ITENS
                break
            chave = k if k in rotulos or CHAVE.match(k) else f"{OMITIDO}{i}"
            if chave != k:
                lim.omitidos += 1
            out[chave] = sanear(x, rotulos, lim)
        return out
    lim.omitidos += 1
    return OMITIDO


def _tabela(linhas: list[dict], rotulos: set[str], lim: Limites):
    """Tabela só sai com uma coluna de contagem (o n de cada linha), e linhas com n < K ficam de fora.
    Sem ela, é indistinguível de linhas cruas (df.head()), então é recusada."""
    k = config.K_ANONIMATO
    chave = next((c for c in CONTAGEM if all(isinstance(r.get(c), (int, float)) for r in linhas)), None)
    if chave is None:
        lim.recusas.append(f"tabela sem coluna de contagem ({', '.join(CONTAGEM)}): inclua o tamanho de cada grupo")
        return OMITIDO
    ok = [r for r in linhas if r[chave] >= k]
    lim.omitidos += len(linhas) - len(ok)
    if len(ok) > MAX_ITENS:
        lim.cortados += len(ok) - MAX_ITENS
    return [sanear(r, rotulos, lim) for r in ok[:MAX_ITENS]]


def _perfil(work: Path, parquet: Path) -> str:
    exe = Path(sys.executable)
    return PERFIL.format(exe=exe, exe_real=exe.resolve(), base=Path(sys.base_prefix).resolve(),
                         venv=Path(sys.prefix).resolve(), dados=parquet.parent.resolve(), mpl=_mpl().resolve(),
                         work=work.resolve())


def _mpl() -> Path:
    """Cache de fontes do matplotlib, montado uma vez fora do sandbox (código do próprio Jarvis) e lido por ele.
    Sem isso, cada execução refaz o cache: ~8 s no primeiro gráfico."""
    pasta = config.CACHE_DIR / "mpl"
    if not any(pasta.glob("fontlist*.json")):
        pasta.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-I", "-c", "import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot"],
                       env={"MPLCONFIGDIR": str(pasta), "PATH": "/usr/bin:/bin"}, capture_output=True, timeout=120)
    return pasta


def _vigiar(proc: subprocess.Popen, mem_mb: int, prazo_s: float) -> str | None:
    """Mata o processo (e filhos) acima da memória ou do prazo. Devolve o motivo, ou None se terminou sozinho."""
    inicio = time.monotonic()
    try:
        p = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return None
    while proc.poll() is None:
        try:
            rss = sum(x.memory_info().rss for x in [p, *p.children(recursive=True)])
        except psutil.NoSuchProcess:
            break
        motivo = ("memoria" if rss > mem_mb * 2**20 else
                  "tempo" if time.monotonic() - inicio > prazo_s else None)
        if motivo:
            for x in [*p.children(recursive=True), p]:
                try:
                    x.kill()
                except psutil.NoSuchProcess:
                    pass
            proc.wait()
            return motivo
        time.sleep(0.05)
    return None


def executar(codigo: str, parquet: Path, rotulos: set[str], *, cpu_s: int | None = None, prazo_s: float | None = None,
             mem_mb: int | None = None) -> dict:
    """Roda `codigo` (com `df` já carregado) no sandbox. Devolve só o que pode ir ao Claude e os gráficos para o painel."""
    cpu_s = cpu_s or config.PY_CPU_S
    prazo_s = prazo_s or config.PY_PRAZO_S
    mem_mb = mem_mb or config.PY_MEM_MB
    work = Path(tempfile.mkdtemp(prefix="jarvis_py_"))
    t0 = time.perf_counter()
    try:
        (work / "codigo.py").write_text(codigo, encoding="utf-8")
        (work / "harness.py").write_text(HARNESS.format(cpu=cpu_s, parquet=str(parquet)), encoding="utf-8")
        env = {"PATH": "/usr/bin:/bin", "HOME": str(work), "MPLCONFIGDIR": str(_mpl()), "MPLBACKEND": "Agg",
               "OPENBLAS_NUM_THREADS": "2", "OMP_NUM_THREADS": "2", "PYTHONDONTWRITEBYTECODE": "1"}
        with (work / "saida.log").open("wb") as log:
            proc = subprocess.Popen([SANDBOX_EXEC, "-p", _perfil(work, parquet), sys.executable, "-I", str(work / "harness.py")],
                                    cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
            motivo = _vigiar(proc, mem_mb, prazo_s)
        segundos = round(time.perf_counter() - t0, 2)
        if motivo == "memoria":
            return {"erro": f"interrompido: passou de {mem_mb} MB de memória", "segundos": segundos}
        if motivo == "tempo":
            return {"erro": f"interrompido: passou de {prazo_s:.0f} s", "segundos": segundos}
        try:
            saida = json.loads((work / "saida.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # morto pelo RLIMIT_CPU ou falha antes do harness escrever; o log fica só no terminal do daemon
            print(f"  python isolado sem saída (código {proc.returncode}): "
                  f"{(work / 'saida.log').read_text(errors='replace')[-300:]}")
            return {"erro": f"o processo terminou sem resultado (código {proc.returncode}; limite de CPU é {cpu_s} s)",
                    "segundos": segundos}
        lim = Limites()
        out = {"resultados": sanear(saida["resultados"], rotulos, lim), "segundos": segundos}
        if saida["erro"]:
            out["erro"] = saida["erro"]
        if lim.omitidos or lim.cortados or lim.recusas:
            out["aviso"] = (f"{lim.omitidos} item(ns) omitido(s) (texto desconhecido ou grupo com menos de "
                            f"{config.K_ANONIMATO} linhas) e {lim.cortados} acima do teto; devolva só agregados")
            if lim.recusas:
                out["recusas"] = sorted(set(lim.recusas))
        destino = config.CACHE_DIR / "graficos"
        destino.mkdir(exist_ok=True)
        graficos = []
        for g in saida["graficos"][:4]:
            nome = f"{uuid.uuid4().hex}.png"
            shutil.copy(work / g["arquivo"], destino / nome)
            graficos.append({"url": f"/api/graficos/{nome}", "titulo": g["titulo"] if g["titulo"] in rotulos or
                             (g["titulo"] and len(g["titulo"]) <= 80) else None})
        out["graficos"] = graficos
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)
