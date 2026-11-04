"""Plan kuyruğundaki adımları gerçek görevlere çevirir (beyin → eylem).

Kullanım:
    python tools/plan_to_missions.py [limit]

- runtime/minds/plan-queue.jsonl içindeki state=pending adımları okur
- her adım için company-service.db'ye mission ekler
- işlenen adımları state=queued olarak yeniden yazar
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
sys.path.insert(0, str(CORE))

from ahos.autonomous_company import PersistentMissionQueue  # noqa: E402

QUEUE = RUNTIME / "minds" / "plan-queue.jsonl"


def main(argv: list[str]) -> int:
    limit = int(argv[1]) if len(argv) > 1 else 20
    if not QUEUE.exists():
        print("plan kuyrugu yok:", QUEUE)
        return 1

    lines = [line for line in QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    pending = [entry for entry in entries if entry.get("state") == "pending"]
    if not pending:
        print("bekleyen plan adimi yok")
        return 0

    mission_queue = PersistentMissionQueue(RUNTIME / "company-service.db")
    stamp = int(time.time())
    created = 0

    for index, entry in enumerate(pending[:limit]):
        department = str(entry.get("department") or "genel")
        action = str(entry.get("action") or "plan adimi")
        worker = str(entry.get("worker") or "")
        mission_id = f"CMD-{department}-plan-{stamp}-{index}"
        try:
            mission_queue.enqueue(
                mission_id=mission_id,
                objective=f"{department} · {action} (işçi: {worker})",
                primary_department=department,
                max_attempts=1,
                replace_existing=True,
            )
            entry["state"] = "queued"
            entry["mission_id"] = mission_id
            entry["queued_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            created += 1
        except Exception as exc:  # noqa: BLE001 - tek adım hatası döngüyü durdurmaz
            entry["state"] = "error"
            entry["error"] = type(exc).__name__

    QUEUE.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n", encoding="utf-8")
    print(f"göreve çevrilen plan adımı: {created} / {len(pending)} bekleyen")
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
