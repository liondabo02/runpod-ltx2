import json
from pathlib import Path

from ahos_quality99.browser_evidence import ControlCenterBrowserEvidence


def test_captured_control_center_browser_evidence_is_valid():
    path = Path(__file__).resolve().parents[2] / "runtime" / "AHOS-QUALITY-99" / "BROWSER-EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = ControlCenterBrowserEvidence().evaluate(payload)
    assert report.accepted is True, report.blockers
