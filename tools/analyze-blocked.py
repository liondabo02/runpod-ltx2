"""Engelli görevlerin kök neden analizi (tersine mühendislik).

Çıktı: neden sınıfları, departman dağılımı, tekrar eden örüntüler ve
her sınıf için "en iyi ajanlar ne yapıyor" eşlemesi.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.failure_analytics import classify_error

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row

rows = list(con.execute(
    "select mission_id, primary_department, last_error, attempts, max_attempts, "

    "substr(mission_id, 5, instr(substr(mission_id,5),'-')-1) as kind "
    "from missions where status='blocked'"
))
print(f"engelli toplam: {len(rows)}\n")

causes = Counter()
by_dep = defaultdict(Counter)
attempts_hist = Counter()
for row in rows:
    cause = classify_error({"message": row["last_error"] or ""})
    causes[cause] += 1
    by_dep[row["primary_department"]][cause] += 1
    attempts_hist[row["attempts"] or 0] += 1

print("=== NEDEN DAĞILIMI ===")
for cause, count in causes.most_common():
    print(f"  {count:3} · {cause}")

print("\n=== DEPARTMAN × NEDEN ===")
for dep, counter in sorted(by_dep.items(), key=lambda kv: -sum(kv[1].values())):
    detail = ", ".join(f"{k}={v}" for k, v in counter.most_common(3))
    print(f"  {dep:14} {sum(counter.values()):3} → {detail}")

print("\n=== DENEME SAYISI ===")
print("  " + ", ".join(f"{k}={v}" for k, v in sorted(attempts_hist.items())))

print("\n=== ÖRNEK HATALAR (ilk 12) ===")
for row in rows[:12]:
    print(f"  [{row['primary_department']:12}] {(row['last_error'] or '')[:110]}")

out = R / "analysis" / "blocked-causes.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({
    "total": len(rows),
    "causes": dict(causes),
    "by_department": {dep: dict(counter) for dep, counter in by_dep.items()},
    "attempts": dict(attempts_hist),
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nkayıt: {out}")
