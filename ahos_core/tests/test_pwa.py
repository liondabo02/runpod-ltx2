"""PWA readiness checks (installable + offline cache)."""

from __future__ import annotations

import json

from ahos.pwa import validate_pwa

MANIFEST = {
    "name": "Mipiluna",
    "start_url": "./index.html",
    "display": "standalone",
    "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}],
}


def _project(tmp_path, *, manifest: bool = True, sw: bool = True, link: bool = True):
    www = tmp_path / "www"
    www.mkdir(parents=True)
    head = '<link rel="manifest" href="manifest.webmanifest">' if link else ""
    body = (
        "<script>navigator.serviceWorker.register('sw.js');</script>" if sw else ""
    )
    (www / "index.html").write_text(
        f"<!doctype html><html lang='tr'><head>{head}</head><body>{body}</body></html>",
        encoding="utf-8",
    )
    (www / "precache.js").write_text('const CORE_ASSETS = ["index.html"];\n', encoding="utf-8")
    if manifest:
        (www / "manifest.webmanifest").write_text(json.dumps(MANIFEST), encoding="utf-8")
        (www / "icon-192.png").write_bytes(b"\x89PNG")
    (www / "sw.js").write_text(
        "importScripts('./precache.js');\n"
        "self.addEventListener('fetch', function (event) {});\n",
        encoding="utf-8",
    )
    return tmp_path


def test_complete_pwa_is_ready(tmp_path) -> None:
    result = validate_pwa(_project(tmp_path))

    assert result["ready"] is True, result["problems"]


def test_missing_manifest_link_is_reported(tmp_path) -> None:
    result = validate_pwa(_project(tmp_path, link=False))

    assert result["ready"] is False
    assert any("manifest bağlı" in problem for problem in result["problems"])


def test_missing_service_worker_registration_is_reported(tmp_path) -> None:
    result = validate_pwa(_project(tmp_path, sw=False))

    assert result["ready"] is False
    assert any("service worker" in problem for problem in result["problems"])


def test_missing_icon_file_is_reported(tmp_path) -> None:
    root = _project(tmp_path)
    (root / "www" / "icon-192.png").unlink()

    result = validate_pwa(root)

    assert result["ready"] is False
    assert any("ikon" in problem for problem in result["problems"])
