"""CEO'nun eksik iki yetkisi: **bütçe** ve **kriz yönetimi**.

Bütçe: departman başına günlük harcama limiti; limit dolunca ücretli iş açılmaz.
Kriz: aynı hata sınıfı 3 kez tekrarlarsa CEO karar kaydı yazar ve departmana
dar kapsamlı bir kriz görevi bırakır.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DAILY_USD = 0.50
ESCALATE_AFTER = 3


def _budget_path(runtime: Path) -> Path:
    return runtime / "budget.json"


def _load(runtime: Path) -> dict:
    try:
        return json.loads(_budget_path(runtime).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def caps(runtime_dir: str | Path) -> dict[str, float]:
    payload = _load(Path(runtime_dir))
    return {str(k): float(v) for k, v in (payload.get("caps") or {}).items()}


def set_cap(runtime_dir: str | Path, department: str, usd: float) -> None:
    runtime = Path(runtime_dir)
    payload = _load(runtime)
    values = payload.setdefault("caps", {})
    values[department] = float(usd)
    _budget_path(runtime).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def spent_today(runtime_dir: str | Path, *, day: str | None = None) -> float:
    path = Path(runtime_dir) / "premium-spend.jsonl"
    if not path.exists():
        return 0.0
    today = day or time.strftime("%Y-%m-%d")
    total = 0.0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("day") == today:
            total += float(row.get("cost_usd") or 0.0)
    return round(total, 6)


def can_spend(runtime_dir: str | Path, department: str, amount: float = 0.0) -> tuple[bool, str]:
    runtime = Path(runtime_dir)
    cap = caps(runtime).get(department, DEFAULT_DAILY_USD)
    used = spent_today(runtime)
    if used + amount >= cap:
        return False, f"bütçe dolu: {department} ${used:.4f} + ${amount:.4f} >= ${cap:.2f}"
    return True, ""


def summary(runtime_dir: str | Path) -> dict:
    runtime = Path(runtime_dir)
    return {
        "spent_today_usd": spent_today(runtime),
        "caps": caps(runtime) or {"*": DEFAULT_DAILY_USD},
    }


@dataclass(frozen=True)
class Crisis:
    cause: str
    count: int
    departments: tuple[str, ...]

    def text(self) -> str:
        return (
            f"KRİZ: '{self.cause}' hatası {self.count} kez tekrarlandı "
            f"({', '.join(self.departments) or '-'}). Plan değişikliği gerekiyor."
        )


def detect_crisis(runtime_dir: str | Path, *, threshold: int = ESCALATE_AFTER, window: int = 60) -> Crisis | None:
    path = Path(runtime_dir) / "ceo" / "retry-policy.jsonl"
    if not path.exists():
        return None
    counts: dict[str, int] = {}
    departments: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-window:]:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        cause = str(row.get("cause") or "")
        if not cause:
            continue
        counts[cause] = counts.get(cause, 0) + 1
        departments.setdefault(cause, set()).add(str(row.get("department") or ""))
    for cause, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        if count >= threshold:
            return Crisis(cause=cause, count=count, departments=tuple(sorted(departments[cause] - {""})))
    return None


def act(runtime_dir: str | Path, *, threshold: int = ESCALATE_AFTER) -> dict:
    """Kriz varsa karar + dar kapsamlı görev üretir."""

    runtime = Path(runtime_dir)
    crisis = detect_crisis(runtime, threshold=threshold)
    if crisis is None:
        return {"crisis": None}

    stamp = int(time.time())
    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": "crisis",
        "cause": crisis.cause,
        "count": crisis.count,
        "departments": list(crisis.departments),
        "text": crisis.text(),
    }
    path = runtime / "ceo" / "escalations.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    created: list[str] = []
    try:
        from .autonomous_company import PersistentMissionQueue

        queue = PersistentMissionQueue(runtime / "company-service.db")
        for department in crisis.departments[:2]:
            mission_id = f"CMD-{department}-crisis-{stamp}"
            queue.enqueue(
                mission_id=mission_id,
                objective=(
                    f"KRİZ GÖREVİ: '{crisis.cause}' hatası {crisis.count} kez tekrarlandı. "
                    "Tek dosyalık en küçük adıma böl, kök nedeni yaz, düzeltmeyi uygula."
                ),
                primary_department=department,
                max_attempts=2,
                replace_existing=True,
            )
            created.append(mission_id)
    except Exception:  # noqa: BLE001 - kuyruk isteğe bağlı
        pass

    record["missions"] = created
    return {"crisis": record}
