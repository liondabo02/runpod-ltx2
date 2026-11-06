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


def _mission_counts(runtime: Path) -> tuple[int, int]:
    """(toplam tamamlanan, son bir saatte tamamlanan) — kuyruk DB'sinden."""

    import sqlite3

    db = runtime / "company-service.db"
    if not db.is_file():
        return 0, 0
    try:
        con = sqlite3.connect(db)
        try:
            total = con.execute(
                "SELECT COUNT(*) FROM missions WHERE status='completed'"
            ).fetchone()[0]
            last_hour = con.execute(
                "SELECT COUNT(*) FROM missions WHERE status='completed' "
                "AND updated_at > datetime('now','-1 hour')"
            ).fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return 0, 0
    return int(total), int(last_hour)


def _write_service_state(runtime: Path, **fields) -> None:
    """Servis durumunu yaz; tick_once'un yazdığı alanları koru."""

    path = runtime / "daemon-state.json"
    payload: dict = {}
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
    payload.update(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None):
    """__main__ entrance: sınırlı, tek örnekli döngü.

    `AHOS-Daemon.ps1` bu süreci `--interval-seconds`, `--missions-per-hour`,
    `--missions-total`, `--no-evidence-limit`, `--pause-cooldown-minutes`
    bayraklarıyla başlatır ve `<runtime>/daemon-state.json` dosyasını okur.
    Durdurma: `<runtime>/daemon.stop` dosyası.
    """

    import argparse
    import os
    import sys
    import time

    # Taze bir kabukta stdout cp1252 olabilir; Türkçe durum metni yüzünden
    # çökmemek için akışları UTF-8'e çevir.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - yeniden yapılandırılamaz akış
        pass

    parser = argparse.ArgumentParser(prog="ahos-daemon", description="AHOS otonomi döngüsü")
    parser.add_argument("runtime_positional", nargs="?", default=None)
    parser.add_argument("--runtime-dir", default=None)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--missions-per-hour", type=int, default=6)
    parser.add_argument("--missions-total", type=int, default=200)
    parser.add_argument("--no-evidence-limit", type=int, default=3)
    parser.add_argument("--pause-cooldown-minutes", type=int, default=120)
    parser.add_argument("--once", action="store_true", help="tek tur çalıştır (test)")
    args = parser.parse_args(argv)

    runtime = Path(args.runtime_dir or args.runtime_positional or ".")
    runtime.mkdir(parents=True, exist_ok=True)
    stop_file = runtime / "daemon.stop"
    pid_file = runtime / "daemon.pid"
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    pid = os.getpid()
    pid_file.write_text(json.dumps({"pid": pid, "started_at": started_at}), encoding="utf-8")

    baseline, _ = _mission_counts(runtime)
    ticks = 0
    last_reason = ""
    status = "running"

    try:
        while True:
            if stop_file.exists():
                status, last_reason = "stopped", "durdurma dosyası bulundu"
                break

            _, last_hour = _mission_counts(runtime)
            if args.missions_per_hour > 0 and last_hour >= args.missions_per_hour:
                ticks += 1
                last_reason = "saatlik görev limiti doldu; bekleme"
                _write_service_state(
                    runtime, schema=1, pid=pid, started_at=started_at,
                    last_tick_at=time.strftime("%Y-%m-%dT%H:%M:%S"), ticks=ticks,
                    status="running", last_reason=last_reason,
                    interval_seconds=args.interval_seconds,
                    scheduler={
                        "status": "idle",
                        "hour_key": time.strftime("%Y-%m-%dT%H"),
                        "missions_this_hour": last_hour,
                        "missions_total": max(0, _mission_counts(runtime)[0] - baseline),
                        "last_reason": last_reason,
                    },
                )
                if args.once:
                    break
                time.sleep(max(1, args.interval_seconds))
                continue

            try:
                tick_once(str(runtime), [])
                last_reason = "tur tamamlandı"
            except Exception as exc:  # noqa: BLE001 - tur hatası servisi durdurmaz
                last_reason = f"tur hatası: {type(exc).__name__}"

            ticks += 1
            total_now, hour_now = _mission_counts(runtime)
            total_delta = max(0, total_now - baseline)
            _write_service_state(
                runtime, schema=1, pid=pid, started_at=started_at,
                last_tick_at=time.strftime("%Y-%m-%dT%H:%M:%S"), ticks=ticks,
                status="running", last_reason=last_reason,
                interval_seconds=args.interval_seconds,
                scheduler={
                    "status": "idle",
                    "hour_key": time.strftime("%Y-%m-%dT%H"),
                    "missions_this_hour": hour_now,
                    "missions_total": total_delta,
                    "last_reason": last_reason,
                },
            )

            if args.missions_total > 0 and total_delta >= args.missions_total:
                status, last_reason = "stopped", "oturum görev limiti doldu"
                break
            if args.once:
                status, last_reason = "stopped", "tek tur tamamlandı"
                break
            time.sleep(max(1, args.interval_seconds))
    finally:
        _write_service_state(
            runtime, schema=1, pid=pid, started_at=started_at,
            last_tick_at=time.strftime("%Y-%m-%dT%H:%M:%S"), ticks=ticks,
            status=status, last_reason=last_reason or "çıkış",
            interval_seconds=args.interval_seconds,
        )
        pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
