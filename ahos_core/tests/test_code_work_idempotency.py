"""The deterministic worker must be idempotent.

Autonomy re-runs the same project capabilities on every mission. If a second
run rewrote files, the loop would produce fake "changes" and endless churn.
"""

from __future__ import annotations

from pathlib import Path

from ahos.code_work import (
    apply_card_keyboard,
    apply_focus_styles,
    apply_hint_module,
    apply_press_feedback,
    apply_text_scale,
    apply_web_hygiene,
    fix_precache,
    install_quality_gate,
    snapshot,
)


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    www = root / "www"
    www.mkdir(parents=True)
    (www / "index.html").write_text(
        "<!doctype html><html><head><title>Oyun</title></head>"
        '<body><div id="stage"><button class="card">Oyna</button></div>'
        '<script src="app.js"></script></body></html>',
        encoding="utf-8",
    )
    (www / "app.js").write_text("const ready = true;\n", encoding="utf-8")
    return root


def _apply_all(root: Path) -> list[str]:
    applied: list[str] = []
    for step in (
        apply_web_hygiene,
        apply_card_keyboard,
        apply_focus_styles,
        apply_press_feedback,
        apply_hint_module,
        apply_text_scale,
        fix_precache,
        install_quality_gate,
    ):
        applied.extend(step(root))
    return applied


def test_deterministic_capabilities_are_idempotent(tmp_path) -> None:
    root = _project(tmp_path)

    first = _apply_all(root)
    after_first = snapshot(root)
    second = _apply_all(root)
    after_second = snapshot(root)

    assert first, "ilk uygulama en az bir değişiklik üretmeli"
    assert after_first == after_second, (
        "ikinci uygulama dosyaları değiştirmemeli: "
        f"{set(after_first) ^ set(after_second)}"
    )
    assert second == [], f"ikinci tur boş olmalı, döndü: {second[:3]}"


def test_capabilities_do_not_touch_outside_the_project(tmp_path) -> None:
    root = _project(tmp_path)
    outside = tmp_path / "outside.js"
    outside.write_text("original", encoding="utf-8")

    _apply_all(root)

    assert outside.read_text(encoding="utf-8") == "original"
