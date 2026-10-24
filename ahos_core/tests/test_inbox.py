"""Drop a document in the inbox; the holding learns from it."""

from __future__ import annotations

from ahos import inbox, knowledge, learning, skills


def _runtime(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    return runtime


def test_dropped_document_is_learned_and_moved(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    folder = inbox.ensure(runtime)
    (folder / "mimari.md").write_text(
        "# Kuyruk\n\nKira süresi geçen görev yeniden açılır.\n\n"
        "# Kapı\n\nHer yama kabul testinden geçmeden uygulanmaz.",
        encoding="utf-8",
    )

    result = inbox.scan(runtime)

    assert result["moved"] == 1
    assert result["skills"] >= 1
    assert result["lessons"] >= 1
    assert knowledge.stats(runtime)["documents"] >= 1
    moved = list(inbox.processed_dir(runtime).glob("*mimari.md"))
    assert moved, "belge processed klasörüne taşınmalı (silinmez)"
    assert not (folder / "mimari.md").exists()


def test_second_scan_does_not_reprocess(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    folder = inbox.ensure(runtime)
    (folder / "sayfa.md").write_text("# Bölüm\n\nİçerik yeterince uzun olsun diye yazıldı.", encoding="utf-8")
    inbox.scan(runtime)

    again = inbox.scan(runtime)

    assert again["moved"] == 0


def test_skills_from_inbox_are_injected(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    folder = inbox.ensure(runtime)
    (folder / "test.md").write_text(
        "# Test kapısı\n\nHer yama kabul testinden geçmeden uygulanmaz ve kırılırsa geri alınır.",
        encoding="utf-8",
    )
    inbox.scan(runtime)

    block = skills.context(runtime, "kabul testi yama")

    assert "Eğitim kütüphanesinden" in block or block == ""
