"""Failure analytics: turn mission results into a quality budget.

You cannot drive the error rate to zero without knowing what fails. This module
classifies every recorded mission and error line into a small taxonomy, computes
rates and, when a cause repeats, writes a self-improvement task so the holding
works on the weakest link instead of guessing.

Read-only; it never changes a mission.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CAUSES = {
    "no_delivery": "teslimat yok (0 dosya)",
    "acceptance_failed": "kabul testi / doğrulama düştü",
    "model_unavailable": "model erişilemedi (429/404/zaman aşımı)",
    "claim_blocked": "kuyruk sahiplenilemedi",
    "project_lock": "proje kilidi (başka görev çalışıyor)",
    "executor_missing": "yürütücü bağlı değil",
    "target_missing": "hedef dosya bulunamadı",
    "worker_failed": "işçi yürütmesi başarısız (adım düştü)",
    "mission_timeout": "görev süresi aşıldı",
    "cancelled": "acil durdurma / iptal",
    "other": "diğer",
}

IMPROVEMENT_THRESHOLD = 2


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def classify_mission(row: dict) -> str:
    status = str(row.get("status") or "")
    changed = int(row.get("changed_files") or 0)
    if status in {"cancelled"}:
        return "cancelled"
    if changed == 0:
        return "no_delivery"
    if status in {"blocked", "failed"}:
        return "acceptance_failed"
    return "other"


def classify_error(row: dict) -> str:
    message = (str(row.get("message") or "") + " " + str(row.get("kind") or "")).casefold()
    if "sınırını aştı" in message or "iptal doğrulanamadı" in message:
        return "mission_timeout"
    if "worker execution failed" in message or "işçi" in message and "başarısız" in message:
        return "worker_failed"
    if "proje kilidi" in message or "sahibi " in message and "pid" in message:
        return "project_lock"
    if "executor_unavailable" in message or "yürütücü bağlı değil" in message or "executor" in message:
        return "executor_missing"
    if "dosya yok" in message or "hedef" in message and "bulunamadı" in message:
        return "target_missing"
    if any(token in message for token in ("429", "404", "timeout", "zaman aşımı", "model")):
        return "model_unavailable"
    if "başka işçide" in message or "baska iscide" in message or "kapalı:" in message:
        return "claim_blocked"
    if "check_offline" in message or "unicodeencodeerror" in message:
        return "acceptance_failed"
    if "sahiplenilemedi" in message or "claim" in message:
        return "claim_blocked"
    if "durdur" in message or "iptal" in message:
        return "cancelled"
    if "0 dosya" in message or "teslimat yok" in message:
        return "no_delivery"
    if "qa" in message or "kabul" in message or "doğrula" in message:
        return "acceptance_failed"
    return "other"


def queue_today(runtime_dir: str | Path) -> tuple[int, int] | None:
    """Bugünün gerçek teslim oranı: kuyruktaki tüm görevler (ledger değil)."""

    import re as _re
    import sqlite3
    from datetime import datetime, timezone

    db = Path(runtime_dir) / "company-service.db"
    if not db.is_file():
        return None
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        con = sqlite3.connect(str(db))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "select status, result_json from missions where updated_at like ?", (f"{day}%",)
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return None
    delivered = 0
    for row in rows:
        try:
            payload = json.loads(row["result_json"] or "{}")
        except json.JSONDecodeError:
            continue
        summary = " ".join(str(step.get("worker_summary") or "") for step in payload.get("steps") or [])
        match = _re.search(r"(\d+) dosya değişti", summary)
        changed = int(match.group(1)) if match else 0
        if row["status"] == "completed" and changed > 0:
            delivered += 1
    return delivered, len(rows)


def analyse(runtime_dir: str | Path, *, window: int = 200) -> dict:
    runtime = Path(runtime_dir)
    missions = _read_jsonl(runtime / "daemon-missions.jsonl")[-window:]
    errors = _read_jsonl(runtime / "errors.jsonl")[-window:]

    counts = {cause: 0 for cause in CAUSES}
    delivered = 0
    for row in missions:
        status = str(row.get("status") or "")
        changed = int(row.get("changed_files") or 0)
        if status == "routed" and changed > 0:
            delivered += 1
            continue
        if status == "cancelled":
            counts["cancelled"] += 1
        elif changed == 0:
            counts["no_delivery"] += 1
        else:
            counts["acceptance_failed"] += 1
    for row in errors:
        cause = classify_error(row)
        if cause in counts:
            counts[cause] += 1

    mission_failures = len(missions) - delivered
    total = len(missions)
    rate = (delivered / total) if total else 0.0
    # Sinyal yoğunluğu: "diğer" tek başına bir hata nedeni değil, ayrı gösterilir.
    top = sorted(
        ((cause, count) for cause, count in counts.items() if count and cause != "other"),
        key=lambda item: item[1],
        reverse=True,
    )
    from datetime import datetime, timezone

    today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_rows = [row for row in missions if str(row.get("at") or "").startswith(today_key)]
    today_delivered = sum(
        1
        for row in today_rows
        if row.get("status") == "routed" and int(row.get("changed_files") or 0) > 0
    )
    queue_result = queue_today(runtime)
    if queue_result is not None:
        today_delivered, today_total = queue_result
        today_rows = [None] * today_total
    return {
        "today_missions": len(today_rows),
        "today_delivered": today_delivered,
        "today_rate": round(today_delivered / len(today_rows), 3) if today_rows else 0.0,
        "missions": len(missions),
        "delivered": delivered,
        "delivery_rate": round(rate, 3),
        "error_rate": round(1 - rate, 3) if total else 0.0,
        "mission_failures": mission_failures,
        "error_signals": sum(counts.values()),
        "causes": counts,
        "top_causes": [
            {"cause": cause, "label": CAUSES[cause], "count": count} for cause, count in top
        ],
        "total_signals": sum(counts.values()),
    }


def improvement_tasks(report: dict) -> list[dict]:
    """One concrete task per cause that repeats above the threshold."""

    tasks: list[dict] = []
    for item in report.get("top_causes", []):
        if item["count"] < IMPROVEMENT_THRESHOLD:
            continue
        tasks.append(
            {
                "department": "software",
                "title": f"Sistem kalitesi: {item['label']} nedenini azalt ({item['count']} kayıt)",
                "why": f"kalite bütçesi: {item['cause']} tekrar ediyor",
                "kind": "self_improvement",
            }
        )
    return tasks


def write_backlog(runtime_dir: str | Path, tasks: list[dict]) -> Path:
    runtime = Path(runtime_dir)
    path = runtime / "self-improvement.jsonl"
    existing: set[str] = set()
    if path.is_file():
        for row in _read_jsonl(path):
            existing.add(str(row.get("title") or ""))
    with path.open("a", encoding="utf-8") as handle:
        for task in tasks:
            if task["title"] in existing:
                continue
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    runtime = Path("runtime")
    if "--runtime-dir" in args:
        position = args.index("--runtime-dir")
        runtime = Path(args[position + 1]) if position + 1 < len(args) else runtime
    report = analyse(runtime)
    if "--json" in args:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"görev: {report['missions']} · teslim: {report['delivered']} "
              f"({report['delivery_rate']:.0%}) · hata: {report['error_rate']:.0%}")
        for item in report["top_causes"]:
            print(f"  - {item['label']}: {item['count']}")
    tasks = improvement_tasks(report)
    if tasks and "--write" in args:
        path = write_backlog(runtime, tasks)
        print(f"iyileştirme görevleri yazıldı: {path} ({len(tasks)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
