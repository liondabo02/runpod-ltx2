"""Hafif sır taraması: gerçek anahtar desenleri yakalanır, meşru yerler atlanır."""

from __future__ import annotations

from pathlib import Path

from tools.agentshield_lite import main as shield_main


def _run(root: Path, capsys) -> tuple[int, str]:
    code = shield_main(["--root", str(root)])
    return code, capsys.readouterr().out


def test_detects_openai_style_key(tmp_path, capsys):
    (tmp_path / "config.py").write_text('KEY = "sk-' + "a" * 32 + '"\n', encoding="utf-8")
    code, out = _run(tmp_path, capsys)
    assert code == 1
    assert "openai_key" in out
    assert "sk-" not in out.split("findings")[1]  # değer asla yazdırılmaz


def test_env_file_is_the_designated_store(tmp_path, capsys):
    (tmp_path / ".env").write_text("RUNPOD_API_KEY=" + "b" * 40 + "\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# notlar\n", encoding="utf-8")
    code, out = _run(tmp_path, capsys)
    assert code == 0, out
    assert '"clean": true' in out


def test_detects_private_key_block(tmp_path, capsys):
    (tmp_path / "id_rsa").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    code, out = _run(tmp_path, capsys)
    assert code == 1
    assert "private_key" in out
