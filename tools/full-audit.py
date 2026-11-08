import io
import json
import re
import socket
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2")
R = ROOT / "ahos_core" / "runtime"
con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row

print("=== 1) KUYRUK ===")
counts = {r[0]: r[1] for r in con.execute("select status, count(*) from missions group by status")}
print(counts)
real = sum(v for k, v in counts.items() if k != "cancelled")
print(f"gerçek toplam {real} · teslim %{100*counts.get('completed',0)/max(1,real):.1f}")

print("\n=== 2) BEKLEYENLER (yaş + neden) ===")
for row in con.execute("select mission_id, primary_department, created_at, last_error from missions where status='pending' order by created_at"):
    print(f"  {row['mission_id'][:46]:46} {row['primary_department']:12} {row['created_at'][:19]} {(row['last_error'] or '')[:40]}")

print("\n=== 3) ENGELLİ NEDEN DAĞILIMI ===")
buckets = {}
for row in con.execute("select last_error from missions where status='blocked'"):
    text = (row["last_error"] or "").lower()
    if "executor_unavailable" in text or "yürütücü bağlı değil" in text:
        key = "yürütücü yok"
    elif "timeout" in text or "zaman aşımı" in text:
        key = "model zaman aşımı"
    elif "qa failed" in text or "unverified" in text:
        key = "QA reddi"
    elif "0 dosya" in text or "teslimat yok" in text:
        key = "boş teslim"
    elif "dosya yok" in text or "hedef" in text:
        key = "hedef dosya hatası"
    else:
        key = "diğer"
    buckets[key] = buckets.get(key, 0) + 1
for key, value in sorted(buckets.items(), key=lambda kv: -kv[1]):
    print(f"  {value:3} · {key}")

print("\n=== 4) İŞÇİ KARNELERİ (ilk 8) ===")
ledger = R / "worker-metrics.jsonl"
stats = {}
if ledger.exists():
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()[-4000:]:
        try:
            row = json.loads(line)
        except Exception:
            continue
        key = row.get("worker_id")
        item = stats.setdefault(key, {"runs": 0, "ok": 0, "ms": 0.0})
        item["runs"] += 1
        item["ok"] += 1 if row.get("success") else 0
        item["ms"] += float(row.get("duration_ms") or 0)
    ranked = sorted(stats.items(), key=lambda kv: -kv[1]["runs"])[:8]
    for worker, item in ranked:
        rate = item["ok"] / max(1, item["runs"])
        print(f"  {worker:28} koşu={item['runs']:3} başarı=%{rate*100:5.1f} ort={item['ms']/max(1,item['runs'])/1000:7.1f}s")

print("\n=== 5) SIR SIZINTISI TARAMASI ===")
patterns = [re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"), re.compile(r"rpa_[A-Za-z0-9]{20,}")]
hits = []
for path in list(R.glob("*.env")) + list(R.glob("*.json")) + list(ROOT.glob("ahos_core/*.env")):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    for pattern in patterns:
        if pattern.search(text):
            hits.append(str(path.relative_to(ROOT)))
            break
print("anahtar içeren dosyalar:", hits or "yok")

print("\n=== 6) AÇIK PORTLAR (AHOS) ===")
for port in (8765, 8766, 8799, 8800, 11434, 11500):
    sock = socket.socket()
    sock.settimeout(0.4)
    state = "açık" if sock.connect_ex(("127.0.0.1", port)) == 0 else "kapalı"
    sock.close()
    print(f"  {port}: {state}")

print("\n=== 7) KİLİTLER / BACKUP / DİSK ===")
lock_dir = Path(r"C:\Users\esmak\AppData\Local\ahos-locks")
print("kilit dosyası:", len(list(lock_dir.glob("*"))) if lock_dir.exists() else "kilit dizini yok")
print("yedek:", len(list((R / "backups").glob("*.db"))) if (R / "backups").exists() else 0, "db")
import shutil
usage = shutil.disk_usage(ROOT)
print(f"disk boş: {usage.free/1e9:.1f} GB / {usage.total/1e9:.0f} GB")
