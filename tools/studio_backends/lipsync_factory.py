"""AHOS Lip-Sync Factory v0.1 — word-aligned viseme timeline from a WAV.

    python lipsync_factory.py --wav speech.wav --out visemes.json [--language tr]

WAV -> faster-whisper word timestamps -> heuristic viseme classes -> 24 fps mouth
curve. Word alignment + phonetic heuristics (not a forced phoneme aligner); every
gate is measured on the produced file.
"""
import argparse
import json
import math
import sys
import wave

FPS = 24.0

VOWELS = {"a": "AA", "â": "AA", "e": "EE", "ê": "EE", "i": "IH", "ı": "IH",
          "î": "IH", "o": "OH", "ö": "OH", "u": "OU", "û": "OU"}
BILABIAL = set("mbp")
LABIODENTAL = set("fv")
SIBILANT = set("szşcçj")
LIQUID = set("lr")
NASAL = set("nñ")


def letter_visemes(word):
    glyphs = [ch for ch in word.lower() if ch.isalpha()]
    if not glyphs:
        return ["N"]
    out = []
    for ch in glyphs:
        if ch in BILABIAL:
            out.append("MBP")
        elif ch in LABIODENTAL:
            out.append("FV")
        elif ch in SIBILANT:
            out.append("SZ")
        elif ch in LIQUID:
            out.append("LL" if ch == "l" else "RR")
        elif ch in NASAL:
            out.append("NN")
        elif ch in VOWELS:
            out.append(VOWELS[ch])
        else:
            out.append("N")
    collapsed = []
    for viseme in out:
        if not collapsed or collapsed[-1] != viseme:
            collapsed.append(viseme)
    return collapsed[:3] or ["N"]


def audio_duration(path):
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
    return frames / float(rate)


def transcribe(wav, language, model_size):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(wav), language=language, word_timestamps=True,
                                      vad_filter=False, beam_size=1)
    words = []
    for segment in segments:
        for word in getattr(segment, "words", []) or []:
            text = (word.word or "").strip()
            if text:
                words.append({"text": text, "start": float(word.start),
                              "end": float(word.end)})
    return words, getattr(info, "language", language), getattr(info, "duration", None)


def build_timeline(words, duration):
    visemes = []
    for word in words:
        shapes = letter_visemes(word["text"])
        span = max(0.02, word["end"] - word["start"])
        step = span / len(shapes)
        for index, shape in enumerate(shapes):
            visemes.append({"t0": round(word["start"] + index * step, 4),
                            "t1": round(word["start"] + (index + 1) * step, 4),
                            "viseme": shape, "word": word["text"]})
    curve = []
    for frame in range(int(math.ceil(duration * FPS)) + 1):
        t = frame / FPS
        active = next((v for v in visemes if v["t0"] <= t < v["t1"]), None)
        shape = active["viseme"] if active else "N"
        if shape in ("AA", "OU", "OH"):
            opening = 0.9
        elif shape in ("EE", "IH"):
            opening = 0.55
        elif shape == "MBP":
            opening = 0.12
        else:
            opening = 0.3
        curve.append({"frame": frame, "t": round(t, 3), "viseme": shape,
                      "mouth_open": round(opening, 3)})
    return visemes, curve


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--language", default="tr")
    parser.add_argument("--model", default="tiny")
    ns = parser.parse_args(argv)

    duration = audio_duration(ns.wav)
    try:
        words, language, info_duration = transcribe(ns.wav, ns.language, ns.model)
    except Exception as exc:
        payload = {"schema": "ahos.lipsync.v1", "status": "BLOCKED",
                   "reason": "transcription_failed", "error": str(exc)[:300],
                   "wav": ns.wav, "duration": round(duration, 3)}
        with open(ns.out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print("LIPSYNC_BLOCKED transcription_failed")
        return 2

    visemes, curve = build_timeline(words, duration)
    gaps = [round(second["t0"] - first["t1"], 4)
            for first, second in zip(visemes, visemes[1:])]
    covered = max((item["t1"] for item in visemes), default=0.0)
    payload = {
        "schema": "ahos.lipsync.v1",
        "status": "PASSED" if visemes else "BLOCKED",
        "wav": ns.wav, "language": language, "model": ns.model,
        "duration_seconds": round(duration, 3),
        "whisper_duration": round(float(info_duration or 0.0), 3),
        "fps": FPS, "words": words, "visemes": visemes, "mouth_curve": curve,
        "metrics": {"word_count": len(words), "viseme_count": len(visemes),
                    "coverage_seconds": round(covered, 3),
                    "max_gap_seconds": max(gaps) if gaps else 0.0,
                    "tail_gap_seconds": round(max(0.0, duration - covered), 3)},
        "method": "word alignment (faster-whisper) + heuristic phoneme classes",
    }
    with open(ns.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    print("LIPSYNC_OK words=%d visemes=%d max_gap=%.3fs"
          % (len(words), len(visemes), payload["metrics"]["max_gap_seconds"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

