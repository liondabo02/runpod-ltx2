"""Kod modeli seçimi: katmanlı, ücretsizden başlayan, ölçülebilir yönlendirme.

Sorun: tek bir yerel 7B modelle kod görevleri başarısız oluyordu. Profesyonel
çözüm tek model değil, **katmanlı yedekleme**:

1. `local`     — ollama (qwen2.5-coder:7b)        0 $, çevrimdışı
2. `nim`       — NVIDIA NIM ücretsiz kademe        0 $ (kredi), 40 istek/dk
                  qwen/qwen3-coder-480b-a35b-instruct (ajanlı kod için eğitilmiş)
3. `openrouter`— :free SKU'lar                     0 $, model başına ~200 istek/gün
4. `deepseek`  — ücretli son çare                  ~0,25 $/M çıktı

Bu modül anahtarların varlığına bakar, erişilebilirliği ölçer ve **görev sınıfına**
göre (kod / belge / genel) en iyi kullanılabilir sağlayıcıyı seçer. Seçim
`AHOS_LLM_BASE_URL`, `AHOS_LLM_MODEL`, `AHOS_LLM_API_KEY` değişkenlerine yazılır;
böylece mevcut yürütücü kodu değişmeden çalışır.

Ücretli sağlayıcı yalnızca `AHOS_ALLOW_PAID_LLM=1` ise seçilir.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    model: str
    api_key_env: str
    tier: str                 # local | free | paid
    best_for: tuple[str, ...]  # code | document | general
    note: str = ""


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        name="local",
        base_url="http://127.0.0.1:11500/v1",
        model="qwen2.5-coder:7b",
        api_key_env="AHOS_LLM_API_KEY",
        tier="local",
        best_for=("code", "document", "general"),
        note="tünel/ollama; 0 $, çevrimdışı, küçük görevler",
    ),
    Provider(
        name="nim",
        base_url="https://integrate.api.nvidia.com/v1",
        model="qwen/qwen3-coder-480b-a35b-instruct",
        api_key_env="NVIDIA_NIM_API_KEY",
        tier="free",
        best_for=("code",),
        note="ücretsiz kademe; 480B sınıfı, 40 istek/dk, ajanlı kod için eğitilmiş",
    ),
    Provider(
        name="openrouter-free",
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen3-coder:free",
        api_key_env="OPENROUTER_API_KEY",
        tier="free",
        best_for=("code", "general"),
        note="ücretsiz SKU; model başına ~200 istek/gün",
    ),
    Provider(
        name="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        tier="paid",
        best_for=("code", "document", "general"),
        note="son çare; ~0,25 $/M çıktı tokenı",
    ),
)


def _has_key(provider: Provider) -> bool:
    value = os.environ.get(provider.api_key_env, "").strip()
    if provider.tier == "local":
        return True
    return bool(value)


def _reachable(provider: Provider, timeout: float = 4.0) -> bool:
    """Sağlayıcı erişilebilir mi (yalnız GET /models; ücret oluşturmaz)."""

    request = urllib.request.Request(
        provider.base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {os.environ.get(provider.api_key_env, 'x')}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return False


def candidates(task: str = "code", *, probe: bool = False) -> list[Provider]:
    """Görev sınıfına uygun, anahtarı tanımlı sağlayıcılar (ücretsiz önce)."""

    allow_paid = os.environ.get("AHOS_ALLOW_PAID_LLM", "0").strip().lower() in {"1", "true", "yes", "on"}
    order = {"local": 0, "free": 1, "paid": 2}
    found = [
        provider for provider in PROVIDERS
        if task in provider.best_for and _has_key(provider)
        and (provider.tier != "paid" or allow_paid)
    ]
    found.sort(key=lambda provider: (order.get(provider.tier, 9), PROVIDERS.index(provider)))
    if probe:
        found = [provider for provider in found if _reachable(provider)]
    return found


def choose(task: str = "code", *, probe: bool = True) -> Provider | None:
    options = candidates(task, probe=probe)
    if options:
        return options[0]
    # erişim ölçümü hepsini düşürdüyse en az birini yine de dene
    fallback = candidates(task, probe=False)
    return fallback[0] if fallback else None


def apply(provider: Provider) -> dict:
    """Seçilen sağlayıcıyı mevcut yürütücü değişkenlerine yaz."""

    os.environ["AHOS_LLM_BASE_URL"] = provider.base_url
    os.environ["AHOS_LLM_MODEL"] = provider.model
    key = os.environ.get(provider.api_key_env, "").strip()
    if key:
        os.environ["AHOS_LLM_API_KEY"] = key
    os.environ["AHOS_LLM_FREE"] = "1" if provider.tier != "paid" else "0"
    return {
        "provider": provider.name,
        "tier": provider.tier,
        "base_url": provider.base_url,
        "model": provider.model,
        "key_from": provider.api_key_env,
        "has_key": bool(key) or provider.tier == "local",
        "note": provider.note,
    }


def status(*, probe: bool = True) -> dict:
    rows = []
    for provider in PROVIDERS:
        rows.append({
            "name": provider.name,
            "tier": provider.tier,
            "model": provider.model,
            "has_key": _has_key(provider),
            "reachable": _reachable(provider) if probe else None,
            "note": provider.note,
        })
    chosen = choose("code", probe=probe)
    return {
        "providers": rows,
        "chosen_for_code": chosen.name if chosen else None,
        "paid_allowed": os.environ.get("AHOS_ALLOW_PAID_LLM", "0"),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(prog="ahos-model", description="kod modeli seçimi")
    parser.add_argument("--status", action="store_true", help="sağlayıcı durumları")
    parser.add_argument("--choose", choices=["code", "document", "general"], default=None)
    parser.add_argument("--apply", action="store_true", help="seçimi ortama yaz")
    parser.add_argument("--no-probe", action="store_true")
    args = parser.parse_args(argv)

    if args.choose:
        provider = choose(args.choose, probe=not args.no_probe)
        if provider is None:
            print(json.dumps({"ok": False, "reason": "kullanılabilir sağlayıcı yok"}, ensure_ascii=False))
            return 2
        result = apply(provider) if args.apply else {"provider": provider.name, "model": provider.model}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(json.dumps(status(probe=not args.no_probe), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
