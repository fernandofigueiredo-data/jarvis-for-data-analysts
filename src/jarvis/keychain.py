"""Chaves de API no Keychain do macOS, com o .env como alternativa (o .env vence)."""
import os
import subprocess

SERVICE = "com.jarvis.keys"
KEY_NAMES = ("ELEVENLABS_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY")


def _keychain(name: str) -> str | None:
    r = subprocess.run(["security", "find-generic-password", "-a", name, "-s", SERVICE, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def get_secret(name: str) -> str | None:
    return os.getenv(name) or _keychain(name)


def save_secret(name: str, value: str) -> None:
    if name not in KEY_NAMES:
        raise ValueError(f"chave desconhecida: {name}")
    value = value.strip()
    if not value:
        return
    r = subprocess.run(["security", "add-generic-password", "-U", "-a", name, "-s", SERVICE, "-w", value],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "não consegui salvar no Keychain")
