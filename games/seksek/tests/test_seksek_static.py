"""Seksek oyunu — statik kabul testleri (tarayıcı gerektirmez)."""
from __future__ import annotations

from pathlib import Path

GAME = Path(__file__).resolve().parents[1]
HTML = (GAME / "index.html").read_text(encoding="utf-8")


def test_single_game_seksek():
    assert "Mipiluna · Seksek" in HTML
    assert HTML.count("id:'seksek'") == 1
    assert "id:'bestas'" not in HTML


def test_required_gameplay_controls_exist():
    assert 'id="startBtn"' in HTML
    assert 'id="score"' in HTML
    assert 'id="lives"' in HTML
    assert 'id="cv"' in HTML
    assert "pointerdown" in HTML and "pointerup" in HTML
    assert "touch-action" in HTML


def test_restart_and_qa_hooks_exist():
    assert "window.__qa" in HTML
    assert "restart:" in HTML
    assert "qp.get('auto') === '1'" in HTML


def test_audio_assets_present_and_not_empty():
    for name in ("t-02-seksek.mp3", "t-01-merhaba.mp3", "k-02-dogru.mp3", "k-03-yanlis.mp3"):
        path = GAME / "voices" / name
        assert path.is_file() and path.stat().st_size > 1000, name
