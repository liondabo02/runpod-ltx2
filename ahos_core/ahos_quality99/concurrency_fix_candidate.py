from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Callable


@dataclass(frozen=True, slots=True)
class LockRetryReport:
    acquired: bool
    attempts: int
    transient_permission_errors: int
    timed_out: bool


def retry_transient_lock_create(
    attempt_create: Callable[[], bool],
    *,
    timeout_seconds: float = 1.0,
    poll_seconds: float = 0.01,
) -> LockRetryReport:
    """Prototype the shared-lock portability fix without editing shared code."""
    if timeout_seconds <= 0 or poll_seconds <= 0:
        raise ValueError("positive timeout/poll required")
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    permissions = 0
    while True:
        attempts += 1
        try:
            if attempt_create():
                return LockRetryReport(True, attempts, permissions, False)
        except PermissionError:
            permissions += 1
        if time.monotonic() >= deadline:
            return LockRetryReport(False, attempts, permissions, True)
        time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
