from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .autonomous_company import PersistentMissionQueue
from .departments import DepartmentBook, DepartmentSpec


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mission_activity(
    queue: PersistentMissionQueue | None,
    *,
    limit: int = 80,
) -> dict[str, dict[str, object]]:
    """Return the last mission activity for every worker that ever ran."""

    if queue is None:
        return {}

    activity: dict[str, dict[str, object]] = {}
    try:
        missions = queue.list()[-limit:]
    except Exception:  # a corrupt/locked queue must not break the office view
        return {}

    for mission in missions:
        if not mission.result_json:
            continue
        try:
            payload = json.loads(mission.result_json)
        except json.JSONDecodeError:
            continue
        for step in payload.get("steps") or ():
            worker_id = step.get("worker_id")
            if not worker_id:
                continue
            activity[str(worker_id)] = {
                "mission_id": mission.mission_id,
                "step_id": step.get("step_id"),
                "stage": step.get("stage"),
                "mission_status": payload.get("status"),
                "at": mission.updated_at,
                "objective": mission.objective,
            }
    return activity


def _worker_state(
    entry: dict[str, object] | None,
    *,
    now: datetime,
    working_window: timedelta,
) -> tuple[str, str | None, str | None]:
    if entry is None:
        return "idle", None, None

    moment = _parse_timestamp(entry.get("at"))
    fresh = moment is not None and (now - moment) <= working_window
    stage = str(entry.get("stage") or "")
    mission_status = str(entry.get("mission_status") or "")

    if mission_status == "blocked" and stage == "blocked" and fresh:
        return "blocked", str(entry.get("step_id") or ""), str(entry.get("objective") or "")

    # Bitmiş görev "çalışıyor" sayılmaz: ajan işi bitirdiğinde bekleme durumuna
    # döner. Yalnız gerçekten yürüyen (running) görev çalışma durumudur; canlı
    # yürütme bilgisi live_activity üzerinden ayrıca eklenir.
    if fresh and mission_status == "running":
        return "working", str(entry.get("step_id") or ""), str(entry.get("objective") or "")

    return "idle", str(entry.get("step_id") or ""), str(entry.get("objective") or "")


def build_office_model(
    book: DepartmentBook,
    queue: PersistentMissionQueue | None,
    *,
    now: datetime | None = None,
    working_window_seconds: int = 120,
) -> dict[str, object]:
    """Build the data model the office floor renders.

    States come from real mission history (queue result payloads); nothing is
    invented. The animation is only a visual layer on top of those states.
    """

    moment = now or _utc_now()
    window = timedelta(seconds=working_window_seconds)
    activity = _mission_activity(queue)
    try:
        from .live_activity import active as live_active
        from .live_activity import history as live_history

        live = live_active()
        events = live_history(50)
    except Exception:  # pragma: no cover - defensive
        live = {}
        events = []

    rooms: list[dict[str, object]] = []
    stats = {"working": 0, "idle": 0, "blocked": 0}
    ticker: list[dict[str, object]] = []

    for spec in book.active():
        workers = []
        for worker in spec.workers:
            entry = activity.get(worker.worker_id)
            state, step_id, objective = _worker_state(
                entry,
                now=moment,
                working_window=window,
            )
            live_entry = live.get(worker.worker_id)
            if live_entry:
                state = "working"
                step_id = str(live_entry.get("step_id") or step_id or "")
            stats[state] = stats.get(state, 0) + 1
            workers.append(
                {
                    "worker_id": worker.worker_id,
                    "name": worker.name,
                    "role": worker.role,
                    "team_id": worker.team_id,
                    "state": state,
                    "step_id": step_id,
                    "objective": objective,
                }
            )

        rooms.append(
            {
                "department_id": spec.department_id,
                "name": spec.name,
                "source": spec.source,
                "workers": workers,
                "working": sum(1 for w in workers if w["state"] == "working"),
            }
        )

        for worker in workers:
            if worker["state"] != "idle" and worker["objective"]:
                ticker.append(
                    {
                        "at": activity.get(worker["worker_id"], {}).get("at"),
                        "worker_id": worker["worker_id"],
                        "name": worker["name"],
                        "department": spec.name,
                        "objective": worker["objective"],
                        "state": worker["state"],
                    }
                )

    ticker.sort(key=lambda item: str(item.get("at") or ""), reverse=True)

    return {
        "generated_at": moment.isoformat(),
        "working_window_seconds": working_window_seconds,
        "rooms": rooms,
        "stats": stats,
        "ticker": ticker[:8],
        "events": list(reversed(events))[:50],
        "department_count": len(rooms),
        "worker_count": sum(len(room["workers"]) for room in rooms),
    }


_STATE_LABELS = {
    "working": "çalışıyor",
    "idle": "bekliyor",
    "blocked": "engellendi",
}


def _esc(value: object) -> str:
    import html

    return html.escape("" if value is None else str(value), quote=True)


def _initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _figure(worker: dict[str, object]) -> str:
    state = str(worker["state"])
    initials = _initials(str(worker["name"]))
    role = str(worker["role"]).replace("_", " ")
    title = (
        f"{worker['name']} · {role} · {_STATE_LABELS.get(state, state)}"
        + (f" · {worker['step_id']}" if worker.get("step_id") else "")
    )
    return (
        f'<div class="figure {state}" title="{_esc(title)}">'
        f'<div class="avatar">{_esc(initials)}</div>'
        f'<div class="tag">{_esc(str(worker["name"]).split()[0])}</div>'
        "</div>"
    )


def render_office(model: dict[str, object]) -> str:
    stats = model["stats"]
    rooms_html = []
    for room in model["rooms"]:
        figures = "".join(_figure(worker) for worker in room["workers"])
        rooms_html.append(
            f'<section class="room">'
            f'<header><span class="room-name">{_esc(room["name"])}</span>'
            f'<span class="room-meta">{len(room["workers"])} ajan · '
            f'{room["working"]} çalışıyor</span></header>'
            f'<div class="floor">{figures}</div>'
            f"</section>"
        )

    ticker_html = "".join(
        f'<li><span class="dot {_esc(item["state"])}"></span>'
        f'<b>{_esc(item["name"])}</b> · {_esc(item["department"])} · '
        f'{_esc(item["objective"])}</li>'
        for item in model["ticker"]
    ) or "<li>Henüz iş almış bir ajan yok — panelden bir komut verin.</li>"

    kind_labels = {
        "started": "görev başladı",
        "step_started": "adım başladı",
        "step_finished": "adım bitti",
        "completed": "görev tamamlandı",
        "failed": "görev başarısız",
    }
    events_html = "".join(
        f'<tr><td>{_esc(str(event.get("at", ""))[11:23])}</td>'
        f'<td><span class="dot {_esc(event.get("kind"))}"></span>'
        f'{_esc(kind_labels.get(str(event.get("kind")), str(event.get("kind"))))}</td>'
        f'<td>{_esc(event.get("worker_id") or "-")}</td>'
        f'<td>{_esc(event.get("step_id") or "-")}</td>'
        f'<td class="mono">{_esc(str(event.get("mission_id") or "")[:44])}</td></tr>'
        for event in model.get("events") or ()
    ) or '<tr><td colspan="5">Henüz gerçek ajan olayı yok.</td></tr>'

    return f'''<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="3">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AHOS Ofis — canlı çalışan görünümü</title>
<style>
:root{{--bg:#0b1020;--panel:#131c30;--line:#26324b;--text:#e9eefc;--muted:#93a4c4;--ok:#33d17a;--warn:#f6c85f;--bad:#ff6b6b;--accent:#7aa2ff}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Segoe UI,Arial,sans-serif;background:radial-gradient(1200px 600px at 20% -10%,#15213a,#0b1020);color:var(--text)}}
header.top{{padding:22px 28px 8px;display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}}
h1{{margin:0;font-size:24px}} .sub{{color:var(--muted);font-size:13px;margin-top:6px}}
a.back{{color:var(--accent);text-decoration:none;font-size:14px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap}}
.pill{{background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:6px 12px;font-size:13px}}
.pill b{{margin-left:6px}}
main{{padding:12px 28px 40px}}
.ticker{{margin:10px 0 18px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 16px}}
.ticker h2{{font-size:13px;text-transform:uppercase;color:var(--muted);margin:0 0 8px}}
.ticker ul{{list-style:none;margin:0;padding:0;font-size:13px;color:#c8d4ee}}
.ticker li{{padding:3px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:8px;background:var(--muted)}}
.dot.working{{background:var(--ok);box-shadow:0 0 8px var(--ok)}} .dot.blocked{{background:var(--bad)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
.room{{background:var(--panel);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
.room header{{display:flex;justify-content:space-between;gap:8px;padding:12px 14px;border-bottom:1px solid var(--line);font-size:14px}}
.room-name{{font-weight:650}} .room-meta{{color:var(--muted);font-size:12px}}
.floor{{position:relative;min-height:130px;padding:14px;display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end;
background:repeating-linear-gradient(0deg,#121a2c 0 38px,#0f1727 38px 40px)}}
.figure{{width:64px;text-align:center;transition:transform .4s ease}}
.avatar{{width:44px;height:44px;margin:0 auto;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:15px;
background:linear-gradient(160deg,#2b3a5c,#1b2740);border:2px solid #33456b;color:#cfdcff}}
.tag{{font-size:10px;color:var(--muted);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.figure.idle{{animation:sway 6s ease-in-out infinite}}
.figure.idle .avatar{{border-color:#33456b;opacity:.75}}
.figure.working{{transform:translateY(-10px)}}
.figure.working .avatar{{border-color:var(--ok);box-shadow:0 0 14px rgba(51,209,122,.55);animation:work .9s ease-in-out infinite}}
.figure.blocked .avatar{{border-color:var(--bad);box-shadow:0 0 12px rgba(255,107,107,.5)}}
@keyframes sway{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
@keyframes work{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.07)}}}}
</style></head><body>
<header class="top">
  <div><h1>AHOS Ofis — canlı</h1>
  <div class="sub">Gerçek görev geçmişinden beslenir · {model["department_count"]} departman · {model["worker_count"]} ajan · yenilenme 3s · {_esc(model["generated_at"])}</div></div>
  <div class="stats">
    <span class="pill">Çalışıyor <b style="color:var(--ok)">{stats["working"]}</b></span>
    <span class="pill">Bekliyor <b>{stats["idle"]}</b></span>
    <span class="pill">Engel <b style="color:var(--bad)">{stats["blocked"]}</b></span>
    <a class="back" href="/">← Panele dön</a>
  </div>
</header>
<main>
  <div class="ticker"><h2>Son hareketler</h2><ul>{ticker_html}</ul></div>
  <div class="section"><h2>Son ajan olayları (gerçek kayıt)</h2>
  <table><thead><tr><th>Saat</th><th>Olay</th><th>Ajan</th><th>Adım</th><th>Görev</th></tr></thead>
  <tbody>{events_html}</tbody></table></div>
  <div class="grid">{"".join(rooms_html)}</div>
</main></body></html>'''
