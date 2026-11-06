"""Gelisim trendi: her kosuda isci/departman metriklerini olcup trend dosyasina yazar."""
import json, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
CFG = CORE / "config"


def main() -> int:
    db = RUNTIME / "company-service.db"
    queue = {}
    if db.exists():
        with sqlite3.connect(db) as con:
            queue = dict(con.execute("select status,count(*) from missions group by status").fetchall())

    minds = []
    for f in (RUNTIME / "minds").glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        m = d.get("self_model") or {}
        minds.append({
            "worker": d.get("worker_id"),
            "department": d.get("department"),
            "events": len(d.get("events") or []),
            "rate": float(m.get("success_rate") or 0.0),
            "plans": len(m.get("plan_scores") or {}),
        })

    total = len(minds) or 1
    avg_rate = round(sum(x["rate"] for x in minds) / total, 4)
    row = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "workers": len(minds),
        "avg_success": avg_rate,
        "events": sum(x["events"] for x in minds),
        "workers_with_plan_score": sum(1 for x in minds if x["plans"]),
        "queue": queue,
    }

    trend = CFG / "improvement-trend.jsonl"
    with open(trend, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    lines = [json.loads(l) for l in trend.read_text(encoding="utf-8").splitlines() if l.strip()]
    delta = None
    if len(lines) >= 2:
        delta = round(lines[-1]["avg_success"] - lines[-2]["avg_success"], 4)

    print(f"isci={row['workers']} ortalama_basari=%{round(avg_rate*100,2)} olay={row['events']} "
          f"plan_puanli={row['workers_with_plan_score']}")
    print(f"kuyruk: completed={queue.get('completed',0)} blocked={queue.get('blocked',0)} pending={queue.get('pending',0)}")
    print(f"onceki olcume gore degisim: {delta if delta is not None else 'ilk olcum'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())