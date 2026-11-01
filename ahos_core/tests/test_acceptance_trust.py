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
