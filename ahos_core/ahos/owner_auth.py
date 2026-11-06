"""Sahip kimlik doğrulaması, oturumları ve ayrıcalıklı işlem kapısı.

Tek nihai sahip: Harun. Kurallar:
- Kullanıcı adını yazmak kimlik doğrulama değildir; parola PBKDF2 ile doğrulanır.
- Oturum token'ı yalnız parola doğrulandıktan sonra üretilir, süreli ve kapsamlıdır.
- Hiçbir ajan kendi onayını veremez: onay işlemleri `actor="owner"` + geçerli
  oturum ister; ajan aktörü her durumda reddedilir ve denetime yazılır.
- Yetkiler en az yetki ilkesiyle kapsam (scope) bazlıdır.
- Acil durdurma ayrı kapsam ister ve denetlenir.

Bu modül ağ çağrısı yapmaz; yalnız yerel dosya + SQLite inbox kullanır.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from pathlib import Path

SCHEMA = 1
ITERATIONS = 200_000
SCOPES = ("approvals", "spend", "delete", "publish", "credentials", "authority", "stop")
MIN_PASSWORD = 12


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _path(runtime) -> Path:
    path = Path(runtime) / "owner"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict) -> None:
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def audit(runtime, event: str, **fields) -> dict:
    record = {"at": _now_iso(), "event": event, **fields}
    with (_path(runtime) / "audit.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def init_owner(runtime, username: str, password: str) -> dict:
    username = username.strip().lower()
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"owner password must be at least {MIN_PASSWORD} characters")
    if password.casefold() == username:
        raise ValueError("owner password must not equal the username")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    payload = {"schema": SCHEMA, "username": username, "salt": salt.hex(),
               "hash": digest.hex(), "iterations": ITERATIONS, "created_at": _now_iso()}
    _write_json(_path(runtime) / "owner-auth.json", payload)
    audit(runtime, "owner.initialized", username=username)
    return {"username": username, "created_at": payload["created_at"]}


def _owner(runtime) -> dict | None:
    payload = _read_json(_path(runtime) / "owner-auth.json", None)
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        return None
    return payload


def authenticate(runtime, username: str, password: str, *, scope: str = "approvals",
                 ttl_seconds: int = 1800, now: float | None = None) -> dict:
    owner = _owner(runtime)
    if owner is None:
        raise PermissionError("owner credentials are not initialized")
    if username.strip().lower() != owner["username"]:
        audit(runtime, "owner.login.denied", reason="unknown_user")
        raise PermissionError("invalid owner credentials")
    salt = bytes.fromhex(owner["salt"])
    expected = bytes.fromhex(owner["hash"])
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                 int(owner["iterations"]))
    if not hmac.compare_digest(digest, expected):
        audit(runtime, "owner.login.denied", reason="bad_password")
        raise PermissionError("invalid owner credentials")
    if scope not in SCOPES:
        raise ValueError(f"unknown scope: {scope}")
    moment = time.time() if now is None else float(now)
    token = secrets.token_urlsafe(32)
    session = {"token_hash": hashlib.sha256(token.encode()).hexdigest(),
               "scope": scope, "actor": "owner", "created_at": _now_iso(),
               "expires_at": moment + max(60, int(ttl_seconds))}
    store = _read_json(_path(runtime) / "owner-sessions.json", {"schema": SCHEMA, "sessions": []})
    sessions = [row for row in store.get("sessions") or []
                if float(row.get("expires_at") or 0) > moment]
    sessions.append(session)
    _write_json(_path(runtime) / "owner-sessions.json",
                {"schema": SCHEMA, "sessions": sessions[-50:]})
    audit(runtime, "owner.login.ok", username=owner["username"], scope=scope)
    return {"token": token, "scope": scope, "expires_at": session["expires_at"],
            "actor": "owner"}


def verify(runtime, token: str, *, scope: str | None = None,
           now: float | None = None) -> dict:
    moment = time.time() if now is None else float(now)
    digest = hashlib.sha256(str(token or "").encode()).hexdigest()
    store = _read_json(_path(runtime) / "owner-sessions.json", {"sessions": []})
    for row in store.get("sessions") or []:
        if hmac.compare_digest(str(row.get("token_hash") or ""), digest):
            if float(row.get("expires_at") or 0) <= moment:
                audit(runtime, "owner.session.denied", reason="expired")
                raise PermissionError("owner session expired")
            if row.get("actor") != "owner":
                raise PermissionError("session actor is not the owner")
            if scope is not None and row.get("scope") != scope:
                audit(runtime, "owner.session.denied", reason="scope",
                      required=scope, actual=row.get("scope"))
                raise PermissionError(f"session scope {row.get('scope')} cannot do {scope}")
            return row
    audit(runtime, "owner.session.denied", reason="unknown_token")
    raise PermissionError("invalid owner session")


def revoke(runtime, token: str) -> None:
    digest = hashlib.sha256(str(token or "").encode()).hexdigest()
    store = _read_json(_path(runtime) / "owner-sessions.json", {"sessions": []})
    keep = [row for row in store.get("sessions") or []
            if not hmac.compare_digest(str(row.get("token_hash") or ""), digest)]
    _write_json(_path(runtime) / "owner-sessions.json",
                {"schema": SCHEMA, "sessions": keep})
    audit(runtime, "owner.logout")


class SecureApprovalGate:
    """OwnerApprovalInbox üzerinde kimlik + kapsam + denetim kapısı."""

    def __init__(self, runtime, inbox) -> None:
        self.runtime = Path(runtime)
        self.inbox = inbox

    def _owner_session(self, token: str) -> dict:
        return verify(self.runtime, token, scope="approvals")

    def approve(self, request_id: str, *, token: str, actor: str = "owner"):
        try:
            self._owner_session(token)
            if str(actor).strip().lower() != "owner":
                raise PermissionError("only the owner may approve; agents cannot self-approve")
        except PermissionError as exc:
            audit(self.runtime, "approval.denied", request_id=request_id,
                  actor=actor, reason=str(exc))
            raise
        decided = self.inbox.approve(request_id)
        audit(self.runtime, "approval.approved", request_id=request_id, actor="owner")
        return decided

    def reject(self, request_id: str, *, token: str, actor: str = "owner"):
        try:
            self._owner_session(token)
            if str(actor).strip().lower() != "owner":
                raise PermissionError("only the owner may reject")
        except PermissionError as exc:
            audit(self.runtime, "approval.denied", request_id=request_id,
                  actor=actor, reason=str(exc))
            raise
        decided = self.inbox.reject(request_id)
        audit(self.runtime, "approval.rejected", request_id=request_id, actor="owner")
        return decided


def emergency_stop(runtime, token: str) -> Path:
    verify(runtime, token, scope="stop")
    path = Path(runtime) / "autonomy.stop"
    path.write_text(f"owner emergency stop {_now_iso()}\n", encoding="utf-8")
    audit(runtime, "autonomy.stop", actor="owner")
    return path


def clear_stop(runtime, token: str) -> None:
    verify(runtime, token, scope="stop")
    (Path(runtime) / "autonomy.stop").unlink(missing_ok=True)
    audit(runtime, "autonomy.resume", actor="owner")
