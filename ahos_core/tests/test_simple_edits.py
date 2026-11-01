from __future__ import annotations

from pathlib import Path

from ahos.simple_edits import apply_simple_edit, parse_simple_edit


def _project(tmp_path: Path) -> Path:
    (tmp_path / "www").mkdir()
    (tmp_path / "www" / "card-keys.js").write_text("// oyun kodu\n", encoding="utf-8")
    return tmp_path


def test_parse_append_comment(tmp_path) -> None:
    root = _project(tmp_path)

    edit = parse_simple_edit(
        root, "www/card-keys.js dosyasının sonuna şu yorumu ekle: // ahos-test"
    )

    assert edit is not None
    assert edit.path == "www/card-keys.js"
    assert edit.text == "// ahos-test"
    assert edit.mode == "append"


def test_parse_returns_none_for_complex_task(tmp_path) -> None:
    root = _project(tmp_path)

    assert parse_simple_edit(root, "oyunu baştan aşağı yeniden tasarla") is None


def test_parse_returns_none_when_file_missing(tmp_path) -> None:
    root = _project(tmp_path)

    assert parse_simple_edit(root, "www/yok.js sonuna ekle: // x") is None


def test_apply_appends_text(tmp_path) -> None:
    root = _project(tmp_path)
    edit = parse_simple_edit(root, "www/card-keys.js sonuna ekle: // eklendi")

    ok, detail = apply_simple_edit(root, edit)

    assert ok is True
    assert (root / "www" / "card-keys.js").read_text(encoding="utf-8").endswith("// eklendi\n")
    assert detail.startswith("append")


def test_apply_is_idempotent(tmp_path) -> None:
    root = _project(tmp_path)
    edit = parse_simple_edit(root, "www/card-keys.js sonuna ekle: // ayni")
    apply_simple_edit(root, edit)

    ok, detail = apply_simple_edit(root, edit)

    assert ok is True          # idempotent: tekrar ekleme başarı sayılır
    assert "zaten" in detail


def test_prepend_mode(tmp_path) -> None:
    root = _project(tmp_path)
    edit = parse_simple_edit(root, "www/card-keys.js başına ekle: // bas")

    ok, _ = apply_simple_edit(root, edit)

    assert ok is True
    assert (root / "www" / "card-keys.js").read_text(encoding="utf-8").startswith("// bas")
