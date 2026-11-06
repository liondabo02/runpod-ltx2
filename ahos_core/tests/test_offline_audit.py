"""Offline independence audit tests."""

from __future__ import annotations

from ahos.offline_audit import audit


def _project(tmp_path, *, external: bool = False, gate: bool = True):
    root = tmp_path / "proj"
    (root / "www").mkdir(parents=True)
    script = (
        '<script src="https://cdn.example.com/lib.js"></script>'
        if external
        else '<script src="app.js"></script>'
    )
    (root / "www" / "index.html").write_text(
        '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width"><title>x</title></head>'
        f'<body>{script}<a href="https://example.com/sayfa">dış bağlantı</a></body></html>',
        encoding="utf-8",
    )
    (root / "www" / "app.js").write_text("const a = 1;\n", encoding="utf-8")
    (root / "www" / "precache.js").write_text('const PRECACHE = ["app.js"];\n', encoding="utf-8")
    if gate:
        (root / "tools").mkdir()
        (root / "tools" / "check_offline.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    return root


def test_clean_project_is_offline_ready(tmp_path) -> None:
    report = audit(_project(tmp_path))

    assert report["offline_ready"] is True
    assert report["findings"] == []
    assert report["external_references"] == 0


def test_external_script_is_a_blocker(tmp_path) -> None:
    report = audit(_project(tmp_path, external=True))

    assert report["offline_ready"] is False
    kinds = [finding["kind"] for finding in report["findings"]]
    assert "external_dependency" in kinds


def test_plain_anchor_to_internet_is_not_a_blocker(tmp_path) -> None:
    report = audit(_project(tmp_path))

    # <a href> bir bağlantıdır, kaynak yüklemez; çevrimdışı çalışmayı bozmaz.
    assert report["external_references"] == 0


def test_missing_gate_and_cache_are_reported(tmp_path) -> None:
    root = _project(tmp_path, gate=False)
    (root / "www" / "precache.js").unlink()

    report = audit(root)

    kinds = [finding["kind"] for finding in report["findings"]]
    assert "no_acceptance_gate" in kinds
    assert "no_offline_cache" in kinds
