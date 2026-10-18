import json
from pathlib import Path

from ahos_quality99.tool_inventory import ToolInventoryValidator


def test_captured_tool_inventory_is_valid_but_deepseek_remains_open():
    path = Path(__file__).resolve().parents[2] / "runtime" / "AHOS-QUALITY-99" / "TOOL-INVENTORY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = ToolInventoryValidator().evaluate(payload)
    assert report.valid is True
    assert report.zero_cost_local_reviewer_available is True
    assert report.deepseek_local_available is False
    assert "deepseek_local_model_missing" in report.blockers
