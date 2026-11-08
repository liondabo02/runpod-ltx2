"""Cooperative cancellation for missions.

A mission runs in a worker thread. When its deadline expires we cannot kill a
Python thread, so instead we revoke a per-mission token. Every file write that
belongs to a mission passes through :func:`guard`; a revoked token raises
``MissionCancelled`` before the write happens. The owner console additionally
waits a bounded time for the worker thread to observe the revocation, so a
"timed out" mission is only reported as cancelled when the worker really
stopped writing.
"""

from __future__ import annotations

import contextvars
import threading
import uuid


class MissionCancelled(RuntimeError):
    """Raised inside a worker when its mission token has been revoked."""


class MissionToken:
    def __init__(self, mission_id: str) -> None:
        self.mission_id = mission_id
        self.token_id = uuid.uuid4().hex[:12]
        self._revoked = threading.Event()
        self.finished = threading.Event()

    @property
    def revoked(self) -> bool:
        return self._revoked.is_set()

    def revoke(self) -> None:
        self._revoked.set()

    def guard(self) -> None:
        if self.revoked:
            raise MissionCancelled(
                f"mission {self.mission_id} token {self.token_id} iptal edildi"
            )


_CURRENT: contextvars.ContextVar[MissionToken | None] = contextvars.ContextVar(
    "ahos_mission_token", default=None
)


def activate(token: MissionToken) -> None:
    _CURRENT.set(token)


def deactivate() -> None:
    _CURRENT.set(None)


def current() -> MissionToken | None:
    return _CURRENT.get()


def guard() -> None:
    token = _CURRENT.get()
    if token is not None:
        token.guard()
