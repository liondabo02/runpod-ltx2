"""PWA shell capability: installable and offline, idempotent."""

from __future__ import annotations

from ahos.code_work import apply_pwa_shell


def _project(tmp_path):
    root = tmp_path / "proj"
    www = root / "www"
    www.mkdir(parents=True)
    (www / "index.html").write_text(
        "<!doctype html><html lang='tr'><head></head><body><h1>oyun</h1></body></html>",
        encoding="utf-8",
    )
    (www / "precache.js").write_text('const CORE_ASSETS = ["index.html"];\n', encoding="utf-8")
    return root


def test_pwa_shell_creates_manifest_worker_and_wiring(tmp_path) -> None:
    root = _project(tmp_path)

    applied = apply_pwa_shell(root)

    assert applied, "ilk uygulama dosya üretmeli"
    www = root / "www"
    assert (www / "manifest.webmanifest").is_file()
    assert (www / "sw.js").is_file()
    html = (www / "index.html").read_text(encoding="utf-8")
    assert "manifest.webmanifest" in html
    assert "serviceWorker" in html


def test_pwa_shell_is_idempotent(tmp_path) -> None:
    root = _project(tmp_path)
    apply_pwa_shell(root)
    first = (root / "www" / "index.html").read_text(encoding="utf-8")

    second = apply_pwa_shell(root)

    assert second == (), "ikinci uygulama hiçbir şey yapmamalı"
    assert (root / "www" / "index.html").read_text(encoding="utf-8") == first


def test_pwa_shell_keeps_an_existing_manifest(tmp_path) -> None:
    root = _project(tmp_path)
    custom = '{"name": "Özel", "start_url": "./", "display": "standalone", "icons": []}'
    (root / "www" / "manifest.webmanifest").write_text(custom, encoding="utf-8")

    apply_pwa_shell(root)

    assert (root / "www" / "manifest.webmanifest").read_text(encoding="utf-8") == custom


def test_pwa_shell_skips_non_web_project(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    assert apply_pwa_shell(empty) == ()
