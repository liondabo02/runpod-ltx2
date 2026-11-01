"""Yeniden deneme politikası — Temporal/kuyruk desenlerinin sadeleştirilmiş hâli.

Kurallar:
- Hata sınıfına göre **yeniden denenebilir mi?** kararı verilir.
- Gecikme üstel artar, üst sınır vardır (thundering herd önlenir).
- Aynı hata üst üste 3 kez gelirse görev **eskalasyona** gider (CEO'ya).
"""

from __future__ import annotations

from dataclasses import dataclass

RETRYABLE = {
    "worker_failed",
    "mission_timeout",
    "model_unavailable",
    "no_delivery",
    "target_missing",
    "project_lock",
}
FATAL = {
    "acceptance_failed",
    "cancelled",
    "claim_blocked",
    "executor_missing",
    "other",
}

BASE_DELAY = 30
MAX_DELAY = 900
ESCALATE_AFTER = 3


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    delay_seconds: int
    escalate: bool
    reason: str


def classify_retryable(cause: str) -> bool:
    return cause in RETRYABLE


def backoff(attempt: int, *, base: int = BASE_DELAY, cap: int = MAX_DELAY) -> int:
    """Üstel geri çekilme: 30, 60, 120, 240 … (üst sınır 900 s)."""

    if attempt < 1:
        attempt = 1
    delay = base * (2 ** (attempt - 1))
    return min(cap, delay)


def decide(cause: str, attempt: int, *, escalate_after: int = ESCALATE_AFTER) -> RetryDecision:
    """Hata sınıfı + deneme sayısına göre karar üretir."""

    if not classify_retryable(cause):
        return RetryDecision(False, 0, False, f"yeniden denenemez: {cause}")
    if attempt >= escalate_after:
        return RetryDecision(
            False, 0, True,
            f"{attempt} denemede çözülmedi ({cause}); CEO eskalasyonu",
        )
    return RetryDecision(True, backoff(attempt), False, f"yeniden dene: {cause}")


def plan(runtime_dir, cause: str, attempt: int) -> dict:
    """Kararı sözlük olarak döndürür (kayıt/denetim için)."""

    decision = decide(cause, attempt)
    return {
        "cause": cause,
        "attempt": attempt,
        "retry": decision.retry,
        "delay_seconds": decision.delay_seconds,
        "escalate": decision.escalate,
        "reason": decision.reason,
    }
