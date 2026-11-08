"""Tüm kadro aday üretimi: Kaan/Esra gerçek çıktı, kota engeli kayıtlı."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT / "studio" / "candidates"
sys.path.insert(0, str(ROOT / "tools"))

import identity_lock  # noqa: E402


def manifest(cid: str) -> dict:
    return json.loads((CAND / cid / "model-sheet" / "model-sheet-manifest.json")
                      .read_text(encoding="utf-8"))


def test_kaan_candidate_has_turnaround_and_expressions():
    data = manifest("kaan")
    assert data["status"] == "CANDIDATE_PENDING_REVIEW"
    assert data["owner_approval"] == "NONE"
    assert data["views"] == 4 and data["expression_panels"] == 12
    assert (CAND / "kaan" / "model-sheet" / "kaan-turnaround-kontext-seed-2002.png").is_file()
    assert (CAND / "kaan" / "model-sheet" / "kaan-expressions-kontext-seed-3002.png").is_file()


def test_esra_only_turnaround_and_blocked_expression():
    data = manifest("esra")
    assert data["views"] == 4 and data["expression_panels"] == 0
    assert (CAND / "esra" / "model-sheet" / "esra-turnaround-kontext-seed-2003.png").is_file()
    assert not (CAND / "esra" / "model-sheet" / "esra-expressions-kontext-seed-3003.png").exists()


def test_generation_log_records_quota_stop():
    log = json.loads((CAND / "all-cast-generation-log.json").read_text(encoding="utf-8"))
    assert "kaan" in log and "esra" in log
    assert log["esra"]["error"] == "AppError"
    assert "ZeroGPU" in log["esra"]["detail"]


def test_no_commercial_or_approved_claims():
    for cid in ("aden", "kaan", "esra"):
        data = manifest(cid)
        assert data["final_use_allowed"] is False
        assert "NON-COMMERCIAL" in data["model_license"]
        assert "APPROVED" not in json.dumps(data, ensure_ascii=False)
    assert identity_lock.verify() == []
