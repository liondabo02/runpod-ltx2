"""Engelli görev triyajı — kök nedene göre doğru aksiyon.

Kurallar (tersine mühendislik sonucu):
- claim_blocked / "başka işçide"      → kira bitmiş; **yeniden aç** (güvenli)
- executor_missing                    → yürütücü artık var; **yeniden aç**
- acceptance_failed                   → kapı düzeldi; **yeniden aç**
- mission_timeout                     → daha uzun süre + tek dosya; **yeniden aç**
- model_unavailable                   → hızlı yerel modelle **yeniden aç**
- worker_failed                       → plan kapısı + onarım devrede; **yeniden aç**
- other                               → sahibe bırak (dokunma)

Tur başına üst sınır vardır; her aksiyon `runtime/analysis/triage.jsonl`'e yazılır.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

from ahos.failure_analytics import classify_error

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 25

# Legacy bulk updates were unsafe: an error category is not proof that a
# mission can be retried without duplicate side effects or discarded QA.
# This report is now read-only; use ahos.queue_repair.reopen_blocked with
# an explicit dry-run and independent review for verified stale leases.
REOPEN: set[str] = set()

con = sqlite3.connect(R / "company-service.db")
con.row_factory = sqlite3.Row
rows = list(con.execute(
    "select mission_id, primary_department, last_error from missions where status='blocked' "
    "order by updated_at asc"
))

counts: dict[str, int] = {}
reopened: list[str] = []
skipped: list[str] = []

for row in rows:
    if len(reopened) >= LIMIT:
        break
    cause = classify_error({"message": row["last_error"] or ""})
    counts[cause] = counts.get(cause, 0) + 1
    if cause not in REOPEN:
        skipped.append(row["mission_id"])
        continue
    con.execute(
        "update missions set status='pending', attempts=0, max_attempts=2, "
        "lease_owner=NULL, lease_until=NULL, next_attempt_at=0, result_json=NULL, "
        "last_error=?, updated_at=datetime('now') where mission_id=?",
        (f"triyaj: {cause} → yeniden deneme", row["mission_id"]),
    )
    reopened.append(row["mission_id"])

con.commit()

# Adım kilidi taskboard.json'da tutulur; yeniden açılan görevlerin
# "done" kayıtları temizlenmezse görev "başka işçide" diye geri düşer.
try:
    board_path = R / "taskboard.json"
    if board_path.exists() and reopened:
        payload = json.loads(board_path.read_text(encoding="utf-8"))
        tasks = payload.get("tasks") if isinstance(payload, dict) else payload
        keep = [t for t in tasks if not any(str(t.get("task_id", "")).startswith(m) for m in reopened)]
        if isinstance(payload, dict):
            payload["tasks"] = keep
            board_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            board_path.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
        print("taskboard temizlendi:", len(tasks) - len(keep))
except Exception as exc:  # noqa: BLE001 - board temizliği isteğe bağlı
    print("taskboard temizlik hatası:", exc)

record = {
    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "reopened": len(reopened),
    "skipped": len(skipped),
    "by_cause": counts,
    "missions": reopened[:40],
}
out = R / "analysis" / "triage.jsonl"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")

print("neden sayımı:", counts)
print("yeniden açılan:", len(reopened))
for mission in reopened[:10]:
    print("  ", mission[:60])
print("dokunulmayan (sahibe):", len(skipped))
print("kuyruk:", dict(con.execute("select status,count(*) from missions group by status").fetchall()))
