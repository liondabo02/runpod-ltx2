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


def test_real_user_start_button_targets_game_metadata():
    assert "startGame(GAMES[0]);" in HTML
    assert "startGame(current);" not in HTML


def test_eight_square_gameplay_and_no_synthetic_victory():
    assert "target++;" in HTML
    assert "if (target > 8)" in HTML
    assert "phase = 'completed';" in HTML
    assert "if (phase === 'flight' && flight)" in HTML
    assert "__qa.finish" not in HTML
    assert "finish: function()" not in HTML


def test_other_seven_game_engines_removed_from_standalone_page():
    for banned in ("function Bestas()", "function YakarTop()", "function YerdenYuksek()",
                   "function YediKule()", "function Saklambac()", "function Sayilar()",
                   "function Harfler()"):
        assert banned not in HTML
    assert "var CLASSES = { seksek: Seksek };" in HTML
