"""Transcreve os comandos sintéticos com faster-whisper em três configurações e mede acerto de termos e latência."""
import json, re, sys, time, unicodedata
from pathlib import Path
import soundfile as sf
from faster_whisper import WhisperModel

BASE = Path(__file__).parent
FRASES = json.load(open(BASE / "frases.json"))
JARVIS_PROMPT = "Jarvis, abre o Chrome. Aumenta o volume. Coloca um timer de cinco minutos. Quais as notícias do Data Hackers?"
# vocabulário que o Jarvis conheceria: colunas do arquivo aberto + glossário pessoal do analista
VOCAB = "ticket_medio, valor_total, data_venda, id_cliente, UF, NPS, CNPJ, CAC, LTV, churn, p-valor, e-commerce, join, percentil, CSV"
CONFIGS = {
    "atual_jarvis": dict(initial_prompt=JARVIS_PROMPT),
    "prompt_vocab": dict(initial_prompt=f"Comandos de análise de dados. Colunas e termos: {VOCAB}."),
    "hotwords": dict(initial_prompt=JARVIS_PROMPT, hotwords=VOCAB),
}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"(?<=\d)\.(?=\d{3})", "", t)  # 1.234,56 -> 1234,56
    t = re.sub(r"[_\-]", " ", t)
    t = re.sub(r"[^a-z0-9, ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def main(modelo: str):
    t0 = time.perf_counter()
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    carga = round(time.perf_counter() - t0, 1)
    res = {"modelo": modelo, "carga_s": carga, "configs": {}}
    for nome, kw in CONFIGS.items():
        acertos = total = 0; lat = []; exemplos = []
        for voz in ("luciana", "eddy"):
            for i, f in enumerate(FRASES):
                audio, _ = sf.read(BASE / "audio" / f"{voz}_{i:02d}.wav", dtype="float32")
                t = time.perf_counter()
                segs, _ = m.transcribe(audio, language="pt", beam_size=1, vad_filter=True, **kw)
                txt = " ".join(s.text.strip() for s in segs)
                lat.append(time.perf_counter() - t)
                ok = [norm(term) in norm(txt) for term in f["termos"]]
                acertos += sum(ok); total += len(ok)
                if not all(ok):
                    exemplos.append({"voz": voz, "esperado": f["texto"], "ouvido": txt,
                                     "faltou": [t for t, o in zip(f["termos"], ok) if not o]})
        lat.sort()
        res["configs"][nome] = {"acerto_termos_pct": round(100 * acertos / total, 1), "termos": total,
                                "latencia_mediana_s": round(lat[len(lat) // 2], 2), "latencia_max_s": round(lat[-1], 2),
                                "erros": exemplos}
        print(f"{modelo:16s} {nome:13s} acerto={res['configs'][nome]['acerto_termos_pct']:5}%  mediana={res['configs'][nome]['latencia_mediana_s']}s  max={res['configs'][nome]['latencia_max_s']}s", flush=True)
    json.dump(res, open(BASE / f"resultado_{modelo.replace('/', '_')}.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "small")
