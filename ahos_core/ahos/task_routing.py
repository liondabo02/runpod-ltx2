"""G017 — 30 görev tipi için model/araç yönlendirme politikası.

Mevcut `model_router.pick()` yalnız model adı seçer; bu modül görev tipini
sınıflandırır, deterministik işleri modelden uzak tutar, QA'yı bağımsız
değerlendiriciye yollar ve ücretli modeli açık onay + bütçe kapısına bağlar.

Model çağrısı yapmaz; yalnız gerekçeli rota üretir.
"""

from __future__ import annotations

import os

DETERMINISTIC = "deterministic"
LOCAL_LIGHT = "local_light"
STRONG = "strong_model"
CODE = "code_model"
VISION = "vision"
VIDEO = "video"
RESEARCH = "research"
QA = "qa"

TASK_TYPES: dict[str, str] = {
    "simple_edit": DETERMINISTIC,
    "deterministic_append": DETERMINISTIC,
    "file_check": DETERMINISTIC,
    "schema_validate": DETERMINISTIC,
    "status_report": DETERMINISTIC,
    "arithmetic_check": DETERMINISTIC,
    "health_check": DETERMINISTIC,
    "doc_template": DETERMINISTIC,
    "summarize_short": LOCAL_LIGHT,
    "rewrite_short": LOCAL_LIGHT,
    "translate_short": LOCAL_LIGHT,
    "classify_text": LOCAL_LIGHT,
    "faq_answer": LOCAL_LIGHT,
    "architecture_review": STRONG,
    "strategy_analysis": STRONG,
    "complex_debug": STRONG,
    "legal_analysis": STRONG,
    "financial_model_analysis": STRONG,
    "research_synthesis": STRONG,
    "code_patch": CODE,
    "test_generation": CODE,
    "refactor": CODE,
    "api_design": CODE,
    "image_review": VISION,
    "design_consistency": VISION,
    "ocr_check": VISION,
    "video_render": VIDEO,
    "scene_generation": VIDEO,
    "independent_qa": QA,
    "web_research": RESEARCH,
}

ROUTE_TOOL = {
    DETERMINISTIC: "python",
    VIDEO: "runpod-ltx2",
    RESEARCH: "knowledge-base",
    QA: "independent-verifier",
}

PAID_ROUTES = {STRONG}


def _paid_allowed() -> bool:
    return os.environ.get("AHOS_ALLOW_PAID_LLM", "0").strip().lower() in {
        "1", "true", "yes", "on"}


def _model_for(route_class: str) -> str:
    """Mevcut model_router.pick() üzerinden uç noktaya uygun model adı."""

    try:
        from . import model_router

        kind = "deterministic" if route_class == DETERMINISTIC else "complex"
        picked = model_router.pick(kind)
        if picked:
            return picked
    except Exception:  # noqa: BLE001 - rota üretimi model seçimine bağımlı değil
        pass
    defaults = {
        LOCAL_LIGHT: os.environ.get("AHOS_FALLBACK_MODEL", "qwen2.5-coder:3b"),
        STRONG: os.environ.get("AHOS_PREMIUM_MODEL", "mistralai/mistral-large-4-0"),
        CODE: os.environ.get("AHOS_LLM_MODEL", "qwen2.5-coder:7b"),
        VISION: os.environ.get("AHOS_VISION_MODEL", "gpt-4o-mini"),
    }
    return defaults.get(route_class, "")


def route(task_type: str, *, budget_usd: float | None = None,
          paid_allowed: bool | None = None) -> dict:
    route_class = TASK_TYPES.get(str(task_type))
    if route_class is None:
        return {"task_type": task_type, "route": "unrouted", "model": None,
                "paid": False, "qa_independent": False,
                "reason": "bilinmeyen görev tipi; önce sınıflandır"}
    allowed = _paid_allowed() if paid_allowed is None else bool(paid_allowed)
    if route_class in PAID_ROUTES:
        enough_budget = budget_usd is None or float(budget_usd) > 0
        if allowed and enough_budget:
            return {"task_type": task_type, "route": route_class,
                    "model": _model_for(route_class), "paid": True,
                    "qa_independent": False,
                    "reason": "karmaşık analiz; ücretli model onaylı ve bütçe var"}
        return {"task_type": task_type, "route": route_class,
                "model": _model_for(LOCAL_LIGHT), "paid": False,
                "qa_independent": False,
                "reason": ("karmaşık analiz; ücretli kapalı → ücretsiz yedek"
                           if not allowed else
                           "karmaşık analiz; bütçe yok → ücretsiz yedek")}
    tool = ROUTE_TOOL.get(route_class)
    model = tool if tool else _model_for(route_class)
    reasons = {
        DETERMINISTIC: "deterministik iş; model çağrısı yok",
        LOCAL_LIGHT: "küçük metin işi; hafif yerel model",
        CODE: "kodlama işi; kod modeli",
        VISION: "görsel iş; görsel model",
        VIDEO: "video işi; üretim hattı",
        RESEARCH: "kaynak tarama; yerel bilgi ağı",
        QA: "QA üreticiden bağımsız değerlendirici",
    }
    return {"task_type": task_type, "route": route_class, "model": model,
            "paid": False, "qa_independent": route_class == QA,
            "reason": reasons.get(route_class, "standart rota")}


def report(*, budget_usd: float | None = None) -> list[dict]:
    return [route(name, budget_usd=budget_usd) for name in TASK_TYPES]


if __name__ == "__main__":
    import json

    for row in report():
        print(json.dumps(row, ensure_ascii=False))
