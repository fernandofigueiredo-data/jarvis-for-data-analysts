"""Microfone: detecção de fala por energia (VAD) e recorte de frases.

Um piso de ruído móvel acompanha o ambiente; acima de um múltiplo dele começa uma frase, com
alguns blocos de "pre-roll" para não comer a primeira sílaba. Ideia do hey-jev, reescrita aqui.
"""
import collections
import queue
import threading

import numpy as np
import sounddevice as sd

from jarvis import config

BLOCK = 1600  # 100 ms a 16 kHz
END_SILENCE = 8  # 0,8 s de silêncio fecha a frase
MAX_BLOCKS = 150  # 15 s no máximo por frase
MIN_SPEECH = 4  # menos que 0,4 s de voz é ruído


class Recorder:
    def __init__(self, device: str | int | None = None) -> None:
        self.segments: queue.Queue[np.ndarray] = queue.Queue()
        self.listening = False  # modo "sempre ouvindo": recorta frases
        self.held = False  # push-to-talk: grava tudo enquanto segurado
        self.guard = False  # ele está falando: exige mais energia para disparar (eco do alto-falante)
        self.level = 0.0  # 0..1 para a forma de onda do painel
        self.noise = 0.005
        self._frames: list[np.ndarray] = []
        self._reset()
        self._lock = threading.Lock()
        self.stream = sd.InputStream(device=device, samplerate=config.SAMPLE_RATE, channels=1, dtype="float32",
                                     blocksize=BLOCK, callback=self._cb)

    def _reset(self) -> None:
        self._speech: list[np.ndarray] = []
        self._silent = 0
        self._preroll: collections.deque[np.ndarray] = collections.deque(maxlen=3)

    def sync(self) -> None:
        """Microfone só fica ligado quando alguém precisa dele (o ponto laranja do macOS diz a verdade)."""
        with self._lock:
            need = self.listening or self.held
            if need and not self.stream.active:
                self._reset()
                self.stream.start()
            elif not need and self.stream.active:
                self.stream.stop()
                self.level = 0.0

    def _cb(self, indata, *_):
        block = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(block**2)))
        self.level = min(1.0, float(np.sqrt(rms / 0.08)))
        if self.held:
            self._frames.append(block)
            return
        if not self.listening:
            return
        threshold = max(self.noise * (6 if self.guard else 3), 0.02 if self.guard else 0.01)
        loud = rms > threshold
        if not self._speech:
            if loud:
                self._speech, self._silent = [*self._preroll, block], 0
            else:
                self.noise = 0.95 * self.noise + 0.05 * rms
                self._preroll.append(block)
            return
        self._speech.append(block)
        self._silent = 0 if loud else self._silent + 1
        if self._silent >= END_SILENCE or len(self._speech) >= MAX_BLOCKS:
            if len(self._speech) - self._silent >= MIN_SPEECH:
                self.segments.put(np.concatenate(self._speech))
            self._reset()

    def press(self) -> None:
        self._frames, self.held = [], True
        self.sync()

    def release(self) -> np.ndarray:
        self.held = False
        audio = np.concatenate(self._frames) if self._frames else np.zeros(0, dtype="float32")
        self._frames = []
        self.sync()
        return audio
