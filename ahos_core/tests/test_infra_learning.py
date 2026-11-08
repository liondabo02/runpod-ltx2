"""Infrastructure health and document learning."""

from __future__ import annotations

import json
import time

from ahos import infra, knowledge, learning


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "daemon-state.json").write_text(
        json.dumps({"pid": 1, "status": "running"}), encoding="utf-8"
    )
    (runtime / "company-service.db").write_bytes(b"")
    return runtime


def test_healthy_daemon_is_reported(tmp_path) -> None:
    runtime = _runtime(tmp_path)

    report = infra.check(runtime)

    daemon = next(item for item in report.checks if item.name == "daemon")
    assert daemon.ok is True
    assert report.ok is True


def test_stale_daemon_is_reported(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    old = time.time() - 3600
    import os

    os.utime(runtime / "daemon-state.json", (old, old))

    report = infra.check(runtime)

    daemon = next(item for item in report.checks if item.name == "daemon")
    assert daemon.ok is False
    assert report.ok is False


def test_repair_is_not_called_when_healthy(tmp_path, monkeypatch) -> None:
    runtime = _runtime(tmp_path)
    called: list[str] = []
    monkeypatch.setattr(infra, "repair", lambda *a, **k: called.append("repair") or [])

    infra.health(runtime, fix=True)

    assert called == []


def test_digest_extracts_lessons_offline(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "mimari.md").write_text(
        "# Kuyruk\n\nKira süresi geçen görevler yeniden açılır ve başka işçi alabilir.\n\n"
        "# Test\n\nHer yama kabul testinden geçmeden uygulanmaz.",
        encoding="utf-8",
    )

    result = learning.digest(runtime, docs)

    assert result["lessons"] >= 2
    rows = learning.lessons(runtime, limit=10)
    assert any("kira" in row["lesson"].lower() or "Kuyruk" in row["lesson"] for row in rows)


def test_lessons_are_injected_into_context(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "yigin.md").write_text(
        "# Yığın\n\nHer yama kabul testinden geçmeden uygulanmaz.", encoding="utf-8"
    )
    knowledge.add(runtime, docs)
    learning.digest(runtime, docs)

    block = knowledge.context(runtime, "kabul testi yama")

    assert "Bilgi ağından" in block
    assert "Ders" in block or "yigin.md" in block
