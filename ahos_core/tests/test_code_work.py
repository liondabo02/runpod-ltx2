from __future__ import annotations

from pathlib import Path

from ahos.code_work import (
    apply_web_hygiene,
    detect_web_root,
    diff_snapshots,
    make_project_executor,
    read_texts,
    render_asset_report,
    scan_assets,
    snapshot,
)
from ahos.workforce_execution import WorkItem


def _game_project(tmp_path: Path) -> Path:
    root = tmp_path / "mipiluna"
    www = root / "www"
    www.mkdir(parents=True)
    (www / "index.html").write_text(
        "<html>\n<head>\n<title>Mipiluna</title>\n"
        '<link rel="stylesheet" href="style.css">\n'
        '<script src="missing.js"></script>\n'
        "</head><body><img src=\"assets/logo.png\"></body></html>\n",
        encoding="utf-8",
    )
    (www / "style.css").write_text("body{color:#000}\n", encoding="utf-8")
    assets = www / "assets"
    assets.mkdir()
    (assets / "logo.png").write_bytes(b"\x89PNG")
    return root


def test_detect_web_root_prefers_www(tmp_path) -> None:
    root = _game_project(tmp_path)

    assert detect_web_root(root).name == "www"


def test_asset_scan_finds_missing_references(tmp_path) -> None:
    report = scan_assets(_game_project(tmp_path))

    assert report.referenced == 3
    assert any("missing.js" in item for item in report.missing)
    assert all("logo.png" not in item for item in report.missing)
    assert report.ok is False


def test_web_hygiene_applies_lang_charset_viewport(tmp_path) -> None:
    root = _game_project(tmp_path)

    applied = apply_web_hygiene(root)

    text = (root / "www" / "index.html").read_text(encoding="utf-8")
    assert 'lang="tr"' in text
    assert 'charset="utf-8"' in text or "charset=utf-8" in text
    assert 'name="viewport"' in text
    assert 'alt=""' in text
    assert len(applied) == 4

    # second run is a no-op
    assert apply_web_hygiene(root) == ()


def test_snapshot_diff_reports_real_change(tmp_path) -> None:
    root = _game_project(tmp_path)
    before = snapshot(root)
    before_texts = read_texts(root, tuple(before))

    apply_web_hygiene(root)

    after = snapshot(root)
    changes = diff_snapshots(root, before, after, before_texts=before_texts)

    assert len(changes) == 1
    assert changes[0].path == "www/index.html"
    assert changes[0].change == "modified"
    assert 'lang="tr"' in changes[0].diff
    assert changes[0].diff.startswith("--- a/www/index.html")


def test_asset_report_renders_missing_list(tmp_path) -> None:
    report = scan_assets(_game_project(tmp_path))

    text = render_asset_report(report)

    assert "Görsel Varlık Denetimi" in text
    assert "missing.js" in text


def test_project_executor_writes_real_diff_artifact(tmp_path) -> None:
    root = _game_project(tmp_path)
    executor = make_project_executor(root, tmp_path / "artifacts")

    brief = executor(
        WorkItem(
            task_id="M-1:brief",
            title="denetim",
            department="oyun",
            required_capabilities=frozenset({"testing"}),
        ),
        "oyun-manager",
    )
    produce = executor(
        WorkItem(
            task_id="M-1:produce",
            title="düzeltme",
            department="oyun",
            required_capabilities=frozenset({"javascript"}),
        ),
        "oyun-engineering-lead",
    )

    assert brief.success is True
    assert (tmp_path / "artifacts" / "M-1_brief" / "ASSET_REPORT.md").exists()

    assert produce.success is False
    assert "eksik varlık" in produce.summary
    changes = tmp_path / "artifacts" / "M-1_produce" / "CHANGES.md"
    diff = tmp_path / "artifacts" / "M-1_produce" / "CHANGES.diff"
    assert changes.exists() and diff.exists()
    assert "dosya değişti" in produce.summary
    assert "tools/check_offline.py" in diff.read_text(encoding="utf-8")
    assert 'lang="tr"' in diff.read_text(encoding="utf-8")

def test_quality_gate_is_added_and_runs_clean(tmp_path) -> None:
    import subprocess
    import sys

    from ahos.code_work import install_quality_gate

    root = _game_project(tmp_path)
    applied = install_quality_gate(root)

    gate = root / "tools" / "check_offline.py"
    assert applied and gate.exists()
    assert install_quality_gate(root) == ()

    completed = subprocess.run(
        [sys.executable, str(gate)],
        capture_output=True,
        text=True,
        timeout=60,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 1  # missing.js gerçekten eksik
    assert "missing.js" in completed.stdout

def test_quality_gate_is_recorded_as_added_file(tmp_path) -> None:
    from ahos.code_work import install_quality_gate, read_texts, snapshot, diff_snapshots

    root = _game_project(tmp_path)
    before = snapshot(root)
    before_texts = read_texts(root, tuple(before))

    install_quality_gate(root)

    after = snapshot(root)
    changes = diff_snapshots(root, before, after, before_texts=before_texts)

    assert any(item.path == "tools/check_offline.py" for item in changes)
    added = next(item for item in changes if item.path == "tools/check_offline.py")
    assert added.change == "added"
    assert "+++ b/tools/check_offline.py" in added.diff
