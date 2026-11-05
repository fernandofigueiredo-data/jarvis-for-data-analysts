"""Localização precisa do Mac (Wi-Fi/CoreLocation) pelo app auxiliar "Jarvis Localização".

O macOS só entrega a localização a um app com Info.plist que pediu permissão; o Python do Jarvis não é um. O app
auxiliar (localizacao/main.swift) é compilado uma vez em cache/JarvisLocal.app e recompilado só se o código mudar:
cada compilação nova é outro binário, e o macOS pede a permissão de novo.
"""
import hashlib
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from jarvis import config

SRC = Path(__file__).parent / "localizacao"
APP = config.CACHE_DIR / "JarvisLocal.app"
STAMP = APP / "Contents" / "fonte.sha1"
WAIT_S = 20  # com a permissão dada, a resposta vem em poucos segundos; na primeira vez o pedido espera o usuário


def _source_hash() -> str:
    return hashlib.sha1((SRC / "main.swift").read_bytes() + (SRC / "Info.plist").read_bytes()).hexdigest()


def ensure_app() -> Path | None:
    """Compila o app auxiliar se ainda não existe (ou se o código mudou). None se não houver swiftc."""
    digest = _source_hash()
    if STAMP.exists() and STAMP.read_text().strip() == digest:
        return APP
    if not shutil.which("swiftc"):
        return None
    shutil.rmtree(APP, ignore_errors=True)
    (APP / "Contents" / "MacOS").mkdir(parents=True)
    shutil.copy(SRC / "Info.plist", APP / "Contents" / "Info.plist")
    r = subprocess.run(["swiftc", "-O", str(SRC / "main.swift"), "-o", str(APP / "Contents" / "MacOS" / "JarvisLocal")],
                       capture_output=True, text=True)
    if r.returncode:
        print(f"  localização: o app auxiliar não compilou: {r.stderr[-300:]}")
        shutil.rmtree(APP, ignore_errors=True)
        return None
    subprocess.run(["codesign", "-s", "-", "--force", str(APP)], capture_output=True)
    STAMP.write_text(digest)
    return APP


def current(wait: float = WAIT_S) -> dict | None:
    """{"lat", "lon", "acc"} do Mac, ou None (sem permissão, sem resposta a tempo ou sem como compilar o app)."""
    try:
        app = ensure_app()
    except OSError as exc:
        print(f"  localização: {exc}")
        return None
    if app is None:
        return None
    out = config.CACHE_DIR / f"local-{uuid.uuid4().hex}.json"
    subprocess.run(["open", "-n", str(app), "--args", str(out)], capture_output=True)
    fim = time.time() + wait
    try:
        while time.time() < fim:
            if out.exists() and out.stat().st_size:
                time.sleep(0.05)  # o app grava de uma vez; garante a leitura do arquivo inteiro
                r = json.loads(out.read_text())
                if "erro" in r:
                    print(f"  localização do Mac indisponível: {r['erro']}")
                    return None
                return {"lat": float(r["lat"]), "lon": float(r["lon"]), "acc": float(r.get("acc", 0))}
            time.sleep(0.25)
        print("  localização do Mac: sem resposta (a permissão ainda não foi dada?)")
        return None
    finally:
        out.unlink(missing_ok=True)
