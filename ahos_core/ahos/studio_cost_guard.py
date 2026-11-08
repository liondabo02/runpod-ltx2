"""Stüdyo maliyet ve döngü koruması — saf, yan etkisiz politikalar."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class LoopGuard(RuntimeError):
    pass


@dataclass(frozen=True)
class Policy:
    max_tokens: int = 12000
    max_cost_usd: float = 0.0
    max_retries: int = 2
    pending_cap: int = 300
    require_paid_approval: bool = True
    cheap_first: bool = True


MODEL_BY_KIND = {"cheap": "local-cheap", "standard": "local-standard", "paid": "remote-paid"}


def authorize(kind: str, *, pending: int, cached: bool, owner_approval: bool,
              policy: Policy = Policy()) -> dict:
    """Bir görevin LLM kullanıp kullanamayacağını ve hangi modeli kullanacağını söyler."""
    if kind == "deterministic":
        return {"allowed": False, "reason": "deterministic_local_only", "model": None}
    if cached:
        return {"allowed": False, "reason": "cache_hit", "model": None}
    if pending > policy.pending_cap:
        return {"allowed": False, "reason": "pending_cap_exceeded", "model": None}
    if kind == "paid" and policy.require_paid_approval and not owner_approval:
        return {"allowed": False, "reason": "paid_requires_owner_approval", "model": None}
    model = MODEL_BY_KIND.get(kind, "local-cheap")
    return {"allowed": True, "reason": "ok", "model": model,
            "max_tokens": policy.max_tokens, "max_cost_usd": policy.max_cost_usd}


def estimate_tokens(text: str) -> int:
    """Kaba tahmin; gerçek kullanım değildir."""
    return max(1, len(text) // 4)


def charge(tokens: int, cost_usd: float, policy: Policy = Policy()) -> dict:
    if tokens > policy.max_tokens:
        raise BudgetExceeded(f"token {tokens} > {policy.max_tokens}")
    if cost_usd > policy.max_cost_usd:
        raise BudgetExceeded(f"maliyet {cost_usd} > {policy.max_cost_usd}")
    return {"tokens": tokens, "cost_usd": cost_usd, "within_budget": True}


def guard_attempts(attempts: int, policy: Policy = Policy()) -> int:
    if attempts > policy.max_retries:
        raise LoopGuard(f"deneme {attempts} > {policy.max_retries}")
    return attempts


def load_policy(path: str | Path) -> Policy:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Policy(**{key: data[key] for key in data if key in Policy.__dataclass_fields__})


def policy_dict(policy: Policy = Policy()) -> dict:
    return asdict(policy)
