"""Klon/web teslimi icin bagimsiz kabul araclari (vendored, MIT).

Kaynak: https://github.com/Jakeschincariol/replica-skill ("replica-skill"),
MIT lisansi. `ahos_core/tools/replica/` altina oldugu gibi kopyalandi.

Neden burada: AHOS'un kabul katmani yalnizca "dosya var mi" diye bakmamali.
Bir klon/web teslimi icin iki bagimsiz olcum gerekiyor:

  1. Ozellik paritesi  - kac zorunlu ozellik gercekten calisiyor (must/should/could).
  2. Duzen paritesi    - ekran yerlesimi orijinalle ne kadar ortusuyor (renk disi).

Bu modul ikisini de deterministik, agsiz ve bagimliliksiz hesaplar; QA bu
sayilari esik olarak kullanabilir. Icerik/kod kopyalamaz: yalnizca olcer.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPLICA_DIR = Path(__file__).resolve().parents[1] / "tools" / "replica"


def _load(module_name: str, filename: str):
    path = REPLICA_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"replica araci yok: {path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules.setdefault(module_name, module)
    spec.loader.exec_module(module)
    return module


def feature_parity(csv_path: str | Path) -> dict:
    """features.csv -> {"feature_score", "must_have_done/total", "missing", ...}."""

    parity = _load("ahos_replica_parity", "parity.py")
    rows = parity.load(str(csv_path))
    return parity.score(rows)


def layout_parity(original_png: str | Path, clone_png: str | Path, *, width: int = 480) -> dict:
    """Iki ekran goruntusunun yerlesim skoru (renk farki sayilmaz)."""

    imgdiff = _load("ahos_replica_imgdiff", "imgdiff.py")
    report, _diff = imgdiff.compare(
        imgdiff.read_png(str(original_png)),
        imgdiff.read_png(str(clone_png)),
        mode="layout",
        width=width,
    )
    return report


def accept(
    features_csv: str | Path,
    *,
    original_png: str | Path | None = None,
    clone_png: str | Path | None = None,
    min_features: float = 80.0,
    min_layout: float = 50.0,
) -> tuple[bool, dict]:
    """Teslim kabulu: ozellik esigi + (verildiyse) duzen esigi.

    Donen sozluk, QA kaydina yazilabilecek ham sayilari icerir; "passed"
    yalnizca butun zorunlu ozellikler bitmis ve esikler gecilmisse True olur.
    """

    features = feature_parity(features_csv)
    evidence: dict = {
        "feature_score": features["feature_score"],
        "must_have_done": features["must_have_done"],
        "must_have_total": features["must_have_total"],
        "missing": features["missing"],
    }

    must_ok = (
        features["must_have_total"] > 0
        and features["must_have_done"] == features["must_have_total"]
    )
    features_ok = must_ok and features["feature_score"] >= min_features

    layout_ok = True
    if original_png is not None and clone_png is not None:
        report = layout_parity(original_png, clone_png)
        layout_score = float(report.get("score", 0.0))
        evidence["layout_score"] = layout_score
        evidence["layout_verdict"] = report.get("verdict")
        layout_ok = layout_score >= min_layout

    evidence["passed"] = bool(features_ok and layout_ok)
    evidence["reasons"] = (
        []
        if evidence["passed"]
        else [
            reason
            for reason, ok in (
                (
                    f"zorunlu ozellikler eksik: {features['must_have_total'] - features['must_have_done']}",
                    must_ok,
                ),
                (f"ozellik skoru {features['feature_score']} < {min_features}", features_ok),
                (f"duzen skoru {evidence.get('layout_score')} < {min_layout}", layout_ok),
            )
            if not ok
        ]
    )
    return evidence["passed"], evidence
