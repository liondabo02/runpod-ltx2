import io
import json
import sqlite3
import sys
import time
import wave
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MODEL_DIR = Path(r"C:\AHOS\models\kokoro")
RUNTIME = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
OUT = RUNTIME / "projects" / "mipiluna" / "www" / "voices" / "kokoro-onnx-test-en.wav"

onnx = MODEL_DIR / "kokoro-v1.0.onnx"
voices = MODEL_DIR / "voices-v1.0.bin"
print("kokoro onnx:", onnx.exists(), round(onnx.stat().st_size / 1e6, 1) if onnx.exists() else 0, "MB")
print("kokoro voices:", voices.exists(), round(voices.stat().st_size / 1e6, 1) if voices.exists() else 0, "MB")

if onnx.exists() and voices.exists():
    started = time.time()
    try:
        from kokoro_onnx import Kokoro

        kokoro = Kokoro(str(onnx), str(voices))
        samples, rate = kokoro.create(
            "Welcome to AHOS holding. This narration voice is free, local and natural.",
            voice="af_heart",
            speed=1.0,
            lang="en-us",
        )
        import numpy as np

        pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype("<i2")
        with wave.open(str(OUT), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(pcm.tobytes())
        print(f"kokoro onnx OK: {time.time()-started:.1f}s · {OUT.name} · {OUT.stat().st_size} bayt · {len(pcm)/rate:.1f}s")
    except Exception as exc:  # noqa: BLE001
        print("kokoro onnx HATA:", type(exc).__name__, exc)

print("\n--- engelli görev sınıflandırması ---")
con = sqlite3.connect(RUNTIME / "company-service.db")
con.row_factory = sqlite3.Row
rows = con.execute("select mission_id, objective, last_error, updated_at from missions where status='blocked'").fetchall()
buckets = Counter()
for row in rows:
    text = ((row["last_error"] or "") + " " + (row["objective"] or "")).lower()
    if "timeout" in text or "iptal doğrulanamadı" in text:
        buckets["zaman aşımı"] += 1
    elif "publickey" in text or "10054" in text or "connection" in text:
        buckets["ağ/tünel kopması"] += 1
    elif "başka işçide" in text or "kuyruk" in text or "lease" in text:
        buckets["kuyruk/lease"] += 1
    elif "qa" in text:
        buckets["QA reddi"] += 1
    elif "worker execution failed" in text:
        buckets["işçi hatası"] += 1
    else:
        buckets["diğer"] += 1
print("toplam:", len(rows))
for name, count in buckets.most_common():
    print(f"  {count:3} · {name}")
