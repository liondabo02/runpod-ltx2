"""Provider zinciri: her ücretsiz kaynağı sırayla dene, sağlıklı olanı kullan.

Motivasyon: makinede birden çok ücretsiz model kaynağı var (yerel Ollama, tünel,
OpenRouter ücretsiz modeller). Hangisinin o an çalıştığı değişebilir (429/404).
Bu modül sırayı ve sağlık kontrolünü yönetir; hiçbiri çalışmazsa açıkça hata verir.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    model: str
    api_key: str = "local-only"
    usd_per_call: float = 0.0

    def is_free(self) -> bool:
        return self.usd_per_call == 0.0


def default_chain() -> list[Provider]:
    """Ücretsiz kaynaklar; sıra hızlı/limitsiz olandan yavaş olana."""

    tunnel = os.environ.get("AHOS_LLM_BASE_URL", "http://127.0.0.1:11500/v1")
    chain = [
        # Tünel önce: yerel 3b modeli zaman aşımına düşüyor (URLError/Timeout),
        # tüneldeki 7b daha güvenilir. Yerel model yedek.
        Provider("tunel-ollama", tunnel, os.environ.get("AHOS_LLM_MODEL", "qwen2.5-coder:7b"), "local-only"),
        Provider("lokal-ollama", "http://127.0.0.1:11434/v1", "qwen2.5-coder:1.5b"),
    ]
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if openrouter_key:
        chain.append(
            Provider(
                "openrouter-free",
                "https://openrouter.ai/api/v1",
                os.environ.get("AHOS_OPENROUTER_FREE_MODEL", "cohere/north-mini-code:free"),
                openrouter_key,
            )
        )
    return chain


def probe(provider: Provider, *, timeout: float = 4.0) -> bool:
    """``/models`` uçunu yoklar; 200 dönerse sağlıklı sayılır."""

    url = provider.base_url.rstrip("/")
    if url.endswith("/v1"):
        url += "/models"
    else:
        url += "/v1/models"
    headers = {"Authorization": f"Bearer {provider.api_key}"}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001 - sağlık kontrolü
        return False

    model_ids = {item.get("id") for item in payload.get("data", []) if isinstance(item, dict)}
    if model_ids and provider.model not in model_ids:
        # Örn. OpenRouter ücretsiz modeli kaldırılmış olabilir (404).
        return False
    return True


def choose_chain(chain: list[Provider] | None = None, *, probe_fn=probe) -> tuple[Provider | None, list[tuple[str, bool]]]:
    """İlk sağlıklı sağlayıcıyı ve tüm denemelerin sonucunu döndürür."""

    candidates = chain if chain is not None else default_chain()
    report: list[tuple[str, bool]] = []
    for provider in candidates:
        healthy = bool(probe_fn(provider))
        report.append((provider.name, healthy))
        if healthy:
            return provider, report
    return None, report


def apply_chain_to_env(*, probe_fn=probe, environ=None) -> dict[str, object]:
    """Sağlıklı sağlayıcıyı ortam değişkenlerine yazar (tek çağrı, tek sefer).

    ``AHOS_PROVIDER_CHAIN=1`` iken AHOS açılışında çağrılır; böylece model
    yürütücüsü hangi ücretsiz kaynağın o an ayakta olduğunu kendiliğinden kullanır.
    """

    import os as _os

    env = environ if environ is not None else _os.environ
    def inference_verified(provider: Provider) -> bool:
        # /models=200 is not enough: the configured model must generate text.
        # Local loopback/tunnel endpoints only; never call paid or unknown remote.
        from .provider_preflight import check_local_inference

        result = check_local_inference(provider.base_url, provider.model, timeout=10)
        return result.available

    real_check = str(env.get("AHOS_PROVIDER_INFERENCE_CHECK", "0")).strip().lower()
    use_real = real_check in {"1", "true", "yes", "on"}
    chosen, report = choose_chain(probe_fn=inference_verified if use_real else probe_fn)
    env["AHOS_PROVIDER_REPORT"] = ",".join(
        f"{name}={'ok' if ok else 'yok'}" for name, ok in report
    )
    if chosen is None:
        if use_real:
            # Prevent a stale, previously selected failing endpoint from running.
            for key in ("AHOS_LLM_BASE_URL", "AHOS_LLM_MODEL", "AHOS_LLM_API_KEY",
                        "AHOS_LLM_FREE", "AHOS_ACTIVE_PROVIDER"):
                env.pop(key, None)
            env["AHOS_PROVIDER_INFERENCE_OK"] = "0"
        return {"chosen": None, "report": report}
    if use_real:
        env["AHOS_PROVIDER_INFERENCE_OK"] = "1"
    env["AHOS_LLM_BASE_URL"] = chosen.base_url
    env["AHOS_LLM_MODEL"] = chosen.model
    env["AHOS_LLM_API_KEY"] = chosen.api_key
    env["AHOS_LLM_FREE"] = "1" if chosen.is_free() else "0"
    env["AHOS_ACTIVE_PROVIDER"] = chosen.name
    return {"chosen": chosen.name, "report": report}
