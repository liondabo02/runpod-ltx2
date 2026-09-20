from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ahos import (
    ActionRequest,
    ApprovalEventType,
    ApprovalInbox,
    ApprovalStatus,
    AuthorityLevel,
)


def _blocked_action() -> ActionRequest:
    return ActionRequest(
        name="publish campaign",
        authority=AuthorityLevel.C,
        external_side_effect=True,
    )


def test_submit_creates_pending_request_without_approval(tmp_path) -> None:
    inbox = ApprovalInbox(tmp_path / "approvals.jsonl")

    request = inbox.submit(_blocked_action())

    assert inbox.pending() == (request,)
    assert request.governance_reasons
    assert [event.event_type for event in inbox.history()] == [
        ApprovalEventType.REQUESTED
    ]


def test_approve_records_owner_decision_and_removes_pending(tmp_path) -> None:
    inbox = ApprovalInbox(tmp_path / "approvals.jsonl")
    request = inbox.submit(_blocked_action())

    decision = inbox.approve(request.request_id, "owner-1", "approved for launch")

    assert decision.status is ApprovalStatus.APPROVED
    assert decision.owner == "owner-1"
    assert inbox.pending() == ()
    assert [event.event_type for event in inbox.history()] == [
        ApprovalEventType.REQUESTED,
        ApprovalEventType.APPROVED,
    ]


def test_reject_records_owner_decision_and_removes_pending(tmp_path) -> None:
    inbox = ApprovalInbox(tmp_path / "approvals.jsonl")
    request = inbox.submit(_blocked_action())

    decision = inbox.reject(request.request_id, "owner-1", "not now")

    assert decision.status is ApprovalStatus.REJECTED
    assert decision.reason == "not now"
    assert inbox.pending() == ()
    assert inbox.history()[-1].owner == "owner-1"


def test_history_is_immutable_and_persisted_as_append_only_events(tmp_path) -> None:
    path = tmp_path / "approvals.jsonl"
    inbox = ApprovalInbox(path)
    request = inbox.submit(_blocked_action())
    before_decision = inbox.history()

    inbox.approve(request.request_id, "owner-1")

    assert len(before_decision) == 1
    assert before_decision[0].event_type is ApprovalEventType.REQUESTED
    with pytest.raises(FrozenInstanceError):
        before_decision[0].request_id = "changed"
    with pytest.raises(FrozenInstanceError):
        before_decision[0].action.name = "changed"
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2
    assert ApprovalInbox(path).history() == inbox.history()
