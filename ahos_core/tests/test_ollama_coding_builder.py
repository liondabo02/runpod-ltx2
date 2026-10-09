import json
from pathlib import PurePosixPath
import pytest
from ahos import ollama_coding_builder as builder


def response(result, **extra):
    return {"done": True, "message": {"content": json.dumps(result)}, **extra}


def test_local_builder_repairs_scope_violation_before_any_write(tmp_path, monkeypatch):
    target = tmp_path / 'src/app.py'
    target.parent.mkdir()
    target.write_text('VALUE = 1\n')
    replies = iter([
        response({"files": [{"path": "outside.py", "content": "bad"}]}),
        response({"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]}),
    ])
    calls = []
    def post(path, payload, timeout):
        calls.append(json.loads(json.dumps(payload)))
        return next(replies)
    monkeypatch.setattr(builder, '_post', post)
    result = builder.request_edits('task', tmp_path, (PurePosixPath('src'),),
        model='qwen2.5-coder:7b', timeout=1, context_chars=1000, attempts=2)
    assert target.read_text() == 'VALUE = 1\n'
    assert not (tmp_path / 'outside.py').exists()
    assert 'Validation:' in calls[1]['messages'][-1]['content']
    assert calls[0]['stream'] is False
    assert 'Authorization' not in calls[0]
    builder.apply_response(tmp_path, (PurePosixPath('src'),), result)
    assert target.read_text() == 'VALUE = 2\n'


@pytest.mark.parametrize('extra', [{"done": False}, {"done_reason": "length"}])
def test_incomplete_output_does_not_write(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(builder, '_post', lambda *a: response(
        {"files": [{"path": "src/new.py", "content": "VALUE=1\n"}]}, **extra))
    with pytest.raises(builder.CodingBuilderError):
        builder.request_edits('task', tmp_path, (PurePosixPath('src'),),
            model='qwen2.5-coder:7b', timeout=1, context_chars=1000, attempts=1)
    assert list(tmp_path.iterdir()) == []


def test_redirects_rejected():
    with pytest.raises(builder.CodingBuilderError):
        builder._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')


def test_status_never_generates_or_reads_prompt(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['builder', '--status'])
    calls = []
    monkeypatch.setattr(builder, '_post', lambda path, body, timeout: calls.append(path) or {'details': {}})
    assert builder.main() == 0
    assert calls == ['/api/show']
    assert json.loads(capsys.readouterr().out)['coding_execution_verified'] is False


def test_cloud_model_rejected_before_request(monkeypatch):
    monkeypatch.setattr('sys.argv', ['builder', '--model', 'qwen:cloud'])
    monkeypatch.setattr(builder, '_post', lambda *a: pytest.fail('must not send'))
    with pytest.raises(SystemExit):
        builder.main()


@pytest.mark.parametrize('result, gate', [
    ({'files': [{'path': 'secret-token.py', 'content': 'bad'}]}, 'scope:'),
    ({'files': [{'path': 'src/new.py', 'content': 'def broken('}]}, 'python_syntax:'),
    ({'edits': [{'path': 'src/absent.py', 'search': 'x', 'replace': 'y'}]}, 'missing_file:'),
])
def test_failed_gate_is_reported_without_model_paths(tmp_path, monkeypatch, result, gate):
    monkeypatch.setattr(builder, '_post', lambda *a: response(result))
    with pytest.raises(builder.CodingBuilderError) as error:
        builder.request_edits('task', tmp_path, (PurePosixPath('src'),),
            model='qwen2.5-coder:7b', timeout=1, context_chars=1000, attempts=1)
    assert gate in str(error.value)
    assert 'secret-token' not in str(error.value)
    assert 'no files written' in str(error.value)
    assert list(tmp_path.iterdir()) == []
