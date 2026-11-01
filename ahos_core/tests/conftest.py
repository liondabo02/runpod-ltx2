"""Test-wide defaults.

Birim testleri gerçek ağa veya gerçek modele çıkmamalıdır; aksi halde paket
dakikalarca asılı kalır (model zaman aşımı 600 sn). Burada deterministik
yürütücü zorlanır; ağ isteyen testler kendi sahte taşıyıcısını enjekte eder.

The browser smoke step in ``project_qa`` is enabled in production, but it must
never launch a real browser from the unit suite: it is slow and depends on an
installed browser. Tests that exercise it inject a fake and switch the env var
back on explicitly.
"""

import os

os.environ["AHOS_BROWSER_QA"] = "0"
os.environ["AHOS_MODEL_BROWSER_CHECK"] = "0"
os.environ["AHOS_GATE_DELTA"] = "0"

# Gerçek model çağrılarını kapat: testler model yürütücüsünü kullanmamalı.
os.environ["AHOS_EXECUTOR"] = "deterministic"
os.environ["AHOS_PROVIDER_CHAIN"] = "0"
for _name in (
    "AHOS_LLM_BASE_URL",
    "AHOS_LLM_API_KEY",
    "AHOS_LLM_MODEL",
    "AHOS_LLM_MODELS",
    "AHOS_LLM_FREE",
    "AHOS_FALLBACK_BASE_URL",
    "AHOS_FALLBACK_API_KEY",
    "AHOS_FALLBACK_MODEL",
):
    os.environ.pop(_name, None)

# Kısa görev süresi: bir test yanlışlıkla gerçek iş başlatırsa dakikalarca asılı kalmasın.
os.environ.setdefault("AHOS_MISSION_TIMEOUT_SECONDS", "20")

# Testlerin çoğu geçici (git dışı) dizinlerde kabul kapısı sabitler. Üretimde bu
# yalnızca açık sahip izniyle veya sürüm kontrolündeki temiz bir kapı için olur;
# kuralın kendisi ``test_acceptance_trust.py`` içinde ayrıca sınanır.
os.environ.setdefault("AHOS_ACCEPTANCE_ALLOW_UNTRACKED", "1")
