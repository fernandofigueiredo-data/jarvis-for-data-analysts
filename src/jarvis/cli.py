"""Um turno pelo terminal: útil para testar o cérebro e as ações sem microfone."""
import sys
import time

from jarvis import dados, router
from jarvis.brain.agent import Brain, BrainError


async def run_text(text: str, speak: bool = False) -> int:
    t = time.time()
    routes = router.route(text)
    if routes:
        replies = [r.run() for r in routes]
        line = " ".join(x for x in replies if x)
        print(f"[rota rápida {', '.join(r.name for r in routes)} · {int((time.time() - t) * 1000)} ms] {line}")
        if speak:
            from jarvis.audio.tts import speak_blocking
            speak_blocking(line)
        return 0
    brain = Brain()
    await brain.start()
    print(f"[claude conectado · {int((time.time() - t) * 1000)} ms]")
    try:
        answer = await brain.ask(text, on_text=lambda d: (sys.stdout.write(d), sys.stdout.flush()),
                                 on_tool=lambda n: print(f"\n  [ferramenta: {n}]"))
        print(f"\n[{int((time.time() - t) * 1000)} ms]")
        if sem_origem := dados.sessao.conferir_turno(answer, text):
            print(f"[números sem origem nos dados] {', '.join(sem_origem)}")
        if speak and answer:
            from jarvis.audio.tts import speak_blocking
            speak_blocking(answer)
    except BrainError as exc:
        print(f"[o Claude não respondeu] {exc}")
        return 1
    finally:
        await brain.stop()
    return 0
