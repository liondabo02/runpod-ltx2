import json
from pathlib import Path

from ahos_quality99.dashboard_flow_evidence import DashboardFlowEvidence


def test_real_dashboard_create_task_flow_evidence_is_valid():
    path = Path(__file__).resolve().parents[2] / "runtime" / "AHOS-QUALITY-99" / "DASHBOARD-FLOW-EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = DashboardFlowEvidence().evaluate(payload)
    assert report.accepted is True, report.blockers
