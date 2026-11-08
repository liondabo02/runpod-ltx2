from __future__ import annotations

from pathlib import Path

from ahos.targets import mentioned_files, missing_targets, suggest_targets


def _project(tmp_path: Path) -> Path:
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "card-keys.js").write_text("// oyun\n", encoding="utf-8")
    (tmp_path / "www" / "style.css").write_text("body{}\n", encoding="utf-8")
    return tmp_path


def test_mentioned_files_extracts_extension_names() -> None:
    found = mentioned_files("www/card-keys.js dosyasına yorum ekle ve style.css güncelle")

    assert "www/card-keys.js" in found
    assert "style.css" in found


def test_mentioned_files_ignores_plain_words() -> None:
    assert mentioned_files("oyunu geliştir ve hızlandır") == ()


def test_missing_targets_detects_absent_file(tmp_path) -> None:
    root = _project(tmp_path)

    missing = missing_targets(root, "www/yok-boyle-dosya.js içine kod ekle")

    assert missing == ("www/yok-boyle-dosya.js",)


def test_missing_targets_accepts_existing_file(tmp_path) -> None:
    root = _project(tmp_path)

    assert missing_targets(root, "www/card-keys.js içine yorum ekle") == ()


def test_missing_targets_accepts_file_in_other_folder(tmp_path) -> None:
    root = _project(tmp_path)

    assert missing_targets(root, "style.css dosyasını düzelt") == ()


def test_suggest_targets_offers_similar_names(tmp_path) -> None:
    root = _project(tmp_path)

    suggestions = suggest_targets(root, "card-key.js dosyasına ekle")

    assert "www/card-keys.js" in suggestions
