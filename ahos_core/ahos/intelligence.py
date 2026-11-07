"""G019 — CEO Intelligence Dashboard verisi ve HTML görünümü.

Tüm metrikler gerçek kayıtlardan okunur; değer yoksa `None`/0 ve açıklama yazılır.
Uydurma başarı/ilerleme üretilmez. Ağ çağrısı yapılmaz.
"""

from __future__ import annotations

import html
import json
import sqlite3
import time
from pathlib import Path

from . import cognitive_memory as cm
from . import worker_state


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _lines(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _queue(runtime: Path) -> dict:
    db = runtime / "company-service.db"
    if not db.is_file():
        return {}
    try:
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
            counts = dict(con.execute("select status,count(*) from missions group by status"))
            verified = con.execute(
                "select count(*) from missions where status='completed' "
                "and json_valid(result_json) and "
                "json_extract(result_json,'$.delivery.verified')=1").fetchone()[0]
            today = con.execute(
                "select count(*) from missions where status='completed' "
                "and updated_at >= ?", (time.strftime("%Y-%m-%d"),)).fetchone()[0]
        return {"counts": counts, "verified_deliveries": verified, "completed_today": today}
    except sqlite3.Error:
        return {}


def _daily_cost(runtime: Path) -> dict:
    day = time.strftime("%Y-%m-%d")
    total = 0.0
    for name in ("premium-spend.jsonl", "model-spend.jsonl"):
        for row in _lines(runtime / name):
            if str(row.get("day") or str(row.get("at") or "")[:10]) != day:
                continue
            try:
                total += float(row.get("cost_usd") or 0.0)
            except (TypeError, ValueError):
                continue
    return {"day": day, "cost_usd": round(total, 6)}


def _security(runtime: Path) -> dict:
    owner = _json(runtime / "owner" / "owner-auth.json", None)
    audit = _lines(runtime / "owner" / "audit.jsonl")
    denials = sum(1 for row in audit if "denied" in str(row.get("event") or ""))
    pending = None
    approvals = runtime / "owner-approvals.db"
    if approvals.is_file():
        try:
            with sqlite3.connect(f"file:{approvals.as_posix()}?mode=ro", uri=True) as con:
                pending = con.execute(
                    "select count(*) from approval_requests where status='waiting_owner_approval'"
                ).fetchone()[0]
        except sqlite3.Error:
            pending = None
    return {"owner_configured": owner is not None,
            "audit_rows": len(audit), "security_denials": denials,
            "pending_approvals": pending}


def _backups(backup_root: Path | None) -> dict:
    root = backup_root or Path(r"C:\actions-runner\_work\AHOS_BACKUPS")
    vaults = sorted(p.name for p in root.glob("vault-*") if p.is_dir()) if root.is_dir() else []
    return {"vaults": len(vaults), "latest": vaults[-1] if vaults else ""}


def _worker_rows(runtime: Path, departments: list[dict]) -> list[dict]:
    help_stats: dict[str, dict] = {}
    for row in _lines(runtime / "cognition" / "_collective.jsonl"):
        if row.get("kind") != "handoff":
            continue
        for role, key in (("given", "from"), ("received", "to")):
            worker = str(row.get(key) or "")
            if worker:
                rec = help_stats.setdefault(worker, {"given": 0, "received": 0})
                rec[role] += 1
    metrics: dict[str, dict] = {}
    for row in _lines(runtime / "worker-metrics.jsonl"):
        worker = str(row.get("worker_id") or "")
        if not worker:
            continue
        rec = metrics.setdefault(worker, {"runs": 0, "success": 0, "last": ""})
        rec["runs"] += 1
        rec["success"] += 1 if row.get("success") is True else 0
        rec["last"] = max(rec["last"], str(row.get("at") or ""))
    rows = []
    records = worker_state.load_all(runtime)
    for dep in departments:
        dep_id = str(dep.get("department_id") or "")
        for worker in dep.get("workers") or []:
            wid = str(worker.get("worker_id") or "")
            if not wid:
                continue
            profile = None
            try:
                profile = cm.load(runtime, wid, dep_id)
            except ValueError:
                profile = None
            mind = _json(runtime / "minds" / f"{wid}.json", {})
            plan_scores = (mind.get("self_model") or {}).get("plan_scores") or {}
            best_plan = max(plan_scores, key=lambda key: plan_scores[key].get("ok", 0),
                            default="")
            procedural = (profile or {}).get("memory", {}).get("procedural") or []
            top_skill = max(procedural, key=lambda row: row.get("ok", 0), default={})
            m = metrics.get(wid) or {}
            state = worker_state.derive(runtime, wid,
                                        last_active=str(m.get("last") or ""),
                                        recorded=records.get(wid))
            rows.append({
                "worker": wid, "name": str(worker.get("name") or wid),
                "department": dep_id,
                "role": str(worker.get("role") or ""),
                "state_code": state["state"],
                "state_label": state["label"],
                "state_reason": state["reason"],
                "stale": state["stale"],
                "unknown": state["unknown"],
                "authority": str(worker.get("authority_level") or ""),
                "capabilities": list(worker.get("capabilities") or [])[:3],
                "runs": int(m.get("runs") or 0),
                "run_rate": round(int(m.get("success") or 0) / max(1, int(m.get("runs") or 0)), 3)
                if m.get("runs") else None,
                "last_run": m.get("last") or "",
                "best_plan": best_plan,
                "learned_methods": len(procedural),
                "top_method": str(top_skill.get("plan_type") or ""),
                "episodic": len((profile or {}).get("memory", {}).get("episodic") or []),
                "evidence": str(((profile or {}).get("evidence") or {}).get("status") or "no_profile"),
                "emotional_mode": str(((profile or {}).get("metacognition") or {})
                                      .get("note") or ""),
                "help_given": int((help_stats.get(wid) or {}).get("given") or 0),
                "help_received": int((help_stats.get(wid) or {}).get("received") or 0),
                "memory_ok": bool(profile is not None or (runtime / "minds" / f"{wid}.json").is_file()),
            })
    return rows


def _deliveries(root: Path) -> list[dict]:
    registry = {}
    db = root / "ahos_core" / "runtime" / "delivery-registry.db"
    if db.is_file():
        try:
            with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as con:
                for artifact_id, verified in con.execute(
                        "select artifact_id, verified from artifacts"):
                    registry[artifact_id] = bool(verified)
        except sqlite3.Error:
            registry = {}
    rows = []
    for manifest_path in sorted((root / "deliverables").glob("*/manifest.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        delivery = payload.get("delivery") or {}
        files = payload.get("files") or {}
        video = files.get("video") or {}
        qa = payload.get("qa") or {}
        rows.append({
            "delivery_id": payload.get("delivery_id") or manifest_path.parent.name,
            "generated_at": payload.get("generated_at"),
            "processed": delivery.get("processed"),
            "file_created": delivery.get("file_created"),
            "file_verified": delivery.get("file_verified"),
            "qa_passed": delivery.get("qa_passed"),
            "delivered": delivery.get("delivered"),
            "video_path": video.get("path"),
            "video_bytes": video.get("bytes"),
            "sha256": video.get("sha256"),
            "width": (qa.get("checks") or {}).get("width"),
            "seconds": (qa.get("checks") or {}).get("duration"),
            "qa_ok": qa.get("ok"),
            "registry_verified": registry.get(payload.get("delivery_id")),
        })
    return rows


def snapshot(runtime, *, backup_root: Path | None = None,
             repo_root: Path | None = None) -> dict:
    runtime = Path(runtime)
    payload = _json(runtime / "departments.json", {"departments": []})
    departments = payload.get("departments") if isinstance(payload, dict) else payload
    health = _json(runtime.parent / "config" / "health-report.json", {})
    queue = _queue(runtime)
    workers = _worker_rows(runtime, departments)
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "holding": {
            "departments": len(departments),
            "workers": len(workers),
            "active_workers": sum(1 for row in workers if row["last_run"]),
            "states": worker_state.counts(workers, key="state_code"),
            "queue": queue.get("counts") or {},
            "verified_deliveries": queue.get("verified_deliveries"),
            "completed_today": queue.get("completed_today"),
            "daily_cost": _daily_cost(runtime),
            "health_ok": health.get("ok"),
        },
        "workers": workers,
        "security": _security(runtime),
        "backups": _backups(backup_root),
        "deliveries": _deliveries(repo_root or Path(__file__).resolve().parents[2]),
        "note": "null = kayıt yok; uydurma değer üretilmez",
    }


def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


def render_html(data: dict) -> str:
    holding = data["holding"]
    rows = []
    for worker in data["workers"]:
        stale = " <small>eski</small>" if worker["stale"] else ""
        unknown = " <small>kayıt yok</small>" if worker["unknown"] else ""
        rows.append(
            "<tr>"
            f'<td><a href="/worker/{_esc(worker["worker"])}">{_esc(worker["name"])}</a>'
            f"<br><small>{_esc(worker['department'])} · "
            f"{_esc(worker['role'])}</small></td>"
            f"<td>{_esc(worker['state_label'])}{stale}{unknown}</td>"
            f"<td>{_esc(', '.join(worker['capabilities']))}</td>"
            f"<td>{_esc(worker['runs'])} · {_esc(worker['run_rate'])}</td>"
            f"<td>{_esc(worker['best_plan'] or '—')}</td>"
            f"<td>{_esc(worker['learned_methods'])}</td>"
            f"<td>{_esc(worker['evidence'])}</td>"
            f"<td>{_esc(worker['help_given'])} / {_esc(worker['help_received'])}</td>"
            f"<td>{_esc(worker['last_run'][:19] or '—')}</td>"
            "</tr>")
    queue = holding["queue"]
    delivery_rows = []
    for item in data.get("deliveries") or []:
        stages = " · ".join(
            f"{label}={'✓' if item.get(key) else '—'}"
            for label, key in (("işlem", "processed"), ("dosya", "file_created"),
                               ("doğrulama", "file_verified"), ("QA", "qa_passed"),
                               ("teslim", "delivered"), ("kayıt", "registry_verified")))
        delivery_rows.append(
            "<tr>"
            f"<td>{_esc(item['delivery_id'])}<br><small>{_esc(item['generated_at'])}</small></td>"
            f"<td>{_esc(stages)}</td>"
            f"<td>{_esc(item['seconds'])} sn · {_esc(item['video_bytes'])} bayt</td>"
            f"<td><code>{_esc((item['sha256'] or '')[:16])}</code><br>"
            f"<small>{_esc(item['video_path'])}</small></td>"
            "</tr>")
    queue_text = ", ".join(f"{key}={value}" for key, value in sorted(queue.items())) or "kayıt yok"
    return f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<title>AHOS CEO Intelligence</title>
<style>
body{{background:#0d1827;color:#e6efff;font:14px/1.45 system-ui;margin:24px}}
h1{{font-size:20px}} h2{{font-size:15px;margin:26px 0 8px;color:#9fc1ff}}
.card{{display:inline-block;background:#152338;border:1px solid #24395a;border-radius:10px;
padding:10px 14px;margin:0 10px 10px 0;min-width:130px}}
.card b{{display:block;font-size:18px}} small{{color:#8fa6c8}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{border-bottom:1px solid #1e3050;padding:6px;text-align:left;vertical-align:top}}
th{{color:#8fa6c8;font-weight:600}} code{{color:#9fc1ff}}
</style>
<h1>AHOS CEO Intelligence · {_esc(data['at'])}</h1>
<p><small>{_esc(data['note'])}</small></p>
<h2>Holding</h2>
<div class="card"><small>Departman</small><b>{_esc(holding['departments'])}</b></div>
<div class="card"><small>İşçi / aktif</small><b>{_esc(holding['workers'])} / {_esc(holding['active_workers'])}</b></div>
<div class="card"><small>Durum (çalışan/boşta/çevrimdışı)</small><b>{_esc(holding['states'].get('working', 0))} / {_esc(holding['states'].get('idle', 0))} / {_esc(holding['states'].get('offline', 0))}</b></div>
<div class="card"><small>Doğrulanmış teslim</small><b>{_esc(holding['verified_deliveries'])}</b></div>
<div class="card"><small>Bugün tamamlanan</small><b>{_esc(holding['completed_today'])}</b></div>
<div class="card"><small>Günlük maliyet</small><b>${_esc(holding['daily_cost']['cost_usd'])}</b></div>
<div class="card"><small>Sağlık</small><b>{_esc(holding['health_ok'])}</b></div>
<p><small>Kuyruk: <code>{_esc(queue_text)}</code></small></p>
<h2>Güvenlik ve Kalite</h2>
<div class="card"><small>Sahip kurulu</small><b>{_esc(data['security']['owner_configured'])}</b></div>
<div class="card"><small>Bekleyen onay</small><b>{_esc(data['security']['pending_approvals'])}</b></div>
<div class="card"><small>Güvenlik reddi</small><b>{_esc(data['security']['security_denials'])}</b></div>
<div class="card"><small>Denetim satırı</small><b>{_esc(data['security']['audit_rows'])}</b></div>
<div class="card"><small>Memory vault</small><b>{_esc(data['backups']['vaults'])}</b></div>
<h2>Ürün Teslimatları</h2>
<table><tr><th>Teslimat</th><th>Aşamalar</th><th>Süre / boyut</th><th>SHA-256 / yol</th></tr>
{''.join(delivery_rows) or '<tr><td colspan="4">kayıt yok</td></tr>'}
</table>
<h2>İşçi Görünümü</h2>
<table><tr><th>İşçi</th><th>Durum</th><th>Uzmanlık</th><th>Koşu / başarı</th><th>En iyi plan</th>
<th>Öğrenilen yöntem</th><th>Kanıt</th><th>Yardım (ver/al)</th><th>Son görev</th></tr>
{''.join(rows)}
</table></html>"""
