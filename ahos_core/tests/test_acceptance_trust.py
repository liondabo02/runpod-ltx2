import hashlib
import json
import pytest
from ahos.acceptance import trusted_gate

@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project'
    (root/'tools').mkdir(parents=True)
    gate = root/'tools/check_offline.py'
    gate.write_text('# independently reviewed test\n')
    baseline = tmp_path/'trusted/baseline.json'
    baseline.parent.mkdir()
    return root, gate, baseline

def enroll(gate, baseline):
    baseline.write_text(json.dumps({str(gate.resolve()).lower():hashlib.sha256(gate.read_bytes()).hexdigest()}))

def test_missing_baseline_does_not_create_trust(project):
    root, gate, baseline = project
    assert not trusted_gate(root, baseline)[0]
    assert not baseline.exists()

def test_preapproved_gate_is_accepted_without_mutating_record(project):
    root, gate, baseline = project
    enroll(gate,baseline)
    before=baseline.read_bytes()
    assert trusted_gate(root,baseline)[0]
    assert baseline.read_bytes()==before

def test_changed_candidate_is_rejected(project):
    root,gate,baseline=project
    enroll(gate,baseline)
    gate.write_text('# changed')
    assert not trusted_gate(root,baseline)[0]

@pytest.mark.parametrize('bad',['{broken','[]','null','{}','{"key":42}','{"key":"not-a-hash"}'])
def test_invalid_baseline_never_reenrolls(project,bad):
    root,gate,baseline=project
    baseline.write_text(bad)
    assert not trusted_gate(root,baseline)[0]
    assert baseline.read_text()==bad

def test_wrong_project_not_added(project,tmp_path):
    root,gate,baseline=project
    enroll(gate,baseline)
    other=tmp_path/'other'
    (other/'tools').mkdir(parents=True)
    (other/'tools/check_offline.py').write_bytes(gate.read_bytes())
    before=baseline.read_bytes()
    assert not trusted_gate(other,baseline)[0]
    assert baseline.read_bytes()==before

def test_duplicate_manifest_key_rejected(project):
    root,gate,baseline=project
    key=json.dumps(str(gate.resolve()).lower())
    value=json.dumps(hashlib.sha256(gate.read_bytes()).hexdigest())
    baseline.write_text('{'+key+':'+value+','+key+':'+value+'}')
    assert not trusted_gate(root,baseline)[0]

def test_oversize_gate_rejected(project):
    root,gate,baseline=project
    gate.write_bytes(b'x'*(1024*1024+1))
    enroll(gate,baseline)
    assert not trusted_gate(root,baseline)[0]


def test_untracked_project_needs_owner_opt_in(project, monkeypatch):
    """Git dışı projede kapı ancak açık sahip izniyle sabitlenir."""
    from ahos.acceptance_bootstrap import ensure_baseline

    root, gate, baseline = project
    monkeypatch.delenv("AHOS_ACCEPTANCE_ALLOW_UNTRACKED", raising=False)

    enrolled, reason = ensure_baseline(root, baseline.parent)
    assert enrolled is False
    assert "sürüm kontrolü" in reason
    assert not (baseline.parent / "acceptance-baseline.json").exists()

    monkeypatch.setenv("AHOS_ACCEPTANCE_ALLOW_UNTRACKED", "1")
    enrolled, reason = ensure_baseline(root, baseline.parent)
    assert enrolled is True, reason


def test_git_tracked_gate_is_pinned_and_tamper_is_refused(tmp_path):
    """Git projesinde temiz kapı sabitlenir; işçi değiştirirse sabitleme reddedilir."""
    import subprocess

    from ahos.acceptance_bootstrap import ensure_baseline

    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    gate = repo / "tools" / "check_offline.py"
    gate.write_text("print('v1')\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)

    evidence = tmp_path / "evidence"
    enrolled, reason = ensure_baseline(repo, evidence)
    assert enrolled is True, reason

    # Aday kabul testini değiştirir: yeni bir sabitleme yapılmamalı.
    gate.write_text("print('v2 - always pass')\n", encoding="utf-8")
    fresh = tmp_path / "evidence2"
    enrolled, reason = ensure_baseline(repo, fresh)
    assert enrolled is False
    assert "değişmiş" in reason
    assert not (fresh / "acceptance-baseline.json").exists()
