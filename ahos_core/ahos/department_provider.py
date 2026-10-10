"""Explicitly enabled, zero-price AI generation for department work.

Configuration contains no credentials. Configure OPENROUTER_API_KEY in the
service environment; enable allow_external only after owner authorization.
Calls have a bounded socket timeout and no automatic provider retries.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
import urllib.request
import urllib.error
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

from .model_gateway import DataSensitivity, ModelGateway, ModelRouteRequest


class DepartmentProviderError(RuntimeError):
    """Categorized diagnostics; persistence never trusts exception text."""

    _REASONS = {
        "provider": "department provider failed",
        "disabled": "external department generation is disabled",
        "request": "department prompt is empty",
        "auth": "department provider authentication failed; check credential",
        "network": "department provider network request failed",
        "malformed": "department provider returned malformed response",
        "http": "department provider HTTP request failed",
        "rate_limit": "provider rate limit; automatic retry scheduled",
    }

    def __init__(self, message: str = "department provider failed", *,
                 category: str = "provider", http_status: int | None = None) -> None:
        self.category = category if category in self._REASONS else "provider"
        self.http_status = (http_status if type(http_status) is int and 100 <= http_status <= 599 else None)
        super().__init__(message)

    @property
    def safe_diagnostic(self) -> str:
        prefix = f"HTTP {self.http_status}: " if self.http_status else ""
        return prefix + self._REASONS.get(self.category, self._REASONS["provider"])



class DepartmentRateLimited(DepartmentProviderError):
    """Safe local diagnostic: no provider response text or credentials."""

    def __init__(self, retry_after_seconds: float = 300) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("HTTP 429: provider rate limit; automatic retry scheduled", category="rate_limit", http_status=429)


def _retry_delay(value: str | None) -> float:
    try:
        delay = float(value)
    except (TypeError, ValueError):
        try:
            target = parsedate_to_datetime(value)
            delay = (target - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return 300.0
    return min(86400.0, max(60.0, delay)) if math.isfinite(delay) else 300.0


@dataclass(frozen=True)
class DepartmentProviderConfig:
    allow_external: bool = False
    model_id: str = "openrouter/free"
    timeout_seconds: float = 90.0

    def __post_init__(self) -> None:
        if not isinstance(self.allow_external, bool):
            raise ValueError("allow_external must be a boolean")
        if not isinstance(self.model_id, str) or not (
            self.model_id == "openrouter/free" or self.model_id.endswith(":free")
        ):
            raise ValueError("department provider requires a zero-price OpenRouter model")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float)) or not math.isfinite(self.timeout_seconds) or not 1 <= self.timeout_seconds <= 180:
            raise ValueError("timeout_seconds must be between 1 and 180")


class DepartmentGenerator:
    """A real JSON generator; it does not execute generated instructions."""

    def __init__(self, config: DepartmentProviderConfig) -> None:
        if not config.allow_external:
            raise DepartmentProviderError("external department generation is disabled", category="disabled")
        self.config = config
        self.plan = ModelGateway().plan(ModelRouteRequest(
            capability="reasoning", model_id=config.model_id,
            sensitivity=DataSensitivity.INTERNAL, preferred_provider_id="openrouter",
            allow_external=True, owner_approved_paid=False, estimated_cost_usd=0.0,
        ))

    def __call__(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise DepartmentProviderError("department prompt is empty", category="request")
        key = os.environ.get(self.plan.api_key_env, "").strip()
        if not key:
            raise DepartmentProviderError("missing OPENROUTER_API_KEY credential", category="auth")
        # Normalize malformed UTF-16 before JSON serialization, as in coding.
        prompt = prompt.encode("utf-16-le", errors="surrogatepass").decode("utf-16-le", errors="replace")
        body = json.dumps({
            "model": self.plan.model_id,
            "messages": [
                {"role": "system", "content": "You are an AHOS department employee. Complete the assigned work as a concrete artifact. Return strict JSON matching the user's contract. Never claim external actions happened; distinguish evidence, assumptions and blockers."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "provider": {"max_price": {"prompt": 0, "completion": 0}},
        }).encode("utf-8")
        request = urllib.request.Request(
            self.plan.base_url.rstrip("/") + "/chat/completions", data=body,
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                # Bound response memory independently of the runtime contract.
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("response too large")
            payload = json.loads(raw.decode("utf-8"))
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty response")
            json.loads(content)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise DepartmentRateLimited(_retry_delay(exc.headers.get("Retry-After") if exc.headers else None)) from None
            raise DepartmentProviderError(f"department provider HTTP {exc.code}", category="auth" if exc.code in (401, 403) else "http", http_status=exc.code) from None
        except (OSError, urllib.error.URLError) as exc:
            raise DepartmentProviderError("department provider network request failed", category="network") from None
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            # Do not persist exception text or response bodies: either can contain
            # credentials supplied by a remote server.
            raise DepartmentProviderError("department provider request failed: " + type(exc).__name__, category="malformed") from None
        return content


def build_department_generator(config: DepartmentProviderConfig) -> DepartmentGenerator:
    return DepartmentGenerator(config)
