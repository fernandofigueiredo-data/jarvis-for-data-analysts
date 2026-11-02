"""Transcrição local com faster-whisper (multilíngue, fixado em português)."""
import threading
import time

import numpy as np

from jarvis import config, dados
from jarvis.memory import memory

NO_SPEECH_MAX = 0.6  # acima disso o próprio Whisper acha que não era fala
# Ajuda o Whisper a escrever os nomes certos nos comandos
PROMPT = "Jarvis, abre o Chrome. Aumenta o volume. Coloca um timer de cinco minutos. Quais as notícias do Data Hackers?"
VOCAB_MAX = 400  # caracteres; o Whisper só aproveita o fim de um prompt longo (~224 tokens)


def build_prompt() -> str:
    """Prompt fixo + termos do glossário + colunas do arquivo aberto. No teste da P6 (voz sintética), pôr os termos
    no prompt levou o acerto de siglas e colunas de 76% para 87% sem mudar a latência."""
    termos = [t for t, _ in memory.glossario(40)] + [c.replace("_", " ") for c in dados.sessao.nomes_colunas]
    vocab = ""
    for t in dict.fromkeys(termos):  # sem repetir, na ordem
        if len(vocab) + len(t) + 2 > VOCAB_MAX:
            break
        vocab += (", " if vocab else "") + t
    return f"{PROMPT} Termos de dados: {vocab}." if vocab else PROMPT


class Transcriber:
    def __init__(self) -> None:
        self.model = None
        self.ready = threading.Event()

    def load(self) -> None:
        from faster_whisper import WhisperModel
        self.model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
        self.ready.set()

    def transcribe(self, audio: np.ndarray, prompt: bool = True) -> tuple[str, int]:
        self.ready.wait()
        t = time.time()
        segs, _ = self.model.transcribe(audio, language=config.LANGUAGE, beam_size=1, vad_filter=True,
                                        initial_prompt=build_prompt() if prompt else None)
        text = " ".join(s.text.strip() for s in segs if s.no_speech_prob <= NO_SPEECH_MAX).strip()
        return text, int((time.time() - t) * 1000)


stt = Transcriber()
