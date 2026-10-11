from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite

from .planner import MissionDefinition, MissionPlanner


@dataclass(frozen=True, slots=True)
class RetryMetadata:
    """Immutable retry state for one scheduled mission attempt."""

    attempt: int
    max_attempts: int
    retries_remaining: int
    backoff_seconds: float
    can_retry: bool


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded, deterministic retry and exponential backoff policy."""

    max_attempts: int = 3
    initial_backoff_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        _validate_non_negative_finite(
            self.initial_backoff_seconds, "initial_backoff_seconds"
        )
        if not _is_finite_number(self.backoff_multiplier):
            raise ValueError("backoff_multiplier must be finite")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")
        if self.max_backoff_seconds is not None:
            _validate_non_negative_finite(
                self.max_backoff_seconds, "max_backoff_seconds"
            )

    def backoff_seconds(self, retry_number: int) -> float:
        """Return the delay before a retry, where retry one follows attempt one."""

        if isinstance(retry_number, bool) or not isinstance(retry_number, int):
            raise TypeError("retry_number must be an integer")
        if retry_number < 1 or retry_number >= self.max_attempts:
            raise ValueError(
                f"retry_number must be between 1 and {self.max_attempts - 1}"
            )
        delay = self.initial_backoff_seconds * self.backoff_multiplier ** (retry_number - 1)
        if self.max_backoff_seconds is not None:
            delay = min(delay, self.max_backoff_seconds)
        return delay

    def metadata_for_attempt(self, attempt: int) -> RetryMetadata:
        """Return immutable retry metadata for a one-based scheduled attempt."""

        if isinstance(attempt, bool) or not isinstance(attempt, int):
            raise TypeError("attempt must be an integer")
        if attempt < 1 or attempt > self.max_attempts:
            raise ValueError(f"attempt must be between 1 and {self.max_attempts}")
        backoff = 0.0 if attempt == 1 else self.backoff_seconds(attempt - 1)
        retries_remaining = self.max_attempts - attempt
        return RetryMetadata(
            attempt=attempt,
            max_attempts=self.max_attempts,
            retries_remaining=retries_remaining,
            backoff_seconds=backoff,
            can_retry=retries_remaining > 0,
        )


@dataclass(frozen=True, slots=True)
class ScheduledMission:
    """A local mission selected for a future attempt; it performs no work."""

    mission: MissionDefinition
    retry: RetryMetadata

    @property
    def mission_id(self) -> str:
        return self.mission.mission_id

    @property
    def retry_metadata(self) -> RetryMetadata:
        return self.retry


class LocalScheduler:
    """Select ready local missions without executing or persisting anything."""

    def __init__(
        self,
        missions: Iterable[MissionDefinition] = (),
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._planner = MissionPlanner(missions)
        self.retry_policy = retry_policy or RetryPolicy()

    def schedule(
        self,
        completed_ids: Iterable[str] = (),
        attempts: Mapping[str, int] | None = None,
    ) -> list[ScheduledMission]:
        """Return deterministic ready missions that have not exhausted retries."""

        attempt_counts = {} if attempts is None else dict(attempts)
        for mission_id, attempt in attempt_counts.items():
            if self._planner.get_mission(mission_id) is None:
                raise KeyError(f"unknown mission {mission_id!r}")
            if isinstance(attempt, bool) or not isinstance(attempt, int):
                raise TypeError("attempt counts must be integers")
            if attempt < 0:
                raise ValueError("attempt counts must not be negative")

        scheduled: list[ScheduledMission] = []
        for mission in self._planner.ready_missions(completed_ids):
            attempt = attempt_counts.get(mission.mission_id, 0) + 1
            if attempt <= self.retry_policy.max_attempts:
                scheduled.append(
                    ScheduledMission(
                        mission=mission,
                        retry=self.retry_policy.metadata_for_attempt(attempt),
                    )
                )
        return scheduled


def _is_finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(value)
    except (OverflowError, TypeError):
        return False


def _validate_non_negative_finite(value: object, name: str) -> None:
    if not _is_finite_number(value):
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
