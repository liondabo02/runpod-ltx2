from __future__ import annotations

import subprocess
from pathlib import Path

from ahos.browser_check import check_page, find_browser, render_report


def _page(tmp_path: Path) -> Path:
    page = tmp_path / "www" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<!doctype html><html lang="tr"><head><title>Mipiluna test</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "</head><body>"
        '<header><h1 id="brand">Mipiluna</h1></header>'
        '<main><section id="home"><div class="cards">'
        '<button class="card" data-game="explore">Renk bahçesi</button>'
        '<button class="card" data-game="paint">Boyama atölyesi</button>'
        '<button class="card" data-game="blocks">Küp ve şekiller</button>'
        "</div></section>"
        '<section id="play" class="hidden"><div id="stage" class="stage"></div></section>'
        "</main></body></html>",
        encoding="utf-8",
    )
    return page


def _runner(dom: str, code: int = 0):
    def _run(argv, timeout):
        return subprocess.CompletedProcess(argv, code, stdout=dom, stderr="")

    return _run


def test_missing_page_fails(tmp_path) -> None:
    result = check_page(tmp_path / "yok.html", tmp_path / "artifacts")

    assert result.ok is False
    assert "bulunamadı" in result.problems[0]


def test_healthy_page_passes(tmp_path) -> None:
    page = _page(tmp_path)
    dom = page.read_text(encoding="utf-8")

    result = check_page(
        page,
        tmp_path / "artifacts",
        browser="edge",
        runner=_runner(dom),
    )

    assert result.ok is True
    assert result.dom_bytes > 200
    assert result.exit_code == 0
    assert result.summary().startswith("tarayıcı: sayfa yüklendi")


def test_empty_dom_fails(tmp_path) -> None:
    page = _page(tmp_path)

    result = check_page(page, tmp_path / "artifacts", browser="edge", runner=_runner(""))

    assert result.ok is False
    assert any("DOM boş" in problem for problem in result.problems)


def test_missing_ui_markers_is_advisory_not_fatal(tmp_path) -> None:
    """Tarayıcı kabul testi değildir: işaret yokluğu tek başına düşürmez.

    Kabul, projenin kendi `tools/check_offline.py` kapısıdır; tarayıcı yalnızca
    "sayfa açıldı mı, JS patladı mı" sorusuna bakar.
    """

    page = _page(tmp_path)
    dom = (
        "<html><head></head><body><p>"
        + ("içerik " * 40)
        + "</p></body></html>"
    )

    result = check_page(page, tmp_path / "artifacts", browser="edge", runner=_runner(dom))

    assert result.ok is True
    assert not any("oyun arayüzü" in problem for problem in result.problems)


def test_render_report_contains_verdict(tmp_path) -> None:
    page = _page(tmp_path)
    result = check_page(
        page,
        tmp_path / "artifacts",
        browser="edge",
        runner=_runner(page.read_text(encoding="utf-8")),
    )

    report = render_report(result)

    assert "Tarayıcı Davranış Kontrolü" in report
    assert "GEÇTİ" in report


def test_find_browser_returns_none_on_missing_paths(monkeypatch) -> None:
    import ahos.browser_check as module

    monkeypatch.setattr(module, "BROWSER_CANDIDATES", (r"C:\yok\edge.exe",))

    assert find_browser() is None

def test_empty_app_shell_fails_after_browser_render(tmp_path) -> None:
    page = _page(tmp_path)
    dom = "<html><head><title>ok</title></head><body><div id='app'></div></body></html>" + (" " * 200)
    result = check_page(page, tmp_path / "evidence", browser="edge", runner=_runner(dom))
    assert result.ok is False
    assert any("boş ekran" in issue for issue in result.problems)


def test_fatal_framework_error_screen_fails(tmp_path) -> None:
    page = _page(tmp_path)
    dom = "<html><head></head><body><h1>Application error: a client-side exception</h1></body></html>" + (" " * 200)
    result = check_page(page, tmp_path / "evidence", browser="edge", runner=_runner(dom))
    assert result.ok is False
    assert any("hata ekranı" in issue for issue in result.problems)


def test_browser_js_error_stderr_fails(tmp_path) -> None:
    page = _page(tmp_path)
    dom = page.read_text(encoding="utf-8")
    def fake(argv, timeout):
        return subprocess.CompletedProcess(argv, 0, stdout=dom, stderr="Uncaught ReferenceError: broken is not defined")
    result = check_page(page, tmp_path / "evidence", browser="edge", runner=fake)
    assert not result.ok
    assert any("JavaScript" in issue for issue in result.problems)


def test_unavailable_browser_is_not_a_pass(tmp_path, monkeypatch) -> None:
    import ahos.browser_check as module
    monkeypatch.setattr(module, "find_browser", lambda: None)
    result = check_page(_page(tmp_path), tmp_path / "evidence")
    assert not result.ok
    assert any("bulunamadı" in issue for issue in result.problems)
