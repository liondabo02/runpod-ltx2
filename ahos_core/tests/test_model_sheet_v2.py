"""v2 model sheet üretim planı — ağ çağrısı olmadan doğrulanır."""
from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def test_dry_run_lists_four_steps():
    import model_sheet_v2

    assert [step["id"] for step in model_sheet_v2.STEPS] == [
        "aden-turnaround", "aden-expressions", "kaan-turnaround", "kaan-expressions"]
    assert all(step["prompt"].strip() for step in model_sheet_v2.STEPS)
    assert [step["seed"] for step in model_sheet_v2.STEPS] == [501, 502, 503, 504]


def test_quota_errors_are_classified_and_stop():
    import model_sheet_v2

    assert model_sheet_v2.classify(
        "You have exceeded your free ZeroGPU quota") == "zerogpu_quota"
    assert model_sheet_v2.classify(
        "Value 432 is less than minimum value 512") == "invalid_parameter"
    assert model_sheet_v2.classify("boom") == "provider_error"


def test_dry_run_exits_zero_without_network(capsys):
    import model_sheet_v2

    code = model_sheet_v2.main(["--dry-run", "--only", "aden-turnaround"])

    assert code == 0
    output = capsys.readouterr().out
    assert "aden-turnaround" in output
    assert "kaan-expressions" not in output
