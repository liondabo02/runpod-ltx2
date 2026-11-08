"""Cinecode adaptörü: kurulum ve QC raporu doğrulaması."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import cinecode_adapter  # noqa: E402

REPORT = ROOT / "studio" / "pipeline" / "cinecode" / "qc-report.json"
VIDEO = ROOT / "deliverables" / "S01E001-SCENE01-2D-RIG" / "S01E001-SCENE01-2D-RIG-1080p24.mp4"


def test_cinecode_install_has_required_scripts():
    status = cinecode_adapter.status()
    if not status["exists"]:
        pytest.skip("cinecode bu makinede yok")
    assert status["scripts"]["qc.py"] and status["scripts"]["make.py"]
    assert status["scripts"]["capture.mjs"] and status["scripts"]["mix.py"]


def test_qc_report_is_real_and_all_checks_pass():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["sha256"] == hashlib.sha256(VIDEO.read_bytes()).hexdigest()
    assert set(report["checks"]) == {"info", "black", "freeze", "dup"}
    assert all(check["exit"] == 0 for check in report["checks"].values())
    assert "1920" in report["checks"]["info"]["stdout"]
    assert "audio: none" in report["checks"]["info"]["stdout"]
