"""No-cost, read-only preflight for local AHOS model inference.

The /models endpoint proves only that HTTP is alive. This validates that
an explicitly configured local model actually returns non-empty text.
Remote/billed endpoints are rejected; this module does NOT alter active routing.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Preflight:
    available: bool
    model: str
    reason: str
    http_status: int | None = None
    base_url: str = ""


def _loopback_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("only explicit local HTTP endpoints are allowed")
    try:
        addr = ipaddress.ip_address(parsed.hostname)
    except ValueError as exc:
        raise ValueError("use a numeric loopback address; hostname/DNS is forbidden") from exc
    if not addr.is_loopback:
        raise ValueError("remote endpoints require a separate owner-approved test")
    if parsed.query or parsed.fragment:
        raise ValueError("query and fragment not supported")
    base = base_url.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def check_local_inference(base_url: str, model: str, *, timeout: float = 12) -> Preflight:
    """Reject false /models positives; at most one tiny, bounded generation."""
    if not model.strip() or timeout <= 0 or timeout > 30:
        return Preflight(False, model, "invalid_model_or_timeout")
    try:
        base = _loopback_url(base_url)
    except ValueError:
        return Preflight(False, model, "remote_or_unsafe_endpoint")
    payload = {
        "model": model,
        "stream": False,
        "max_tokens": 12,
        "messages": [{"role": "user", "content": "Reply with exactly READY."}],
    }
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            # An untrusted endpoint may return enormous data.
            raw = response.read(64_001)
        if status != 200:
            return Preflight(False, model, "non_200_inference", status)
        if len(raw) > 64_000:
            return Preflight(False, model, "oversized_response", status)
        body = json.loads(raw.decode("utf-8"))
        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            return Preflight(False, model, "missing_choices", status)
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return Preflight(False, model, "no_generated_text", status)
        return Preflight(True, model, "inference_ok", status, base)
    except urllib.error.HTTPError as exc:
        return Preflight(False, model, "rate_limited" if exc.code == 429 else f"http_{exc.code}", exc.code)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return Preflight(False, model, "unreachable_or_timeout")
    except (UnicodeError, ValueError, TypeError, KeyError):
        return Preflight(False, model, "malformed_inference_response")


def select_free_model(
    candidates: tuple[tuple[str, str], ...],
    *,
    timeout: float = 8,
) -> tuple[Preflight | None, tuple[Preflight, ...]]:
    """Try bounded local endpoints in priority order; report every failure.

    The caller must explicitly provide numeric loopback endpoints; no paid
    service or DNS endpoint can be queried through this selection path.
    """
    if not candidates:
        return None, ()
    attempts: list[Preflight] = []
    for base_url, model in candidates[:4]:
        result = check_local_inference(base_url, model, timeout=timeout)
        attempts.append(result)
        if result.available:
            return result, tuple(attempts)
    return None, tuple(attempts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded free local inference preflight")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--model", default="qwen2.5-coder:1.5b")
    parser.add_argument("--timeout", type=float, default=12)
    parser.add_argument("--fallback-base-url", default="")
    parser.add_argument("--fallback-model", default="")
    args = parser.parse_args(argv)
    if bool(args.fallback_base_url) != bool(args.fallback_model):
        parser.error("fallback base URL and model must be supplied together")
    if args.fallback_base_url:
        selected, attempts = select_free_model((
            (args.base_url, args.model),
            (args.fallback_base_url, args.fallback_model),
        ), timeout=args.timeout)
        print(json.dumps({
            "available": selected is not None,
            "selected": asdict(selected) if selected else None,
            "attempts": [asdict(entry) for entry in attempts],
        }, ensure_ascii=False))
        return 0 if selected else 2
    result = check_local_inference(args.base_url, args.model, timeout=args.timeout)
    print(json.dumps(asdict(result), ensure_ascii=False))
    return 0 if result.available else 2


if __name__ == "__main__":
    raise SystemExit(main())
