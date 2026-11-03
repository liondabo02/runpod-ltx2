"""Tek komutluk doğrulama — "gerçekten çalıştı mı?" sorusunu yanıtlar.

Kullanım:
    python tools/verify_claims.py

Çıktı: config/verification.json + konsol özeti.
Ajanların (Cline dahil) iddiaları bu dosyadaki VERDICT ile karşılaştırılır.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "ahos_core"
CFG = CORE / "config"
sys.path.insert(0, str(CORE))


def _load(name: str) -> tuple[dict | None, float | None]:
    path = CFG / name
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime
    except json.JSONDecodeError:
        return None, path.stat().st_mtime


def main() -> int:
    now = time.time()
    train, train_mtime = _load("training-report.json")
    health, health_mtime = _load("health-report.json")

    deps = (train or {}).get("departments")
    workers = (train or {}).get("workers")
    passed = (train or {}).get("passed")
    failed = (train or {}).get("failed")
    average = (train or {}).get("average_score")
    train_age = round((now - train_mtime) / 60, 1) if train_mtime else None

    health_ok = bool(health and health.get("ok"))
    bad_checks = [c["name"] for c in (health or {}).get("checks", []) if not c.get("ok")]

    pytest_result = "çalıştırılmadı"
    try:
        import pytest as _pytest_probe  # noqa: F401

        _has_pytest = True
    except Exception:  # noqa: BLE001 - pytest yoksa testler atlanır
        _has_pytest = False
        pytest_result = "atlandı: pytest yüklü değil (pip SSL hatası olabilir)"
    pytest_ok = None
    try:
        if not _has_pytest:
            raise RuntimeError("pytest yok")
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "tests"],
            cwd=str(CORE), capture_output=True, text=True, timeout=600,
        )
        tail = [line for line in done.stdout.splitlines() if "passed" in line or "failed" in line]
        pytest_result = tail[-1] if tail else done.stdout.strip().splitlines()[-1:] or "çıktı yok"
        pytest_ok = done.returncode == 0
    except RuntimeError:
        pass
    except Exception as exc:  # noqa: BLE001
        pytest_result = f"hata: {type(exc).__name__}"

    verdict = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "departments": deps,
        "workers": workers,
        "training": {"passed": passed, "failed": failed, "average": average, "age_minutes": train_age,
                     "fresh": bool(train_age is not None and train_age < 10)},
        "health": {"ok": health_ok, "bad_checks": bad_checks},
        "tests": {"result": pytest_result, "ok": pytest_ok},
        "verdict_ok": bool(
            failed == 0 and average == 100 and health_ok and pytest_ok
        ),
    }
    (CFG / "verification.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== AHOS DOĞRULAMA ===")
    print(f"departman/çalışan : {deps} / {workers}")
    print(f"eğitim            : passed={passed} failed={failed} ort={average} · yaş={train_age} dk "
          f"({'taze' if verdict['training']['fresh'] else 'ESKİ'})")
    print(f"sağlık            : ok={health_ok} · sorunlu={bad_checks or 'yok'}")
    print(f"testler           : {pytest_result}")
    print(f"SONUÇ             : {'GEÇTİ' if verdict['verdict_ok'] else 'KALDI'}")
    print("kayıt             : ahos_core/config/verification.json")
    return 0 if verdict["verdict_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
