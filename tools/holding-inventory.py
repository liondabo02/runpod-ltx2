import io
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2")
CORE = ROOT / "ahos_core" / "ahos"
R = ROOT / "ahos_core" / "runtime"


def line(title):
    print("\n=== " + title + " ===")


line("MODÜLLER")
modules = sorted(p.name for p in CORE.glob("*.py"))
print(f"ahos/*.py: {len(modules)}")
adapters = sorted(p.name for p in (CORE / "adapters").glob("*.py")) if (CORE / "adapters").exists() else []
print("adapters:", ", ".join(adapters))

line("KUYRUK")
con = sqlite3.connect(R / "company-service.db")
counts = {row[0]: row[1] for row in con.execute("select status, count(*) from missions group by status")}
print(counts)
real = sum(v for k, v in counts.items() if k != "cancelled")
print(f"gerçek toplam {real} · teslim %{100*counts.get('completed',0)/max(1,real):.1f}")

line("MALİYET")
ledger = R / "model-spend.jsonl"
calls = 0
usd = 0.0
if ledger.exists():
    for row in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-20000:]:
        try:
            entry = json.loads(row)
        except Exception:
            continue
        calls += 1
        usd += float(entry.get("usd") or 0)
print(f"{calls} çağrı · ${usd:.4f}")

line("PANEL")
for path in ("/", "/systems", "/office", "/outputs", "/panels", "/api/status"):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8766{path}", timeout=6) as resp:
            print(f"{path}: {resp.status} ({len(resp.read())} bayt)")
    except Exception as exc:  # noqa: BLE001
        print(f"{path}: HATA {exc}")

line("SES / RUNPOD / MODEL")
try:
    import edge_tts  # noqa: F401

    print("edge-tts: kurulu")
except Exception:
    print("edge-tts: YOK")
print("kokoro-onnx model:", (Path(r"C:\AHOS\models\kokoro\kokoro-v1.0.onnx").exists()))
print("kokoro voices:", (Path(r"C:\AHOS\models\kokoro\voices-v1.0.bin").exists()))
env = R / "runpod.env"
if env.exists():
    values = dict(l.split("=", 1) for l in env.read_text(encoding="utf-8").splitlines() if "=" in l)
    print("runpod açık:", values.get("AHOS_RUNPOD_ENABLED"), "| video:", values.get("AHOS_RUNPOD_ENDPOINT_VIDEO", "")[-30:])

line("ANDROID")
print("java:", "var" if (Path(r"C:\Program Files\Microsoft\jdk-17.0.13.11-hotspot") .exists() or Path(r"C:\Program Files\Eclipse Adoptium").exists()) else "belirsiz")
print("android sdk:", (Path(r"C:\AHOS\android\sdk").exists() or Path(r"$env:LOCALAPPDATA\Android\Sdk".replace("$env:LOCALAPPDATA", str(Path.home()))) .exists()))

line("BULUT")
print("deploy betiği:", (ROOT / "ops" / "cloud" / "deploy-oracle.ps1").exists())
print("ters tünel betiği:", (ROOT / "ops" / "tunnel" / "keep-reverse-tunnel.ps1").exists())
print("startup:", sorted(p.name for p in Path(r"C:\Users\esmak\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup").glob("AHOS*")))
