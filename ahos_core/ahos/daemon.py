"""Canlı bağlantı (daemon) — her turda çalışan temel sistem."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .health_guard import check as health_check
from . import training
from . import initiative
from . import outcome


class DaemonState:
    """Daemon durumunun tutulduğu struct."""
    def __init__(self, runtime_dir: str | Path):
        self.runtime = Path(runtime_dir)
        self.infra: dict = {}
        self.learning: dict = {}
        self.health: dict = {}
        self.last_tick: float = 0.0


def _health_to_dict(health_report):
    """HealthReport -> JSON serializable dict."""
    if hasattr(health_report, 'to_dict'):
        return health_report.to_dict()
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ok": health_report.ok if hasattr(health_report, 'ok') else False,
        "checks": getattr(health_report, 'checks', []),
        "repairs": getattr(health_report, 'repairs', []),
    }


def load_state(runtime_dir: str | Path) -> DaemonState:
    """Mevcut durumu diskten yükle."""
    state = DaemonState(runtime_dir)
    st_path = Path(runtime_dir) / "daemon-state.json"
    if st_path.exists():
        try:
            data = json.loads(st_path.read_text(encoding="utf-8"))
            state.infra = data.get("infra", {})
            state.learning = data.get("learning", {})
            state.health = data.get("health", {})
        except (json.JSONDecodeError, OSError):
            pass
    return state


def save_state(state: DaemonState) -> None:
    """Durumu diske kaydet."""
    st_path = Path(state.runtime) / "daemon-state.json"
    st_path.parent.mkdir(parents=True, exist_ok=True)
    st_path.write_text(json.dumps({
        "infra": state.infra,
        "learning": state.learning,
        "health": state.health,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def tick_once(runtime_dir: str | Path, departments: list[dict] | None = None) -> dict:
    """Bir tur daemon çalışması.

    Args:
        runtime_dir: runtime dizini
        departments: departments listesi (optional)

    Returns:
        güncellenen state.infra dict'i
    """
    state = load_state(runtime_dir)
    state.last_tick = time.time()

    # 1) Eğitim tazeleme (her 6 turda bir kez)
    if int(state.last_tick) % 6 == 0:
        r = training.teach(runtime_dir, departments or [])
        state.infra["training"] = {"passed": r["passed"], "failed": r["failed"], "average": r["average_score"]}

    # 2) Initiative (her turda)
    if departments:
        from .initiative import tick as initiative_tick
        r = initiative_tick(runtime_dir, departments)
        state.infra["initiative"] = r

    # 3) Outcome (her turda)
    # En işlenen departmanı bul
    dep = departments[0]["department_id"] if departments else ""
    from .outcome import adjust as outcome_adjust
    adj = outcome_adjust(runtime_dir, dep)
    state.infra["outcome"] = {"scope": adj["scope"]}

    # 4) Health check (her turda)
    from .health_guard import check as health_check
    health = health_check(runtime_dir, fix=False)
    state.infra["health"] = _health_to_dict(health)

    # 5) İşçi zihni: düşün, hedef, plan, kalibrasyon (sahiplik her zihinde)
    try:
        from .sovereign import ensure as _pledge
        from .worker_mind import tick as _mind_tick

        _pledge(runtime_dir)
        _thoughts = _mind_tick(runtime_dir, departments or [], limit=6)
        state.infra["minds"] = _thoughts
    except Exception:  # noqa: BLE001
        pass

    # 6) Konuşma: işçiler birbirine soru sorar, cevap verir
    try:
        from .commune import converse as _converse

        state.infra["commune"] = _converse(runtime_dir, departments or [], rounds=2)
    except Exception:  # noqa: BLE001
        pass

    # 7) Beyin → eylem: plan adımlarını gerçek göreve çevir
    try:
        from .mind_feedback import flush_plan_queue as _flush

        state.infra["plan_queue"] = _flush(runtime_dir, limit=10)
    except Exception:  # noqa: BLE001
        pass

    save_state(state)
    return state.infra


def main():
    """__main__ entrance."""
    import sys
    runtime = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    departments = []
    if len(sys.argv) > 2:
        try:
            departments = json.loads(sys.argv[2])
        except Exception:
            pass
    state = tick_once(str(runtime), departments)
    print(json.dumps({"state": state}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
