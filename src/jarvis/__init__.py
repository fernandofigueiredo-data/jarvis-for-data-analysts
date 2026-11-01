"""Jarvis: assistente pessoal de voz para o Mac."""
import argparse
import asyncio
import sys


def main() -> None:
    ap = argparse.ArgumentParser(prog="jarvis")
    ap.add_argument("--text", help="roda um turno com este texto, sem microfone nem painel")
    ap.add_argument("--speak", action="store_true", help="com --text, também fala a resposta")
    ap.add_argument("--no-window", action="store_true", help="não abre a janela; painel em http://127.0.0.1:8787")
    ap.add_argument("--writes", action="store_true", help="libera ações que mudam o mundo (Bash, enviar, apagar)")
    ap.add_argument("--mode", choices=["wake", "ptt", "off"], default="wake",
                    help="wake = sempre ouvindo 'Ei Jarvis'; ptt = segure o Option direito; off = sem microfone")
    args = ap.parse_args()
    if args.writes:
        import os
        os.environ["JARVIS_ALLOW_WRITES"] = "1"
    if args.text:
        from jarvis.cli import run_text
        sys.exit(asyncio.run(run_text(args.text, speak=args.speak)))
    from jarvis.app import run
    run(mode=args.mode, window=not args.no_window)
