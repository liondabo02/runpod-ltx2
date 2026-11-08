"""Skill coverage: does the learned library match the work we do?"""

from __future__ import annotations

import json

from ahos import skilleval, skills


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "docker.md").write_text(
        "# Docker\n\nİmaj içine parola koyma; çalışma kullanıcısını açık belirle.",
        encoding="utf-8",
    )
    (docs / "rag.md").write_text(
        "# RAG\n\nBelgeleri anlam sınırlarına göre parçala ve kaynak kimliği ekle.",
        encoding="utf-8",
    )
    skills.learn(runtime, docs)
    return runtime


def test_coverage_hits_and_misses(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    result = skilleval.coverage(runtime, ["docker imaj parola", "kubernetes autoscaling"])

    assert result["tasks"] == 2
    assert result["with_skill"] >= 1
    assert result["rate"] > 0


def test_missing_topics_are_listed(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    missing = skilleval.gaps(runtime, ["kubernetes autoscaling", "quantum derleyici"])

    assert missing, "kapsanmayan konu listelenmeli"


def test_usage_is_logged_and_counted(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    cards = skills.retrieve(runtime, "docker parola", limit=2)

    skilleval.log_usage(runtime, "docker parola", cards)

    rows = skilleval.usage_rows(runtime)
    assert rows and rows[-1]["skills"], "enjekte edilen kartlar kaydedilmeli"
    report = skilleval.report(runtime)
    assert report["injections"] >= 1
    assert report["cards"] >= 1
