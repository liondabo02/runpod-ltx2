"""İşçi → görev → çıktı → bağımsız QA → kayıt zincirini denetler (salt okunur).

`delivery.verified=1` yalnız teslimat işareti sayılır; gerçek ürün kanıtı değildir.
QA dosyaları isteğe bağlı olarak ayrıca doğrulanır; öneriler ürün sayılmaz. Rapor: hangi işçi gerçekten doğrulanmış çıktı üretmiş,
hangi departman kapsanmış, kaç işçi henüz kanıtsız.

Kullanım:
    python tools/workforce_output_audit.py --runtime <live runtime> --out <json>
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_qa_proof(step: dict, runtime: Path) -> dict:
    """Read a QA proof from within the trusted runtime tree, never external URLs."""
    summary = str(step.get("qa_summary") or "")
    match = re.search(r'([A-Za-z]:\\[^\r\n"<>|]*?\.json)', summary, re.IGNORECASE)
    if not match:
        return {}
    path = Path(match.group(1))
    try:
        if not path.resolve().is_relative_to(runtime.resolve()):
            return {}
        return _loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def audit(runtime: Path, *, verify_qa_files: bool = False) -> dict:
    db = runtime / "company-service.db"
    workers: dict[str, dict] = defaultdict(lambda: {"verified": 0, "qa": 0, "last": ""})
    departments: dict[str, dict] = defaultdict(lambda: {"completed": 0, "verified": 0})
    verified_total = 0
    qa_proof_files = 0
    qa_functional_pass = 0
    parsed = 0
    if db.is_file():
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for row in con.execute(
                "select primary_department, status, result_json, updated_at from missions "
                "where status='completed'"):
            department = str(row["primary_department"] or "")
            departments[department]["completed"] += 1
            payload = _loads(row["result_json"])
            if not payload:
                continue
            parsed += 1
            delivery = payload.get("delivery") or {}
            if not delivery.get("verified"):
                continue
            verified_total += 1
            departments[department]["verified"] += 1
            if verify_qa_files:
                proofs = [_load_qa_proof(step, runtime)
                          for step in (payload.get("steps") or [])]
                qa_proof_files += any(bool(item.get("passed")) for item in proofs)
                qa_functional_pass += any(bool(item.get("passed")) and
                                          bool(item.get("functional_verified"))
                                          for item in proofs)
            stamp = str(row["updated_at"] or "")
            seen = set()
            for step in payload.get("steps") or []:
                worker = str(step.get("worker_id") or "")
                qa = str(step.get("qa_worker_id") or "")
                if worker and worker not in seen:
                    seen.add(worker)
                    workers[worker]["verified"] += 1
                    workers[worker]["last"] = max(workers[worker]["last"], stamp)
                if qa:
                    workers[qa]["qa"] += 1
                    workers[qa]["last"] = max(workers[qa]["last"], stamp)
        con.close()

    roster_path = runtime / "departments.json"
    roster: list[str] = []
    if roster_path.is_file():
        try:
            payload = json.loads(roster_path.read_text(encoding="utf-8"))
            for department in payload.get("departments") or []:
                for worker in department.get("workers") or []:
                    if worker.get("worker_id"):
                        roster.append(str(worker["worker_id"]))
        except (OSError, json.JSONDecodeError):
            roster = []

    proven = sorted(name for name, item in workers.items() if item["verified"] > 0)
    unproven = sorted(set(roster) - set(proven))
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "runtime": str(runtime),
        "completed_total": sum(item["completed"] for item in departments.values()),
        "completed_with_result": parsed,
        "verified_deliveries": verified_total,
        "verified_delivery_flags": verified_total,
        "qa_evidence_checked": verify_qa_files,
        "qa_proof_file_pass_missions": qa_proof_files if verify_qa_files else None,
        "functional_qa_proof_missions": qa_functional_pass if verify_qa_files else None,
        "delivery_flags_without_qa_file_proof": (verified_total - qa_proof_files)
                                              if verify_qa_files else None,
        "roster_workers": len(roster),
        "workers_with_verified_output": len(proven),
        "workers_without_verified_output": len(unproven),
        "unproven_sample": unproven[:10],
        "departments": {name: dict(item) for name, item in sorted(departments.items())},
        "top_workers": sorted(
            ({"worker_id": name, **item} for name, item in workers.items() if item["verified"]),
            key=lambda item: (-item["verified"], item["worker_id"]))[:10],
        "note": "delivery.verified=True bir görev METAVERİSİDİR, fiziksel olarak teslim edilmiş veya yayınlanabilir ürün kanıtı değildir; QA dosyaları yalnız ayrı kanıt seviyesidir.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", default=str(Path("ahos_core") / "runtime"))
    parser.add_argument("--out", default="")
    parser.add_argument("--verify-qa", action="store_true", help="Check stored QA proof JSON files, offline; may be slower")
    args = parser.parse_args(argv)
    report = audit(Path(args.runtime), verify_qa_files=args.verify_qa)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "completed_total", "completed_with_result", "verified_deliveries",
        "roster_workers", "workers_with_verified_output",
        "workers_without_verified_output", "unproven_sample")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
