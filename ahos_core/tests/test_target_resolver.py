from __future__ import annotations

from pathlib import Path

from ahos.target_resolver import resolve_objective


def _project(tmp_path: Path) -> Path:
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "card-keys.js").write_text("// oyun\n", encoding="utf-8")
    (tmp_path / "www" / "style.css").write_text("body{}\n", encoding="utf-8")
    (tmp_path / "www" / "oyun-yazi.js").write_text("// yazi\n", encoding="utf-8")
    return tmp_path


def test_existing_target_is_unchanged(tmp_path) -> None:
    root = _project(tmp_path)

    text, replaced = resolve_objective(root, "www/card-keys.js dosyasına yorum ekle")

    assert text == "www/card-keys.js dosyasına yorum ekle"
    assert replaced == ()


def test_missing_target_is_rewritten_to_real_file(tmp_path) -> None:
    root = _project(tmp_path)

    text, replaced = resolve_objective(root, "style.css dosyasına renk ekle")

    assert "www/style.css" in text
    assert replaced


def test_missing_target_with_similar_name(tmp_path) -> None:
    root = _project(tmp_path)

    text, replaced = resolve_objective(root, "card-key.js dosyasına yorum ekle")

    assert "www/card-keys.js" in text
    assert replaced


def test_unknown_target_without_match_is_kept(tmp_path) -> None:
    root = _project(tmp_path)

    text, replaced = resolve_objective(root, "tamamen-ilgisiz-veri.xyz dosyasını sil")

    assert "tamamen-ilgisiz-veri.xyz" in text
    assert replaced == ()


def test_android_copies_are_not_offered(tmp_path) -> None:
    root = _project(tmp_path)
    (root / "android" / "app").mkdir(parents=True)
    (root / "android" / "app" / "card-keys.js").write_text("x", encoding="utf-8")

    text, _ = resolve_objective(root, "card-keys.js dosyasına yorum ekle")

    assert "android" not in text
