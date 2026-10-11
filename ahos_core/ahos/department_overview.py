"""Read-only department evidence summaries; task counts are not readiness."""
from .department_structure import CORE_DEPARTMENTS


def department_overview(tasks):
    rows = []
    for department in CORE_DEPARTMENTS:
        members = [t for t in tasks if t.get("department") == department]
        counts = {}
        for task in members:
            status = task.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        deadlines = sorted(t["next_retry_at"] for t in members
                           if t.get("status") == "waiting_provider" and t.get("next_retry_at"))
        rows.append({
            "department": department,
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "waiting_provider": counts.get("waiting_provider", 0),
            "blocked": counts.get("blocked", 0),
            "waiting_owner_approval": counts.get("waiting_owner_approval", 0),
            "owner_approved": counts.get("owner_approved", 0),
            "failed": counts.get("retries_exhausted", 0) + counts.get("failed", 0),
            "artifact_count": sum(bool(t.get("artifact_hash")) for t in members
                                  if t.get("status") != "superseded"),
            "next_retry_at": deadlines[0] if deadlines else None,
            "production_readiness": "not_audited",
        })
    return rows
