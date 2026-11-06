from __future__ import annotations

from ahos.model_planner import (
    build_context,
    propose_objectives,
    validate_objectives,
)


DEPARTMENTS = {"oyun": "Oyun Geliştirme", "ai-platform": "AI Platform"}


def test_validation_keeps_only_well_formed_objectives() -> None:
    payload = {
        "objectives": [
            {"department": "oyun", "title": "Kartlara sesli geri bildirim ekle", "why": "a"},
            {"department": "yok", "title": "Bilinmeyen departman için görev", "why": "b"},
            {"department": "oyun", "title": "kısa", "why": "c"},
            {"department": "oyun", "title": "Kartlara sesli geri bildirim ekle", "why": "d"},
        ]
    }

    cleaned = validate_objectives(payload, DEPARTMENTS)

    assert [item["title"] for item in cleaned] == ["Kartlara sesli geri bildirim ekle"]


def test_validation_respects_limit_and_recent_titles() -> None:
    payload = {
        "objectives": [
            {"department": "oyun", "title": "Daha önce yapılmış bir görev", "why": ""},
            {"department": "oyun", "title": "Yeni bir kart oyunu ekle ve test et", "why": ""},
            {"department": "ai-platform", "title": "Panelde maliyet grafiği göster", "why": ""},
        ]
    }

    cleaned = validate_objectives(
        payload, DEPARTMENTS, recent=["Daha önce yapılmış bir görev"], limit=2
    )

    assert len(cleaned) == 2
    assert cleaned[0]["department"] == "oyun"
    assert cleaned[1]["department"] == "ai-platform"


def test_propose_objectives_uses_transport_and_parses_json() -> None:
    calls: list[str] = []

    def transport(system: str, prompt: str, settings) -> str:
        calls.append(prompt)
        return (
            '{"objectives":[{"department":"oyun","title":"Boyalı oyunlara yeni tema ekle",'
            '"why":"çeşitlilik"}]}'
        )

    objectives = propose_objectives(
        DEPARTMENTS,
        {"oyun": ["mipiluna"], "ai-platform": ["foundry"]},
        recent=["eski görev"],
        settings=object(),
        transport=transport,
    )

    assert objectives == [
        {
            "department": "oyun",
            "title": "Boyalı oyunlara yeni tema ekle",
            "why": "çeşitlilik",
        }
    ]
    assert "mipiluna" in calls[0] and "eski görev" in calls[0]


def test_propose_objectives_caps_the_planner_timeout(monkeypatch) -> None:
    from ahos.llm_executor import ModelSettings

    settings = ModelSettings(
        base_url="https://openrouter.ai/api/v1",
        api_key="k",
        model="m:free",
        timeout_seconds=300,
    )
    monkeypatch.setenv("AHOS_PLANNER_TIMEOUT", "20")
    seen: dict = {}

    def transport(system, prompt, used):
        seen["timeout"] = used.timeout_seconds
        return '{"objectives":[]}'

    propose_objectives(DEPARTMENTS, {}, settings=settings, transport=transport)

    assert seen["timeout"] == 20, "planlama turu 20 sn ile sınırlanmalı"


def test_propose_objectives_returns_empty_on_failure() -> None:
    def broken(system: str, prompt: str, settings) -> str:
        raise RuntimeError("model yok")

    assert propose_objectives(DEPARTMENTS, {}, settings=object(), transport=broken) == []


def test_context_lists_departments_projects_and_history() -> None:
    context = build_context(DEPARTMENTS, {"oyun": ["mipiluna"]}, ["önceki iş"])

    assert "oyun (Oyun Geliştirme) → mipiluna" in context
    assert "ai-platform (AI Platform) → proje yok" in context
    assert "- önceki iş" in context
