"""LLM çağrısı ücretli kaynağa gitmesin (V7). Yalnız standart kütüphane; anahtar okumaz/yazdırmaz.

Kural: ücretli çağrı yalnız sahibin açık izniyle (AHOS_ALLOW_PAID=1) yapılır. Bu modül iki şeyi engeller:
  1. Yerel olmayan LLM adresi (localhost/127.0.0.1/::1 dışı): doğrudan ücretli uç olabilir.
  2. Bilinen ücretli model adları (gpt-*, o1/o3/o4, claude/opus/sonnet/haiku, gemini *pro*, grok, openai/..., anthropic/...).
AHOS_FREE_MODELS (virgüllü) listesindeki model adı 2. kuralı geçer. 'auto' gibi bilinmeyen adlar GEÇER ama
maliyeti DOĞRULANMAMIŞTIR: OmniRoute'un arkada neyi seçtiği buradan bilinemez (note alanında yazılır).
"""
import os, re
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PAID_PATTERNS = (r"^gpt[-.]", r"^o[134](-|$)", r"claude", r"\bopus\b", r"\bsonnet\b", r"\bhaiku\b",
                 r"gemini.*pro", r"\bgrok", r"^openai/", r"^anthropic/", r"^azure/", r"^bedrock/")


def check(model, base, env=None):
    """-> {"ok": bool, "reason": str, "note": str}. Karar yalnız girdilerden çıkar (ağ yok)."""
    env = os.environ if env is None else env
    if str(env.get("AHOS_ALLOW_PAID", "")).strip() == "1":
        return {"ok": True, "reason": "", "note": "AHOS_ALLOW_PAID=1: sahibin açık izni var"}
    host = (urlparse(str(base or "")).hostname or "").lower()
    if host not in LOCAL_HOSTS:
        return {"ok": False, "reason": "LLM adresi yerel değil (%s): ücretli uç olabilir; AHOS_ALLOW_PAID=1 gerekir" % (host or "boş"), "note": ""}
    m = str(model or "").strip().lower()
    free = {x.strip().lower() for x in str(env.get("AHOS_FREE_MODELS", "")).split(",") if x.strip()}
    if m in free:
        return {"ok": True, "reason": "", "note": "model AHOS_FREE_MODELS listesinde"}
    for p in PAID_PATTERNS:
        if re.search(p, m):
            return {"ok": False, "reason": "model adı ücretli görünüyor (%s); AHOS_ALLOW_PAID=1 ya da AHOS_FREE_MODELS gerekir" % m, "note": ""}
    return {"ok": True, "reason": "", "note": "maliyet doğrulanmadı: model '%s' yerel ağ geçidinde arkada ne seçeceği bilinmiyor" % m}
