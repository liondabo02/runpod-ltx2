"""Departmanlar arası iş birliği — tek istek, çok departman.

AgentSpace / Munder Difflin'deki "ajanlar birlikte çalışır" fikrinin AHOS
karşılığı: bir istek, niyet analiziyle **departman parçalarına** bölünür; her
parça kendi departmanına görev olarak düşer ve aynı **bilet** altında izlenir.

- `split(objective)`   : isteği departman parçalarına ayırır (niyet + anahtar kelime)
- `launch(runtime, ...)`: parçaları kuyruğa bırakır, ortak bilet açar
- `status(runtime, ticket)`: parçaların durumunu tek yerde toplar
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

# Departman → o departmanın işe katkısı (parça metni)
CONTRIBUTIONS = {
    "oyun": "oyun tarafı: mekanik/akış değişikliğini uygula",
    "software": "yazılım tarafı: teknik uygulamayı ve testleri yap",
    "creative": "stüdyo tarafı: görsel/ses/senaryo üret",
    "data": "veri tarafı: ölçüm kriteri ve rapor hazırla",
    "quality": "kalite tarafı: kabul kriterlerini ve test planını yaz",
    "hukuk": "hukuk tarafı: Türkiye (KVKK), Almanya (DSGVO), AB (AI Act) ve Dubai (DIFC) uyumunu yaz",
    "marketing": "pazarlama tarafı: tanıtım metni ve planı hazırla",
    "research": "araştırma tarafı: rakip/benchmark incelemesi yap",
    "finance": "finans tarafı: maliyet ve bütçe etkisini çıkar",
    "guvenlik": "güvenlik tarafı: risk ve izinleri denetle",
}

KEYWORDS = {
    "oyun": ("oyun", "mipiluna", "level", "bölüm", "sokak"),
    "software": ("kod", "yazılım", "hata", "api", "sayfa", "uygulama", "apk"),
    "creative": ("video", "ses", "dublaj", "jenerik", "görsel", "tasarım", "senaryo"),
    "data": ("veri", "rapor", "analiz", "metrik", "istatistik"),
    "quality": ("test", "kalite", "kabul", "doğrulama"),
    "hukuk": ("hukuk", "kvkk", "gdpr", "dsgvo", "uyum", "compliance", "sözleşme",
              "telif", "lisans", "marka", "difc", "dubai", "bae"),
    "marketing": ("pazarlama", "tanıtım", "reklam", "sosyal medya"),
    "research": ("araştır", "rakip", "benchmark", "incele"),
    "finance": ("bütçe", "maliyet", "fatura", "fiyat"),
    "guvenlik": ("güvenlik", "izin", "şifre", "denetim"),
}

MAX_DEPARTMENTS = 3


@dataclass(frozen=True)
class Part:
    department: str
    objective: str


@dataclass
class Collaboration:
    ticket: str
    objective: str
    parts: list[Part] = field(default_factory=list)
    missions: list[str] = field(default_factory=list)


def split(objective: str, *, limit: int = MAX_DEPARTMENTS) -> list[Part]:
    """İsteği departman parçalarına ayırır (en az bir parça)."""

    low = objective.casefold()
    scores: list[tuple[int, str]] = []
    for department, words in KEYWORDS.items():
        score = sum(1 for word in words if word in low)
        if score:
            scores.append((score, department))
    scores.sort(key=lambda pair: (-pair[0], pair[1]))

    chosen = [department for _, department in scores[:limit]]
    if not chosen:
        chosen = ["genel"]

    parts: list[Part] = []
    for department in chosen:
        note = CONTRIBUTIONS.get(department, "genel yürütme: isteği en küçük adıma böl")
        parts.append(Part(department=department, objective=f"{objective} · {note}"))
    return parts


def launch(runtime_dir: str | Path, objective: str, *, ticket: str | None = None) -> Collaboration:
    """Parçaları kuyruğa bırakır; ortak biletle izlenebilir hale getirir."""

    runtime = Path(runtime_dir)
    stamp = int(time.time())
    ticket = ticket or f"COL-{stamp}"
    collaboration = Collaboration(ticket=ticket, objective=objective, parts=split(objective))

    try:
        from .autonomous_company import PersistentMissionQueue

        queue = PersistentMissionQueue(runtime / "company-service.db")
        for index, part in enumerate(collaboration.parts, start=1):
            mission_id = f"CMD-{part.department}-collab-{stamp}-{index}"
            queue.enqueue(
                mission_id=mission_id,
                objective=part.objective,
                primary_department=part.department,
                max_attempts=2,
                replace_existing=True,
            )
            collaboration.missions.append(mission_id)
    except Exception:  # noqa: BLE001 - kuyruk isteğe bağlı
        pass

    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ticket": ticket,
        "objective": objective,
        "parts": [{"department": part.department, "mission": mission}
                  for part, mission in zip(collaboration.parts, collaboration.missions)],
    }
    path = runtime / "collaborations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return collaboration


def status(runtime_dir: str | Path, ticket: str) -> dict:
    """Bir iş birliği biletinin parçalarını tek yerde toplar."""

    runtime = Path(runtime_dir)
    path = runtime / "collaborations.jsonl"
    entry = None
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("ticket") == ticket:
                entry = row
    if not entry:
        return {"ticket": ticket, "found": False, "parts": []}

    db = runtime / "company-service.db"
    states: dict[str, str] = {}
    if db.exists():
        try:
            with sqlite3.connect(db) as con:
                for mission, state in con.execute(
                    "select mission_id, status from missions"
                ):
                    states[mission] = state
        except sqlite3.Error:
            pass

    parts = [
        {"department": part["department"], "mission": part["mission"],
         "status": states.get(part["mission"], "yok")}
        for part in entry.get("parts", [])
    ]
    done = sum(1 for part in parts if part["status"] == "completed")
    return {
        "ticket": ticket,
        "found": True,
        "objective": entry.get("objective", ""),
        "parts": parts,
        "completed": done,
        "total": len(parts),
        "progress": round(done / len(parts), 2) if parts else 0.0,
    }


# --- yürütme, devir ve portföy -------------------------------------------------


def _missions_by_status(runtime: Path) -> dict[str, str]:
    db = runtime / "company-service.db"
    states: dict[str, str] = {}
    if db.exists():
        try:
            with sqlite3.connect(db) as con:
                for mission, state in con.execute("select mission_id, status from missions"):
                    states[mission] = state
        except sqlite3.Error:
            pass
    return states


def dispatch(runtime_dir: str | Path, *, ticket: str | None = None, limit: int = 10) -> list[dict]:
    """Bir iş birliği biletinin bekleyen parçalarını gerçekten çalıştırır.

    `launch()` yalnızca kuyruğa bırakır; bu fonksiyon parçaları normal görev
    zincirinden geçirir (brief → üretim → proje kapısı → bağımsız QA) ve
    sonuçları döndürür. Böylece "tek istek, çok departman" gerçekten üretir.
    """

    from .autonomous_company import PersistentMissionQueue
    from .owner_console import build_default_console

    runtime = Path(runtime_dir)
    queue = PersistentMissionQueue(runtime / "company-service.db")
    console = build_default_console(runtime)
    states = _missions_by_status(runtime)
    results: list[dict] = []

    db_path = runtime / "collaborations.jsonl"
    records: list[dict] = []
    if db_path.exists():
        for line in db_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    for record in records:
        if ticket and record.get("ticket") != ticket:
            continue
        for part in record.get("parts", []):
            if len(results) >= limit:
                return results
            mission_id = part.get("mission")
            if not mission_id or states.get(mission_id) != "pending":
                continue
            spec = console.book.get(part.get("department"))
            if spec is None:
                results.append({"mission": mission_id, "status": "atlandı",
                                "reason": "departman yok"})
                continue
            with sqlite3.connect(runtime / "company-service.db") as con:
                con.execute(
                    "UPDATE missions SET status='running', lease_owner='collab', lease_until=?, "
                    "attempts=attempts+1, updated_at=datetime('now') "
                    "WHERE mission_id=? AND status='pending'",
                    (time.time() + 1800, mission_id),
                )
            mission = queue.get(mission_id)
            result = console._execute(spec, mission.objective, mission.mission_id)
            try:
                queue.complete(mission_id, owner="collab", result=result)
                status = "completed"
            except Exception as exc:  # noqa: BLE001
                status = "failed"
                try:
                    queue.fail(mission_id, owner="collab", error=f"{type(exc).__name__}: {exc}"[:160])
                except Exception:  # noqa: BLE001
                    pass
            results.append({"mission": mission_id, "department": part.get("department"),
                            "status": status})
    return results


def portfolio(runtime_dir: str | Path) -> dict:
    """CEO görünümü: departman bazında görev dağılımı ve iş birliği özeti."""

    runtime = Path(runtime_dir)
    db = runtime / "company-service.db"
    departments: dict[str, dict[str, int]] = {}
    if db.exists():
        try:
            with sqlite3.connect(db) as con:
                for department, state, count in con.execute(
                    "select primary_department, status, count(*) from missions "
                    "group by primary_department, status"
                ):
                    departments.setdefault(department or "bilinmeyen", {})[state] = count
        except sqlite3.Error:
            pass

    tickets: list[dict] = []
    path = runtime / "collaborations.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            tickets.append({"ticket": record.get("ticket"), "parts": len(record.get("parts", []))})

    handoffs = load_handoffs(runtime)
    return {
        "departments": departments,
        "recent_tickets": tickets,
        "handoffs": {
            "total": len(handoffs),
            "pending": sum(1 for h in handoffs if h["status"] == "pending"),
            "done": sum(1 for h in handoffs if h["status"] == "done"),
        },
    }


# --- departmanlar arası devir (handoff) ---------------------------------------


def _handoff_path(runtime: Path) -> Path:
    return runtime / "handoffs.jsonl"


def load_handoffs(runtime_dir: str | Path) -> list[dict]:
    path = _handoff_path(Path(runtime_dir))
    if not path.exists():
        return []
    items: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def handoff(runtime_dir: str | Path, source: str, target: str, objective: str,
            *, depends_on: list[str] | None = None) -> dict:
    """Bir departmanın diğerine iş devretmesi (denetlenebilir kayıt)."""

    runtime = Path(runtime_dir)
    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "handoff_id": f"H-{source}-{target}-{int(time.time() * 1000)}",
        "from": source,
        "to": target,
        "objective": objective,
        "depends_on": list(depends_on or []),
        "status": "pending",
        "mission": "",
    }
    path = _handoff_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def dispatch_handoffs(runtime_dir: str | Path, *, limit: int = 5) -> list[dict]:
    """Bağımlılığı tamamlanmış devirleri çalıştırır."""

    from .autonomous_company import PersistentMissionQueue
    from .owner_console import build_default_console

    runtime = Path(runtime_dir)
    states = _missions_by_status(runtime)
    queue = PersistentMissionQueue(runtime / "company-service.db")
    console = build_default_console(runtime)
    results: list[dict] = []
    records = load_handoffs(runtime)

    for record in records:
        if len(results) >= limit:
            break
        if record.get("status") != "pending":
            continue
        if any(dep not in {m for m, s in states.items() if s == "completed"}
               for dep in record.get("depends_on", [])):
            continue
        spec = console.book.get(record["to"])
        if spec is None:
            record["status"] = "failed"
            results.append(record)
            continue
        mission_id = f"{record['handoff_id']}-M"
        try:
            queue.enqueue(mission_id=mission_id, objective=record["objective"],
                          primary_department=record["to"], max_attempts=1)
        except sqlite3.IntegrityError:
            results.append(record)
            continue
        with sqlite3.connect(runtime / "company-service.db") as con:
            con.execute(
                "UPDATE missions SET status='running', lease_owner='handoff', lease_until=?, "
                "attempts=attempts+1, updated_at=datetime('now') "
                "WHERE mission_id=? AND status='pending'",
                (time.time() + 1800, mission_id),
            )
        mission = queue.get(mission_id)
        result = console._execute(spec, mission.objective, mission.mission_id)
        try:
            queue.complete(mission_id, owner="handoff", result=result)
            record["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            record["status"] = "failed"
            try:
                queue.fail(mission_id, owner="handoff", error=f"{type(exc).__name__}: {exc}"[:160])
            except Exception:  # noqa: BLE001
                pass
        record["mission"] = mission_id
        results.append(record)

    path = _handoff_path(runtime)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in records) + "\n",
                    encoding="utf-8")
    return results
