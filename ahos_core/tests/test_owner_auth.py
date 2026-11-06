"""Sahip kimlik doğrulaması ve ayrıcalıklı onay kapısı testleri."""
from __future__ import annotations

import json

import pytest

from ahos import owner_auth


class FakeInbox:
    def __init__(self):
        self.approved = []

    def approve(self, request_id):
        self.approved.append(request_id)
        return {"request_id": request_id, "status": "approved"}

    def reject(self, request_id):
        return {"request_id": request_id, "status": "rejected"}


def _owner(tmp_path):
    owner_auth.init_owner(tmp_path, "harun", "correct-horse-battery")
    return owner_auth.authenticate(tmp_path, "harun", "correct-horse-battery",
                                   scope="approvals")


def test_init_owner_requires_a_real_password(tmp_path):
    with pytest.raises(ValueError):
        owner_auth.init_owner(tmp_path, "harun", "short")
    with pytest.raises(ValueError):
        owner_auth.init_owner(tmp_path, "harun", "harun")
    owner_auth.init_owner(tmp_path, "harun", "correct-horse-battery")
    stored = json.loads((tmp_path / "owner" / "owner-auth.json").read_text(encoding="utf-8"))
    assert "hash" in stored and "correct-horse-battery" not in json.dumps(stored)


def test_wrong_password_and_tampered_token_are_denied(tmp_path):
    _owner(tmp_path)
    with pytest.raises(PermissionError):
        owner_auth.authenticate(tmp_path, "harun", "wrong-password-123")
    with pytest.raises(PermissionError):
        owner_auth.verify(tmp_path, "forged-token", scope="approvals")
    events = [json.loads(line)["event"] for line in
              (tmp_path / "owner" / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "owner.login.denied" in events and "owner.session.denied" in events


def test_session_scope_and_expiry_are_enforced(tmp_path):
    session = _owner(tmp_path)
    with pytest.raises(PermissionError):
        owner_auth.verify(tmp_path, session["token"], scope="spend")
    with pytest.raises(PermissionError):
        owner_auth.verify(tmp_path, session["token"], scope="approvals",
                          now=session["expires_at"] + 1)
    assert owner_auth.verify(tmp_path, session["token"], scope="approvals")["actor"] == "owner"


def test_agent_cannot_approve_and_owner_can(tmp_path):
    session = _owner(tmp_path)
    gate = owner_auth.SecureApprovalGate(tmp_path, FakeInbox())

    with pytest.raises(PermissionError):
        gate.approve("req-1", token=session["token"], actor="software-manager")
    with pytest.raises(PermissionError):
        gate.approve("req-1", token="", actor="owner")
    assert gate.inbox.approved == []

    decided = gate.approve("req-1", token=session["token"], actor="owner")
    assert decided["status"] == "approved" and gate.inbox.approved == ["req-1"]

    events = [json.loads(line) for line in
              (tmp_path / "owner" / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(row["event"] == "approval.denied" and row["actor"] == "software-manager"
               for row in events)
    assert any(row["event"] == "approval.approved" for row in events)


def test_emergency_stop_requires_stop_scope(tmp_path):
    approver = _owner(tmp_path)
    with pytest.raises(PermissionError):
        owner_auth.emergency_stop(tmp_path, approver["token"])
    stopper = owner_auth.authenticate(tmp_path, "harun", "correct-horse-battery",
                                      scope="stop")
    path = owner_auth.emergency_stop(tmp_path, stopper["token"])
    assert path.is_file()
    owner_auth.clear_stop(tmp_path, stopper["token"])
    assert not path.exists()


def test_only_harun_can_be_provisioned_and_original_password_cannot_be_replaced(tmp_path):
    with pytest.raises(PermissionError, match="Harun"):
        owner_auth.init_owner(tmp_path, "stranger", "stranger-password-123")
    assert not (tmp_path / "owner" / "owner-auth.json").exists()
    owner_auth.init_owner(tmp_path, "harun", "original-password-123")
    credential_file = tmp_path / "owner" / "owner-auth.json"
    original = credential_file.read_bytes()
    with pytest.raises(PermissionError, match="already configured"):
        owner_auth.init_owner(tmp_path, "harun", "new-attacker-password-123")
    assert credential_file.read_bytes() == original
    assert owner_auth.authenticate(tmp_path, "harun", "original-password-123")
    with pytest.raises(PermissionError):
        owner_auth.authenticate(tmp_path, "harun", "new-attacker-password-123")


def test_corrupt_owner_file_must_not_be_silently_overwritten(tmp_path):
    directory = tmp_path / "owner"
    directory.mkdir()
    path = directory / "owner-auth.json"
    sentinel = b"not-json-existing-credentials"
    path.write_bytes(sentinel)
    with pytest.raises(PermissionError, match="already configured"):
        owner_auth.init_owner(tmp_path, "harun", "attacker-password-123")
    assert path.read_bytes() == sentinel


def test_concurrent_provisioning_creates_only_one_immutable_owner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    gate = Barrier(2)

    def _register(i: int):
        gate.wait()
        try:
            return owner_auth.init_owner(tmp_path, "harun", f"secret-password-{i}")
        except PermissionError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_register, range(2)))
    assert sum(result is not None for result in results) == 1
    for password in ("secret-password-0", "secret-password-1"):
        try:
            owner_auth.authenticate(tmp_path, "harun", password)
        except PermissionError:
            continue
        break
    else:
        pytest.fail("neither original password authenticates")
    assert (tmp_path / "owner" / "owner-auth.json").is_file()
