"""CEO diagnosis: root cause, evidence, fix and department dispatch."""

from __future__ import annotations

from ahos import ceo_brain, goals


def _rows():
    return [
        {"mission_id": "CMD-1", "objective": "A", "department": "oyun", "summary": "", "cause": "queue_stuck"},
        {"mission_id": "CMD-2", "objective": "B", "department": "oyun", "summary": "", "cause": "queue_stuck"},
        {"mission_id": "CMD-3", "objective": "C", "department": "oyun",
         "summary": "yama hedefi 3 kez bulundu", "cause": "patch_ambiguous"},
    ]


def test_diagnose_groups_and_ranks(monkeypatch) -> None:
    monkeypatch.setattr(ceo_brain, "collect", lambda runtime, limit=200: _rows())

    result = ceo_brain.diagnose("/tmp/does-not-matter")

    assert result["failures"] == 3
    assert result["findings"][0]["cause"] == "queue_stuck"
    assert result["findings"][0]["count"] == 2
    assert result["findings"][0]["owner"] == "software"
    assert result["top"]["fix"]


def test_explain_names_root_cause_and_fix(monkeypatch) -> None:
    monkeypatch.setattr(ceo_brain, "collect", lambda runtime, limit=200: _rows())

    text = ceo_brain.explain(ceo_brain.diagnose("/tmp/does-not-matter"))

    assert "Kök neden" in text
    assert "Çözüm" in text
    assert "Sorumlu" in text
    assert "Kanıt" in text


def test_classify_maps_signals() -> None:
    assert ceo_brain._classify("") == "queue_stuck"
    assert ceo_brain._classify("yama hedefi 4 kez bulundu") == "patch_ambiguous"
    assert ceo_brain._classify("yama hedefi bulunamadı") == "patch_missing"
    assert ceo_brain._classify("model çıktısı geçersiz: JSON çözümlenemedi") == "json_parse"
    assert ceo_brain._classify("doğrulama başarısız; değişiklikler geri alındı") == "acceptance"
    assert ceo_brain._classify("günlük model bütçesi doldu") == "budget"


def test_dispatch_opens_a_goal_for_the_owner(tmp_path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(ceo_brain, "collect", lambda runtime_dir, limit=200: _rows())

    created = ceo_brain.dispatch(runtime, limit=2)

    assert created, "en az bir hedef açılmalı"
    assert goals.load(runtime, created[0]["goal_id"]) is not None
    assert created[0]["department"] in {"software", "oyun", "holding"}
