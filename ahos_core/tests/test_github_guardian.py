from __future__ import annotations

import json

import pytest

from ahos.github_guardian import (
    GuardianJournal,
    next_actions,
    render_report,
    scan_repository,
)


def _make_repo(tmp_path, *, dirty: bool):
    root = tmp_path / ("dirty" if dirty else "clean")
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (root / "app.py").write_text("print('hello')\n", encoding="utf-8")

    if dirty:
        (root / ".env.runtime").write_text(
            "LLM_API_KEY=sk-proj-K9mQ2xR4tY6uW8zB1cE3hJ5nL0pS7dF\n",
            encoding="utf-8",
        )
        (root / "requirements.txt").write_text("requests>=2.0\n", encoding="utf-8")
        (root / "app.py.bak").write_text("eski kod", encoding="utf-8")
    else:
        (root / ".gitignore").write_text(".env*\n*.bak\n", encoding="utf-8")
        (root / ".env").write_text("DEMO=1\n", encoding="utf-8")
        (root / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    return root


def test_dirty_repository_produces_high_and_critical_findings(tmp_path) -> None:
    report = scan_repository(_make_repo(tmp_path, dirty=True))

    rules = {finding.rule_id for finding in report.findings}

    assert "gitignore-missing" in rules
    assert "env-not-ignored" in rules
    assert "secret-in-file" in rules
    assert "unpinned-dependencies" in rules
    assert "backup-files" in rules
    assert "ci-missing" in rules
    assert report.ok is False
    assert report.branch == "main"


def test_clean_repository_is_ok(tmp_path) -> None:
    report = scan_repository(_make_repo(tmp_path, dirty=False))

    assert report.findings == ()
    assert report.ok is True


def test_report_rendering_contains_findings_table(tmp_path) -> None:
    report = scan_repository(_make_repo(tmp_path, dirty=True))

    text = render_report(report)

    assert "Güvenlik ve Kaynak Koruma Raporu" in text
    assert "AKSİYON GEREKİYOR" in text
    assert "`env-not-ignored`" in text


def test_next_actions_map_to_findings(tmp_path) -> None:
    report = scan_repository(_make_repo(tmp_path, dirty=True))

    actions = next_actions(report)

    assert actions
    assert any("gitignore" in action.lower() for action in actions)
    assert any("döndür" in action.lower() or "rotate" in action.lower() for action in actions)


def test_journal_appends_reports(tmp_path) -> None:
    report = scan_repository(_make_repo(tmp_path, dirty=True))
    journal = GuardianJournal(tmp_path / "security" / "guardian.jsonl")

    journal.append(report)
    journal.append(report)

    history = journal.history()
    assert len(history) == 2
    assert history[0]["ok"] is False
    assert "secret-in-file" in history[0]["findings"]


def test_missing_repository_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        scan_repository(tmp_path / "yok")


def test_guardian_executor_writes_security_artifacts(tmp_path) -> None:
    from ahos.github_guardian import make_guardian_executor
    from ahos.workforce_execution import WorkItem

    repo = _make_repo(tmp_path, dirty=True)
    executor = make_guardian_executor(repo, tmp_path / "artifacts")
    item = WorkItem(
        task_id="M-1:brief",
        title="Depo taraması",
        department="guvenlik",
        required_capabilities=frozenset({"secret_scan"}),
    )

    result = executor(item, "guvenlik-secret-scanner")

    assert result.success is True
    artifact = tmp_path / "artifacts" / "M-1_brief" / "SECURITY_REPORT.md"
    assert artifact.exists()
    assert "Güvenlik" in artifact.read_text(encoding="utf-8")
    findings = json.loads(
        (artifact.parent / "findings.json").read_text(encoding="utf-8")
    )
    assert findings["ok"] is False
