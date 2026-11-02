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
# Grupo com menos linhas que isso não vai para o Claude (só agregados reais, decisão de 02/11/2026)
K_ANONIMATO = int(os.getenv("JARVIS_K_ANONIMATO", "5"))

APPS_FILE = ROOT / "apps.json"
SOURCES_FILE = ROOT / "sources.json"
NEWS_INTERVAL_S = int(os.getenv("JARVIS_NEWS_INTERVAL", str(20 * 60)))

for d in (DATA_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)
