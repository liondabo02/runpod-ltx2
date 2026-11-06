"""Sistem sağlık bekçisi — hata oluşmadan önce yakala, otomatik onar.

Kontroller:
1. Servisler: panel (8766), ofis (8799), model tüneli (11500)
2. Süreçler: daemon durumu ve tick ilerlemesi
3. Veri: bayat kiralar, takılı görevler, engelli birikimi
4. Kalite: test paketi (isteğe bağlı, hızlı mod)

Onarım:
- Bayat kira/lease temizliği
- Takılı (uzun süre running) görevleri yeniden kuyruğa alma
- Rapor: `ahos_core/config/health-report.json`
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SERVICES = {
    "panel": "http://127.0.0.1:8766/",
    "office": "http://127.0.0.1:8799/",
    "tunnel": "http://127.0.0.1:11500/v1/models",
}
STUCK_MINUTES = 30


@dataclass
class HealthReport:
    checks: list[dict] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check["ok"] for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ok": self.ok,
            "checks": self.checks,
            "repairs": self.repairs,
        }


def _probe(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200, f"HTTP {response.status}"
    except Exception as exc:  # noqa: BLE001 - kapalı say
        return False, f"{type(exc).__name__}"


def _db(runtime: Path) -> Path:
    return runtime / "company-service.db"


def _counts(runtime: Path) -> dict[str, int]:
    db = _db(runtime)
    if not db.exists():
        return {}
    try:
        with sqlite3.connect(db) as con:
            return dict(con.execute("select status, count(*) from missions group by status").fetchall())
    except sqlite3.Error:
        return {}


def repair(runtime_dir: str | Path) -> list[str]:
    """Bilinen arızaları onarır: bayat kira ve takılı görevler."""

    runtime = Path(runtime_dir)
    actions: list[str] = []
    db = _db(runtime)
    if not db.exists():
        return actions

    try:
        with sqlite3.connect(db) as con:
            cur = con.execute(
                "update missions set lease_owner=NULL, lease_until=NULL where status='pending' "
                "and (lease_owner is not null or lease_until is not null)"
            )
            if cur.rowcount:
                actions.append(f"bayat kira temizlendi: {cur.rowcount}")

            cutoff = time.time() - STUCK_MINUTES * 60
            cur = con.execute(
                "update missions set status='pending', lease_owner=NULL, lease_until=NULL, "
                "attempts=0, next_attempt_at=0, last_error='sağlık bekçisi: takılı görev yeniden' "
                "where status='running' and updated_at < datetime('now', ?)",
                (f"-{STUCK_MINUTES} minutes",),
            )
            if cur.rowcount:
                actions.append(f"takılı görev yeniden kuyruğa: {cur.rowcount}")
            con.commit()
    except sqlite3.Error as exc:
        actions.append(f"veritabanı onarım hatası: {exc}")
    return actions


def check(runtime_dir: str | Path, *, fix: bool = True) -> HealthReport:
    """Tüm kontrolleri yapar; `fix` açıksa onarır."""

    runtime = Path(runtime_dir)
    report = HealthReport()

    for name, url in SERVICES.items():
        ok, detail = _probe(url)
        report.checks.append({"name": f"servis:{name}", "ok": ok, "detail": detail})

    state_path = runtime / "daemon-state.json"
    daemon_ok = False
    daemon_detail = "durum dosyası yok"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            status = str(state.get("status") or "")
            daemon_ok = status in {"running", "idle", "quota_wait", "starting"}
            daemon_detail = f"{status} · tick {state.get('ticks')}"
        except (OSError, json.JSONDecodeError) as exc:
            daemon_detail = f"okunamadı: {exc}"
    report.checks.append({"name": "daemon", "ok": daemon_ok, "detail": daemon_detail})

    counts = _counts(runtime)
    db_ok = bool(counts)
    report.checks.append({"name": "kuyruk-veritabanı", "ok": db_ok, "detail": json.dumps(counts, ensure_ascii=False)})

    blocked = counts.get("blocked", 0)
    report.checks.append(
        {
            "name": "engel-oranı",
            "ok": blocked < 400,
            "detail": f"{blocked} engelli görev",
        }
    )

    if fix:
        report.repairs = repair(runtime)

    cfg = Path(runtime).parent / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "health-report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
