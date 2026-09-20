from pathlib import Path

import pytest

from ahos.studio_acceptance import AcceptancePreflightError, StudioAcceptancePreflight


def backlog(status6="completed"):
    return {
        "tasks": [
            {"id": f"STUDIO-{n:03d}", "status": status6 if n == 6 else "completed"}
            for n in range(1, 9)
        ]
    }


def evaluate(tmp_path: Path, **overrides):
    artifact = tmp_path / "proof.json"
    artifact.write_text("{}", encoding="utf-8")
    values = {
        "episode_id": "S01E001",
        "backlog": backlog(),
        "required_artifacts": (artifact,),
        "voice_similarity_approved": True,
        "owner_approved": True,
        "execution_enabled": True,
        "paid_provider_enabled": True,
        "paid_execution_requested": True,
        "publish_requested": False,
    }
    values.update(overrides)
    return StudioAcceptancePreflight().evaluate(**values)


def test_every_gate_must_pass_before_paid_execution(tmp_path: Path):
    result = evaluate(tmp_path)
    assert result.ready_for_paid_execution is True
    assert all(g.passed for g in result.gates)


def test_studio_006_in_progress_blocks_acceptance(tmp_path: Path):
    result = evaluate(tmp_path, backlog=backlog("in_progress"))
    assert result.ready_for_paid_execution is False
    assert "STUDIO-006" in next(g.message for g in result.gates if g.gate_id == "studio-roadmap")


@pytest.mark.parametrize("field", ["voice_similarity_approved", "owner_approved", "execution_enabled", "paid_provider_enabled"])
def test_each_protected_gate_fails_closed(tmp_path: Path, field: str):
    result = evaluate(tmp_path, **{field: False})
    assert result.ready_for_paid_execution is False


def test_preflight_does_not_spend_without_execution_request(tmp_path: Path):
    result = evaluate(tmp_path, paid_execution_requested=False)
    assert result.ready_for_paid_execution is False
    assert result.paid_execution_requested is False


def test_publish_request_is_blocked(tmp_path: Path):
    result = evaluate(tmp_path, publish_requested=True)
    assert result.ready_for_paid_execution is False


def test_missing_artifact_blocks_acceptance(tmp_path: Path):
    result = evaluate(tmp_path, required_artifacts=(tmp_path / "missing.json",))
    assert result.ready_for_paid_execution is False


def test_invalid_backlog_fails_closed(tmp_path: Path):
    with pytest.raises(AcceptancePreflightError):
        evaluate(tmp_path, backlog={})
