"""Premium model katmanı — yalnız ücretsiz zincir tükendiğinde.

Kural:
1. Ücretsiz zincir (yerel 1.5b/7b, tünel 3b/7b) denenir.
2. Hepsi başarısız olursa ve **günlük bütçe dolmadıysa** premium model çağrılır.
3. Her çağrının maliyeti `runtime/premium-spend.jsonl` dosyasına yazılır.

Varsayılan model `mistralai/mistral-large-4-0` (1M bağlam, function calling,
OpenRouter üzerinden ~$0,004/görev). Bütçe varsayılanı **$0,50/gün**.

Kapalı olması için: `AHOS_ALLOW_PAID_LLM=0` veya `AHOS_PREMIUM_ENABLED=0`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "mistralai/mistral-large-4-0"
DEFAULT_DAILY_USD = 0.50


class PremiumUnavailable(RuntimeError):
    """Premium katman kapalı veya anahtar yok."""


class PremiumBudgetExceeded(RuntimeError):
    """Günlük premium bütçesi doldu."""


@dataclass(frozen=True)
class PremiumResult:
    text: str
    cost_usd: float
    model: str
    tokens: int


def _state_path(runtime: Path) -> Path:
    return runtime / "premium-spend.jsonl"


def enabled() -> bool:
    paid = os.environ.get("AHOS_ALLOW_PAID_LLM", "0").strip().lower()
    premium = os.environ.get("AHOS_PREMIUM_ENABLED", "1").strip().lower()
    return paid in {"1", "true", "yes", "on"} and premium in {"1", "true", "yes", "on"}


def api_key() -> str:
    key = os.environ.get("AHOS_PREMIUM_API_KEY", "").strip()
    if key:
        return key
    return os.environ.get("AHOS_LLM_API_KEY", "").strip()


def daily_cap() -> float:
    try:
        return float(os.environ.get("AHOS_PREMIUM_DAILY_USD", str(DEFAULT_DAILY_USD)))
    except ValueError:
        return DEFAULT_DAILY_USD


def spent_today(runtime_dir: str | Path, *, day: str | None = None) -> float:
    runtime = Path(runtime_dir)
    path = _state_path(runtime)
    if not path.exists():
        return 0.0
    today = day or time.strftime("%Y-%m-%d")
    total = 0.0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("day")) != today:
            continue
        try:
            total += float(row.get("cost_usd") or 0.0)
        except (TypeError, ValueError):
            continue
    return round(total, 6)


def _record(runtime: Path, *, model: str, cost: float, tokens: int) -> None:
    path = _state_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "day": time.strftime("%Y-%m-%d"),
                    "model": model,
                    "cost_usd": round(cost, 6),
                    "tokens": tokens,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _http_transport(model: str, key: str, system: str, prompt: str, max_tokens: int) -> dict:
    import urllib.request

    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
    ).encode()
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


def extract_text(payload: dict) -> str:
    """`content` boşsa `reasoning` alanına düş (reasoning modelleri)."""

    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        return ""
    text = (message.get("content") or "").strip()
    if text:
        return text
    return (message.get("reasoning") or "").strip()


def call_premium(
    system: str,
    prompt: str,
    runtime_dir: str | Path,
    *,
    max_tokens: int = 900,
    model: str | None = None,
    transport=None,
) -> PremiumResult:
    """Ücretli modeli çağırır; bütçe ve kayıt kurallarını uygular."""

    runtime = Path(runtime_dir)
    if not enabled():
        raise PremiumUnavailable("premium katman kapalı (AHOS_ALLOW_PAID_LLM / AHOS_PREMIUM_ENABLED)")

    key = api_key()
    if not key:
        raise PremiumUnavailable("API anahtarı yok")

    spent = spent_today(runtime)
    cap = daily_cap()
    if spent >= cap:
        raise PremiumBudgetExceeded(f"günlük premium bütçe doldu: ${spent:.4f} >= ${cap:.2f}")

    chosen = (model or os.environ.get("AHOS_PREMIUM_MODEL", DEFAULT_MODEL)).strip()
    send = transport or _http_transport
    try:
        payload = send(chosen, key, system, prompt, max_tokens)
    except Exception as exc:  # noqa: BLE001 - yetki/ağ hatalarını sadeleştir
        status = getattr(exc, "code", None)
        if status in {401, 402, 403, 429}:
            raise PremiumUnavailable(f"premium erişimi yok (HTTP {status}); anahtar/kota kontrol et") from exc
        raise PremiumUnavailable(f"premium çağrısı başarısız: {type(exc).__name__}") from exc

    text = extract_text(payload)
    if not text:
        raise PremiumUnavailable("premium model boş yanıt döndü")

    usage = payload.get("usage") or {}
    cost = float(usage.get("cost") or 0.0)
    tokens = int(usage.get("total_tokens") or 0)
    _record(runtime, model=chosen, cost=cost, tokens=tokens)
    return PremiumResult(text=text, cost_usd=cost, model=chosen, tokens=tokens)
