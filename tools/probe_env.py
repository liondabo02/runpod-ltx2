"""Ortam yoklaması: hangi Python paketleri kurulu (stüdyo servisinin kullandığı Python)."""
import importlib, sys
print("python:", sys.version.split()[0], sys.executable)
for m in ("torch", "transformers", "scipy", "numpy", "PIL", "edge_tts", "soundfile"):
    try:
        mod = importlib.import_module(m); print(m, getattr(mod, "__version__", "var"))
    except Exception as e:
        print(m, "YOK", type(e).__name__)
