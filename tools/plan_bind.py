"""Konuşmadan doğan plan adımlarını GERÇEK göreve bağlar (ve isterse çalıştırır).

Kullanım:
    python tools/plan_bind.py --limit 5 --execute

Kaynak: runtime/minds/plan-queue.jsonl → state=pending adımlar.
Sorun: plan adımları üretiliyor ama (a) tekrar ediyor, (b) göreve dönüşse bile
kuyruğun sonuna düşüp hiç çalışmıyor. Bu araç:

 1. (departman, eylem) çiftine göre tekilleştirir — 300 kopya yerine 1 görev,
 2. belge departmanları için kabul kapısından geçecek biçimde görev metni kurar,
 3. company-service kuyruğuna yazar,
 4. konuşma kaydına `topic = mission_id` ile "plan→görev" bağı ekler,
 5. --execute ile görevi hedefli çalıştırır (kuyruk sırası beklemeden),
 6. sonucu (completed/blocked) gerçek kayıttan raporlar.

Kanıt: runtime/plan-bind-log.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
RUNTIME = CORE / "runtime"
PLAN_QUEUE = RUNTIME / "minds" / "plan-queue.jsonl"
CONVERSATIONS = RUNTIME / "minds" / "conversations.jsonl"
LOG = RUNTIME / "plan-bind-log.jsonl"
sys.path.insert(0, str(CORE))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="bağlanacak tekil plan eylemi")
    parser.add_argument("--execute", action="store_true", help="görevleri hemen çalıştır")
    parser.add_argument("--owner", default="plan-binder")
    args = parser.parse_args(argv)

    from ahos.autonomous_company import PersistentMissionQueue
    from ahos.owner_console import build_default_console
    from ahos.projects import ProjectRegistry

    entries = _read_jsonl(PLAN_QUEUE)
    pending = [e for e in entries if e.get("state") == "pending"]
    if not pending:
        print("bekleyen plan adımı yok")
        return 0

    # (departman, eylem) → en eski kayıt temsilci; tüm kopyalar bağlanır.
    groups: dict[tuple[str, str], list[int]] = {}
    for index, entry in enumerate(entries):
        if entry.get("state") != "pending":
            continue
        key = (str(entry.get("department") or "genel"), str(entry.get("action") or "plan adımı"))
        groups.setdefault(key, []).append(index)
    chosen = list(groups.items())[: max(1, args.limit)]

    registry = ProjectRegistry(RUNTIME / "projects.json")
    queue = PersistentMissionQueue(RUNTIME / "company-service.db")
    console = build_default_console(RUNTIME)

    stamp = int(time.time())
    created = []
    for number, ((department, action), indexes) in enumerate(chosen):
        representative = entries[indexes[0]]
        worker = str(representative.get("worker") or "")
        links = registry.for_department(department)
        kind = str(getattr(links[0], "kind", "") if links else "")

        if kind == "document-workspace":
            objective = (
                f"Tasarım dokümanı üret: {department} planı — {action}. "
                "İçerik: amaç, kapsam, adım listesi, riskler."
            )
        else:
            objective = f"{department} · {action} (işçi: {worker})"

        mission_id = f"CMD-{department}-planbind-{stamp}-{number}"
        queue.enqueue(
            mission_id=mission_id,
            objective=objective,
            primary_department=department,
            max_attempts=1,
            replace_existing=True,
        )
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for index in indexes:
            entries[index].update({"state": "bound", "mission_id": mission_id, "bound_at": now})

        # Konuşma kaydı: plan adımı artık bu görev kimliğine bağlı.
        with CONVERSATIONS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "at": now,
                "from": worker or f"{department}-manager",
                "department": department,
                "topic": mission_id,
                "body": f"plan adımı gerçek göreve bağlandı: {action} → {mission_id}",
                "reply_to": "",
                "kind": "plan-link",
            }, ensure_ascii=False) + "\n")

        created.append({
            "mission_id": mission_id,
            "department": department,
            "action": action,
            "worker": worker,
            "objective": objective,
            "plan_entries": len(indexes),
        })
        print(f"bağlandı: {mission_id} · {department} · {action} ({len(indexes)} plan kaydı)")

    _write_jsonl(PLAN_QUEUE, entries)

    executed = []
    if args.execute:
        from ahos.scope import should_document

        for item in created:
            mission_id = item["mission_id"]
            claimed = queue.claim_next(owner=args.owner, lease_seconds=900, mission_id=mission_id)
            if claimed is None:
                item["result"] = "claim_failed"
                print(f"  {mission_id}: sahiplenilemedi")
                continue
            spec = console.book.get(item["department"])
            if spec is None:
                item["result"] = "department_missing"
                continue
            started = time.monotonic()
            prior = bool(getattr(console, "_scope_document", False))
            try:
                if should_document(item["objective"]) or item["objective"].startswith("Tasarım"):
                    console._scope_document = True
                result = console._execute(spec, item["objective"], mission_id)
            finally:
                console._scope_document = prior
            console._record(mission_id, args.owner, result)
            stored = queue.get(mission_id)
            item["result"] = stored.status.value if stored is not None else "?"
            item["seconds"] = round(time.monotonic() - started, 2)
            item["reason"] = str(getattr(result, "reason", ""))[:200]
            print(f"  {mission_id}: {item['result']} ({item['seconds']}s)")

    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "limit": args.limit,
            "execute": bool(args.execute),
            "bound": created,
        }, ensure_ascii=False) + "\n")

    print(f"bağlanan tekil plan eylemi: {len(created)} · plan kaydı: {sum(c['plan_entries'] for c in created)}")
    print(f"günlük: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
