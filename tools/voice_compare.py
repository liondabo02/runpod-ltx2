#!/usr/bin/env python3
"""Aynı cümleleri farklı ses motorlarıyla seslendirir; out/voice_test/ içinde kulakla karşılaştırma için dosya bırakır."""
import os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import voice_worker as vw

LINES = ["Bak, çiçeğin içinde bir damla var!", "Hoş geldiniz çocuklar, bahçeye hoş geldiniz.", "Nerede acaba? Birlikte arayalım...", "Koşalım, koşalım!"]


def main():
    out = os.path.join(ROOT, "out", "voice_test"); os.makedirs(out, exist_ok=True)
    engines = [("edge", lambda t, o: vw.tts_real_edge(t, "tr-TR-EmelNeural", "+5%", "+35Hz", o))]
    models = [m[:-5] for m in os.listdir(vw.piper_model() and os.path.dirname(vw.piper_model())) if m.endswith(".onnx")] if os.path.isdir(os.path.dirname(vw.piper_model())) else []
    for m in models:
        def f(t, o, m=m):
            os.environ["AHOS_PIPER_MODEL"] = m
            vw.tts_piper(t, "", "+0%", "+0Hz", o)
        engines.append((m, f))
    for name, fn in engines:
        for i, line in enumerate(LINES):
            path = os.path.join(out, "%s_%d.wav" % (name, i + 1))
            try:
                fn(line, path); print("OK", path)
            except Exception as e:
                print("HATA", name, i + 1, str(e)[:160])
    print("\nKlasör:", out)


if __name__ == "__main__":
    main()
