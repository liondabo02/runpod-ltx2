import json
from pathlib import Path

from ahos_quality99.studio_rehearsal_evidence import StudioRehearsalEvidenceValidator


def test_real_studio_rehearsal_evidence_is_valid_and_not_falsely_release_ready():
    path = Path(__file__).resolve().parents[2] / "runtime" / "AHOS-QUALITY-99" / "STUDIO-REHEARSAL-EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = StudioRehearsalEvidenceValidator().evaluate(payload)
    assert report.valid is True, report.blockers
    assert report.release_ready is False
