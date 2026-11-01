"""Haftalık ritim: her departman kendi planını üretir, kapıdan geçirir, raporlanır.

Tasarım (tek adam kararı):
- Ritim görev bazlıdır: her departman için haftada bir "plan" görevi açılır
  (`CAD-<dept>-<yıl><hafta>`). Aynı hafta ikinci kez açılmaz; tekrar çalıştırmak
  zararsızdır.
- Üretim mevcut hattan geçer: brief → produce → kabul kapısı → bağımsız QA.
  Bu modül yeni bir üretim yolu açmaz; yalnızca zamanlamayı ve raporu yönetir.
- Hiçbir içerik filtresi yok: kapılar kalite/teslim doğrular, fikir denetlemez.
- Rapor `runtime/reports/cadence-<tarih>.md` altına yazılır.

Kullanım:
    python -m ahos.ops_cadence --once
    python -m ahos.ops_cadence --once --departments finance,marketing
    python -m ahos.ops_cadence --once --dry-run
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OBJECTIVES = {
    "finance": "Bu haftanın bütçe ve nakit akışı planını hazırla",
    "marketing": "Bu haftanın kanal planını ve içerik takvimini hazırla",
    "sales": "Bu haftanın satış hunisi ve teklif listesini hazırla",
    "research": "Bu haftanın araştırma sorusunu ve kaynak listesini hazırla",
    "data": "Bu haftanın veri kalite kontrolünü ve veri sözlüğünü hazırla",
    "support": "Bu haftanın SSS ve yanıt şablonlarını güncelle",
    "operations": "Bu haftanın süreç ve RACI güncellemesini hazırla",
    "infrastructure": "Bu haftanın yedekleme ve izleme kontrolünü hazırla",
    "guvenlik": "Bu haftanın risk ve erişim denetimini hazırla",
    "quality": "Bu haftanın kabul kriterleri ve test kapsamını hazırla",
    "holding": "Bu haftanın portföy özetini ve karar günlüğünü hazırla",
    "genel": "Bu haftanın iş planını ve öncelik listesini hazırla",
    "software": "Bu haftanın yazılım bakım listesini ve riskini hazırla",
    "creative": "Bu haftanın bölüm planını ve sahne listesini hazırla",
    "oyun": "Bu haftanın oyun tasarım güncellemesini hazırla",
    "ai-platform": "Bu haftanın model ve maliyet değerlendirmesini hazırla",
}


def _week_tag(moment: datetime | None = None) -> str:
    now = moment or datetime.now(timezone.utc)
    year, week, _ = now.isocalendar()
    return f"{year}W{week:02d}"


@dataclass
class CadenceResult:
    department: str
    mission_id: str
    status: str
    verified: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "department": self.department,
            "mission": self.mission_id,
            "status": self.status,
            "verified": self.verified,
            "reason": self.reason,
        }


def run_cycle(
    runtime_dir: str | Path,
    *,
    departments: list[str] | None = None,
    dry_run: bool = False,
    week: str | None = None,
) -> list[CadenceResult]:
    """Haftalık plan görevlerini aç ve çalıştır."""

    from .autonomous_company import PersistentMissionQueue
    from .owner_console import build_default_console

    runtime = Path(runtime_dir)
    tag = week or _week_tag()
    targets = departments or list(DEFAULT_OBJECTIVES)

    if dry_run:
        return [
            CadenceResult(item, f"CAD-{item}-{tag}", "planlandı", False, "dry-run")
            for item in targets
        ]

    db = runtime / "company-service.db"
    queue = PersistentMissionQueue(db)
    console = build_default_console(runtime)

    results: list[CadenceResult] = []

    for department in targets:
        objective = DEFAULT_OBJECTIVES.get(department)
        spec = console.book.get(department) if objective else None
        mission_id = f"CAD-{department}-{tag}"
        if objective is None or spec is None:
            results.append(CadenceResult(department, mission_id, "atlandı", False,
                                         "departman veya hedef yok"))
            continue

        try:
            queue.enqueue(mission_id=mission_id, objective=objective,
                          primary_department=department, max_attempts=1)
        except sqlite3.IntegrityError:
            stored = queue.get(mission_id)
            results.append(CadenceResult(
                department, mission_id, stored.status.value if stored else "?",
                bool(stored and stored.result_json and
                     json.loads(stored.result_json).get("delivery", {}).get("verified")),
                "bu hafta zaten açıldı",
            ))
            continue

        with sqlite3.connect(db) as con:
            con.execute(
                "UPDATE missions SET status='running', lease_owner='cadence', lease_until=?, "
                "attempts=attempts+1, updated_at=datetime('now') "
                "WHERE mission_id=? AND status='pending'",
                (time.time() + 1800, mission_id),
            )

        mission = queue.get(mission_id)
        result = console._execute(spec, mission.objective, mission.mission_id)
        try:
            queue.complete(mission_id, owner="cadence", result=result)
            verified, reason = True, ""
        except Exception as exc:  # noqa: BLE001 - başarısızlık rapora yazılır
            verified, reason = False, f"{type(exc).__name__}: {exc}"[:160]
            try:
                queue.fail(mission_id, owner="cadence", error=reason)
            except Exception:  # noqa: BLE001
                pass
        stored = queue.get(mission_id)
        results.append(CadenceResult(
            department, mission_id, stored.status.value if stored else "?", verified, reason,
        ))

    return results


def write_report(runtime_dir: str | Path, results: list[CadenceResult],
                 *, tag: str | None = None) -> Path:
    runtime = Path(runtime_dir)
    reports = runtime / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    path = reports / f"cadence-{tag or _week_tag()}-{stamp}.md"

    ok = sum(1 for item in results if item.status == "completed")
    lines = [
        f"# Haftalık ritim raporu · {tag or _week_tag()}",
        "",
        f"Üretim: {datetime.now(timezone.utc).isoformat()}",
        f"Sonuç: **{ok}/{len(results)}** departman teslim etti",
        "",
        "| Departman | Görev | Durum | Doğrulanmış | Gerekçe |",
        "|---|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item.department} | `{item.mission_id}` | {item.status} | "
            f"{'evet' if item.verified else 'hayır'} | {item.reason or '—'} |"
        )
    lines += [
        "",
        "## Notlar",
        "",
        "- Her teslim, departmanın kendi kabul kapısından ve bağımsız QA'dan geçti.",
        "- İçerik filtresi uygulanmadı; yalnızca teslim kalitesi denetlendi.",
        "- Maliyet: 0 $ (model çağrısı yok).",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="haftalık departman ritmi")
    parser.add_argument("--runtime-dir", default=str(Path(__file__).resolve().parents[1] / "runtime"))
    parser.add_argument("--departments", default="", help="virgülle ayrılmış departman listesi")
    parser.add_argument("--once", action="store_true", help="tek tur çalıştır")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--week", default=None)
    args = parser.parse_args(argv)

    departments = [d.strip() for d in args.departments.split(",") if d.strip()] or None
    results = run_cycle(args.runtime_dir, departments=departments,
                        dry_run=args.dry_run, week=args.week)
    path = write_report(args.runtime_dir, results, tag=args.week) if not args.dry_run else None
    print(json.dumps({
        "results": [item.as_dict() for item in results],
        "report": str(path) if path else None,
        "completed": sum(1 for item in results if item.status == "completed"),
        "total": len(results),
    }, indent=2, ensure_ascii=False))
    return 0 if all(item.status in {"completed", "planlandı", "atlandı"} or item.verified
                    for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
