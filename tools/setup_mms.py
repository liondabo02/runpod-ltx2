"""Kurmancî ses motorunu kurar ve dener: pip install transformers; MMS modelini indirir; kısa test sesi üretir."""
import os, subprocess, sys, wave
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
try:
    import transformers  # noqa: F401
    print("transformers zaten kurulu", transformers.__version__)
except Exception:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "transformers"], capture_output=True, text=True)
    print("pip kodu", r.returncode); print((r.stdout + r.stderr)[-800:])
import tts_mms
print("kullanılabilir:", tts_mms.available())
out = os.path.join(ROOT, "out", "kmr_test.wav")
d = tts_mms.synth("Silav, navê min Kaan e. Em îro li baxçeyê dilîzin.", "facebook/mms-tts-kmr-script_latin", out)
print("süre sn:", round(d, 2), out)
with wave.open(out) as w:
    import array
    a = array.array("h", w.readframes(w.getnframes()))
print("tepe genlik:", max(abs(x) for x in a))
