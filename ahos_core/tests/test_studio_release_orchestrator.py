import hashlib
import json

from ahos.studio_executor import STAGES
from ahos.studio_release_orchestrator import StudioReleaseOrchestrator


def _hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _ledger():
    return {
        "episode_id": "S01E001",
        "status": "awaiting_final_owner_release",
        "publishing_enabled": False,
        "stages": {stage: {"status": "completed"} for stage in STAGES},
    }


def _owner():
    value = {
        "episode_id": "S01E001",
        "owner_approved": True,
        "publish_requested": False,
    }
    value["decision_hash"] = _hash(value)
    return value


def test_studio_release_orchestrator_passes_complete_chain():
    report = StudioReleaseOrchestrator().evaluate(
        execution_ledger=_ledger(),
        delivery_evidence={"release_candidate_ready": True, "evidence_hash": "a" * 64},
        owner_release=_owner(),
    )
    assert report.ready is True
    assert report.blockers == ()


def test_studio_release_orchestrator_keeps_publish_separate():
    owner = _owner()
    owner["publish_requested"] = True
    unsigned = dict(owner)
    unsigned.pop("decision_hash")
    owner["decision_hash"] = _hash(unsigned)
    report = StudioReleaseOrchestrator().evaluate(
        execution_ledger=_ledger(),
        delivery_evidence={"release_candidate_ready": True, "evidence_hash": "a" * 64},
        owner_release=owner,
    )
    assert report.ready is False
    assert "owner:publish_must_be_separate_action" in report.blockers
