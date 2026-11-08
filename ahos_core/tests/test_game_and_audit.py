"""Oyun üretimi ve uygulama denetimi."""

from __future__ import annotations

from pathlib import Path

from ahos.app_audit import audit_html, audit_path
from ahos.game_builder import GameBrief, audit_game, build_game

GOOD_PAGE = """<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="description" content="örnek açıklama yeterince uzun">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="Örnek">
<link rel="icon" href="data:,">
<link rel="manifest" href="site.webmanifest">
<title>Örnek sayfa</title></head>
<body><h1>Başlık</h1><img src="a.png" alt="açıklama"><a href="#bolum">git</a>
<div id="bolum" role="main" aria-label="içerik">içerik</div></body></html>
"""

BAD_PAGE = """<!doctype html><html><head><title></title></head>
<body><img src="yok.png"><a href="eksik.html">kırık</a><input id="x"></body></html>
"""


def test_build_game_produces_a_playable_file(tmp_path):
    manifest = build_game(GameBrief(title="Test Oyunu", item_name="yıldız"), tmp_path)
    index = Path(manifest["file"])

    assert index.is_file() and manifest["bytes"] > 3000
    assert (tmp_path / "site.webmanifest").is_file()
    report = audit_game(index)
    assert report["passed"] is True, report
    assert report["measurements"]["canvas"] is True
    assert report["measurements"]["loop"] is True
    assert report["measurements"]["syntax_ok"] in (True, None)


def test_audit_game_rejects_a_broken_file(tmp_path):
    broken = tmp_path / "index.html"
    broken.write_text("<html><body>yok</body></html>", encoding="utf-8")
    report = audit_game(broken)
    assert report["passed"] is False
    assert any("eksik" in problem or "küçük" in problem for problem in report["problems"])


def test_audit_html_scores_a_complete_page():
    report = audit_html(text=GOOD_PAGE)
    assert report["passed"] is True, report
    assert report["score"] >= 70
    assert report["counts"]["high"] == 0


def test_audit_html_reports_gaps_with_fixes():
    report = audit_html(text=BAD_PAGE, root=Path("."))
    issues = {finding["issue"] for finding in report["findings"]}
    assert any("meta description" in issue for issue in issues)
    assert any("h1" in issue for issue in issues)
    assert any("alt" in issue for issue in issues)
    assert any("kırık" in issue for issue in issues)
    assert report["passed"] is False
    for finding in report["findings"]:
        assert finding["fix"]


def test_audit_path_accepts_a_folder(tmp_path):
    (tmp_path / "index.html").write_text(GOOD_PAGE, encoding="utf-8")
    (tmp_path / "site.webmanifest").write_text("{}", encoding="utf-8")
    report = audit_path(tmp_path)
    assert report["file"].endswith("index.html")
    assert report["passed"] is True
