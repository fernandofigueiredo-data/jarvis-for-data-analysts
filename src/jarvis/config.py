"""Configuração central. Tudo pode ser sobrescrito por variáveis de ambiente ou pelo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.getenv("JARVIS_DATA_DIR", ROOT / "data"))
CACHE_DIR = Path(os.getenv("JARVIS_CACHE_DIR", ROOT / "cache"))
LOG_FILE = Path.home() / "Library/Logs/Jarvis.log"
UI_DIST = ROOT / "ui" / "dist"

MODEL = os.getenv("JARVIS_MODEL", "claude-sonnet-5-5")
EFFORT = os.getenv("JARVIS_EFFORT", "low")
MAX_TURNS = int(os.getenv("JARVIS_MAX_TURNS", "24"))
# Ações que mudam o mundo (Bash, escrever arquivos, enviar e-mail) só com isto ligado
ALLOW_WRITES = os.getenv("JARVIS_ALLOW_WRITES") == "1"

HOST = "127.0.0.1"
PORT = int(os.getenv("JARVIS_PORT", "8787"))

SAMPLE_RATE = 16000
WHISPER_MODEL = os.getenv("JARVIS_WHISPER_MODEL", "small")
LANGUAGE = "pt"
TTS_VOICE = os.getenv("JARVIS_VOICE", "Luciana")  # voz do macOS em pt-BR
ELEVEN_VOICE_ID = os.getenv("JARVIS_ELEVEN_VOICE_ID", "")

LOCATION = os.getenv("JARVIS_LOCATION", "")  # "São Paulo" etc.; vazio = descobre pelo IP

# Arquivos de dados: o Jarvis só abre o que estiver nestas pastas (separadas por ":")
DATA_FOLDERS = [Path(p).expanduser() for p in
                os.getenv("JARVIS_PASTAS_DADOS", "~/Downloads:~/Documents:~/Desktop").split(os.pathsep) if p]
# Arquivos arrastados para o painel; sempre permitida
UPLOAD_DIR = DATA_DIR / "arquivos"
UPLOAD_MAX_BYTES = int(os.getenv("JARVIS_UPLOAD_MAX_MB", "1024")) * 1024 * 1024
# Grupo com menos linhas que isso não vai para o Claude (só agregados reais, decisão de 02/11/2026)
K_ANONIMATO = int(os.getenv("JARVIS_K_ANONIMATO", "5"))

# Python isolado (fase 4): limites de CPU, relógio e memória por execução
PY_CPU_S = int(os.getenv("JARVIS_PY_CPU_S", "30"))
PY_PRAZO_S = float(os.getenv("JARVIS_PY_PRAZO_S", "60"))
PY_MEM_MB = int(os.getenv("JARVIS_PY_MEM_MB", "1536"))
# Monitor de KPIs: de quanto em quanto tempo as regras são conferidas
KPI_INTERVALO_S = int(os.getenv("JARVIS_KPI_INTERVALO_MIN", "60")) * 60

# Modo análise profunda (fase 5): plugin analise-dados; vazio = o instalado pelo Claude Code
PLUGIN_ANALISE = os.getenv("JARVIS_PLUGIN_ANALISE", "")
ANALISES_DIR = Path(os.getenv("JARVIS_PASTA_ANALISES", "~/Documents/Análises Jarvis")).expanduser()
EFFORT_PROFUNDO = os.getenv("JARVIS_EFFORT_PROFUNDO", "medium")
ABRIR_NOTEBOOK = os.getenv("JARVIS_ABRIR_NOTEBOOK", "1") == "1"

APPS_FILE = ROOT / "apps.json"
SOURCES_FILE = ROOT / "sources.json"
NEWS_INTERVAL_S = int(os.getenv("JARVIS_NEWS_INTERVAL", str(20 * 60)))
# Resumo diário de notícias de dados: horário HH:MM (vazio desliga) e temas que sobem no ranking
DIGEST_TIME = os.getenv("JARVIS_RESUMO_HORA", "08:00")
NEWS_THEMES = os.getenv("JARVIS_NOTICIAS_TEMAS", "análise de dados, ciência de dados, engenharia de dados, SQL, "
                        "pandas, DuckDB, dbt, Power BI, Databricks, analytics, dashboard, BI, estatística, LLM")

for d in (DATA_DIR, CACHE_DIR, UPLOAD_DIR):
    d.mkdir(parents=True, exist_ok=True)
