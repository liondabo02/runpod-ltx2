"""Heuristic planner: real objectives without a model or a network."""

from __future__ import annotations

from ahos.heuristic_planner import scan


def _project(tmp_path, extra_html: str = "", scripts: int = 0):
    root = tmp_path / "proj"
    (root / "www").mkdir(parents=True)
    (root / "www" / "index.html").write_text(
        f"<!doctype html><html {extra_html}><head><title>x</title></head><body></body></html>",
        encoding="utf-8",
    )
    for index in range(scripts):
        (root / "www" / f"mod{index}.js").write_text("const a = 1;\n" * 10, encoding="utf-8")
    return root


def test_flags_missing_html_metadata(tmp_path) -> None:
    root = _project(tmp_path)

    objectives = scan(root)

    joined = " | ".join(objectives)
    assert "lang" in joined
    assert "viewport" in joined
    assert "charset" in joined


def test_clean_simple_page_only_reports_real_gaps(tmp_path) -> None:
    root = _project(
        tmp_path,
        extra_html='lang="tr"',
        scripts=1,
    )
    html = root / "www" / "index.html"
    html.write_text(
        '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        "<title>x</title></head><body></body></html>",
        encoding="utf-8",
    )

    objectives = scan(root)

    assert all("lang" not in item or "dil" not in item for item in objectives)
    assert all("viewport" not in item for item in objectives)


def test_oversized_script_is_split_suggestion(tmp_path) -> None:
    root = _project(tmp_path, extra_html='lang="tr"')
    (root / "www" / "index.html").write_text(
        '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width"></head></html>',
        encoding="utf-8",
    )
    (root / "www" / "big.js").write_text("// x\n" * 40_000, encoding="utf-8")

    objectives = scan(root)

    assert any("modullere ayir" in item for item in objectives)


def test_limit_and_dedupe(tmp_path) -> None:
    root = _project(tmp_path)
    (root / "www" / "big.js").write_text("// x\n" * 40_000, encoding="utf-8")

    objectives = scan(root, limit=2)

    assert len(objectives) <= 2
    assert len(set(objectives)) == len(objectives)


def test_missing_directory_returns_nothing(tmp_path) -> None:
    assert scan(tmp_path / "yok") == []
