"""Skill cards learned from training documents."""

from __future__ import annotations

import json

from ahos import ceo, skills


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text(
        json.dumps({"status": "running", "executor_mode": "model"}), encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "kuyruk.md").write_text(
        "# Kuyruk güvenliği\n\n"
        "Bir görev sahiplenildiğinde kira süresi yazılır ve süresi geçen kira "
        "yeniden açılır. Böylece çöken işçinin görevi kaybolmaz.\n\n"
        "# Test kapısı\n\n"
        "Her yama kabul testinden geçmeden uygulanmaz; testler kırılırsa değişiklik "
        "geri alınır.",
        encoding="utf-8",
    )
    return runtime, docs


def test_offline_skills_are_extracted_and_retrieved(tmp_path) -> None:
    runtime, docs = _runtime(tmp_path)

    result = skills.learn(runtime, docs)

    assert result["cards"] >= 2
    hits = skills.retrieve(runtime, "kira süresi test kapısı")
    assert hits, "görevle ilgili beceri bulunmalı"
    assert any("kira" in card["rule"].lower() for card in hits)


def test_learning_is_idempotent(tmp_path) -> None:
    runtime, docs = _runtime(tmp_path)
    skills.learn(runtime, docs)

    again = skills.learn(runtime, docs)

    assert again["cards"] == 0
    assert skills.stats(runtime)["cards"] >= 2


def test_skills_context_is_prompt_ready(tmp_path) -> None:
    runtime, docs = _runtime(tmp_path)
    skills.learn(runtime, docs)

    block = skills.context(runtime, "kabul testi kapısı")

    assert "Eğitim kütüphanesinden" in block


def test_ceo_facts_are_grounded_numbers(tmp_path) -> None:
    runtime, _docs = _runtime(tmp_path)
    (runtime / "daemon-missions.jsonl").write_text(
        json.dumps({"status": "routed", "changed_files": 2}) + "\n", encoding="utf-8"
    )

    state = ceo._snapshot(runtime)
    facts = ceo._facts_text(runtime, state)

    assert "teslim_orani=%" in facts
    assert "son_gorevler=" in facts
