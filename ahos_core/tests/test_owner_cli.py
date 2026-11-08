from __future__ import annotations

from ahos.owner_cli import main


def test_owner_cli_status_on_empty_runtime(tmp_path, capsys) -> None:
    code = main(["--runtime-dir", str(tmp_path), "durum"])

    assert code == 0
    out = capsys.readouterr().out
    assert out.strip(), "durum komutu boş çıktı vermemeli"


def test_owner_cli_task_goes_through_the_console(tmp_path, capsys) -> None:
    python = tmp_path / "proj"
    (python / "pkg").mkdir(parents=True)
    (python / "pkg" / "mod.py").write_text("print(1)\n", encoding="utf-8")

    code = main(
        [
            "--runtime-dir",
            str(tmp_path / "rt"),
            "yazılım departmanı kur",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "Yazılım" in out or "yazılım" in out.lower()


def test_owner_cli_unknown_command_still_answers(tmp_path, capsys) -> None:
    code = main(["--runtime-dir", str(tmp_path), "bilinmeyen", "komut"])

    assert code in (0, 1)
    assert capsys.readouterr().out.strip()
