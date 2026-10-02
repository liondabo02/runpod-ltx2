import json

import pytest

from ahos.autonomous_studio import _hash
from ahos.studio_approval import StudioApprovalError, record_owner_decision


def make_studio(tmp_path):
    studio = tmp_path / "S01E003"
    artifacts = studio / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "episode.json").write_text("{}", encoding="utf-8")
    approval = {
        "schema": "ahos.single-owner-decision.v1",
        "episode_id": "S01E003",
        "decision_required": "approve_or_reject_external_production_execution",
        "owner_approved": False,
        "paid_execution_enabled": False,
        "external_execution_enabled": False,
        "publishing_enabled": False,
        "evidence": {"render_job_count": 10},
        "artifacts": {"episode": "artifacts/episode.json"},
    }
    approval["evidence_hash"] = _hash(approval)
    (studio / "OWNER-APPROVAL.json").write_text(
        json.dumps(approval), encoding="utf-8"
    )
    (studio / "studio-report.json").write_text(
        json.dumps({"status": "waiting_owner_approval"}), encoding="utf-8"
    )
    return studio


def test_approval_is_hash_bound_budget_capped_and_does_not_execute(tmp_path):
    studio = make_studio(tmp_path)
    result = record_owner_decision(
        studio,
        decision="approve",
        confirm_episode_id="S01E003",
        max_budget_usd=4.25,
    )
    receipt = json.loads(result.decision_path.read_text(encoding="utf-8"))
    assert result.execution_authorized is True
    assert receipt["max_budget_usd"] == 4.25
    assert receipt["publishing_enabled"] is False
    assert receipt["consumed"] is False
    assert receipt["decision_hash"]
    assert json.loads((studio / "studio-report.json").read_text())["status"] == "approved_for_execution"


def test_approval_requires_exact_episode_and_positive_budget(tmp_path):
    studio = make_studio(tmp_path)
    with pytest.raises(StudioApprovalError, match="exactly match"):
        record_owner_decision(
            studio,
            decision="approve",
            confirm_episode_id="S01E004",
            max_budget_usd=2,
        )
    with pytest.raises(StudioApprovalError, match="positive"):
        record_owner_decision(
            studio,
            decision="approve",
            confirm_episode_id="S01E003",
            max_budget_usd=0,
        )


def test_tampered_packet_is_rejected(tmp_path):
    studio = make_studio(tmp_path)
    path = studio / "OWNER-APPROVAL.json"
    payload = json.loads(path.read_text())
    payload["episode_id"] = "S99E999"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StudioApprovalError, match="integrity"):
        record_owner_decision(
            studio,
            decision="approve",
            confirm_episode_id="S99E999",
            max_budget_usd=1,
        )


def test_conflicting_second_decision_is_rejected(tmp_path):
    studio = make_studio(tmp_path)
    record_owner_decision(
        studio,
        decision="approve",
        confirm_episode_id="S01E003",
        max_budget_usd=2,
    )
    with pytest.raises(StudioApprovalError, match="immutable"):
        record_owner_decision(
            studio,
            decision="approve",
            confirm_episode_id="S01E003",
            max_budget_usd=3,
        )
