import io
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
target = sys.argv[1] if len(sys.argv) > 1 else "oyun-engineering-specialist"

rows = []
for line in (R / "worker-metrics.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    if row.get("worker_id") != target:
        continue
    rows.append(row)

print(f"{target}: {len(rows)} kayıt")
failures = [r for r in rows if not r.get("success")]
print("başarısız:", len(failures))

buckets = Counter()
for row in failures:
    reason = (row.get("reason") or "").casefold()
    if "dosya yok" in reason or "hedef" in reason:
        buckets["hedef dosya yok"] += 1
    elif "timeout" in reason or "zaman aşımı" in reason:
        buckets["model zaman aşımı"] += 1
    elif "boş" in reason or "edits" in reason:
        buckets["boş yama"] += 1
    elif "belirsiz" in reason or "kez bulundu" in reason:
        buckets["hedef belirsiz"] += 1
    elif "geri alındı" in reason or "doğrulama" in reason:
        buckets["kabul kapısı"] += 1
    elif "json" in reason:
        buckets["geçersiz JSON"] += 1
    else:
        buckets["diğer"] += 1

for name, count in buckets.most_common():
    print(f"  {count:3} · {name}")

print("\nson 5 hata:")
for row in failures[-5:]:
    print(" -", row.get("at", "")[:19], "|", str(row.get("reason"))[:140])
