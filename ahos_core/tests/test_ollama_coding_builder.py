import json
import subprocess
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
    assert [p for p in tmp_path.iterdir() if p.name != ".git"] == []


def test_redirects_rejected():
    with pytest.raises(builder.CodingBuilderError):
        builder._NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')


def test_dead_code_proposal_is_repaired_before_any_write(tmp_path, monkeypatch):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    original = "def run():\n    value = 1\n    return value\n"
    target.write_text(original)
    calls = []
    proposals = iter([
        response({"edits": [{"path": "src/app.py", "search": "    value = 1", "replace": "    raise RuntimeError()\n    value = 2"}]}),
        response({"edits": [{"path": "src/app.py", "search": "    value = 1", "replace": "    value = 2"}]}),
    ])
    def post(*args):
        calls.append(args[1])
        assert target.read_text() == original
        return next(proposals)
    monkeypatch.setattr(builder, "_post", post)
    result = builder.request_edits("repair", tmp_path, (PurePosixPath("src"),),
        model="qwen2.5-coder:7b", timeout=1, context_chars=1000, attempts=2)
    assert "unreachable_code:" in calls[1]["messages"][-1]["content"]
    builder.apply_response(tmp_path, (PurePosixPath("src"),), result)
    assert target.read_text() == original.replace("value = 1", "value = 2")


@pytest.mark.parametrize("source", [
    "def run():\n    if False:\n        raise ValueError()\n    return 2\n",
    "def run():\n    try:\n        raise ValueError()\n    except ValueError:\n        return 2\n",
])
def test_conditional_termination_is_not_misclassified(tmp_path, source):
    builder.apply_response(tmp_path, (PurePosixPath("src"),),
        {"files": [{"path": "src/new.py", "content": source}]})
    assert (tmp_path / "src" / "new.py").read_text() == source


def test_existing_dead_code_does_not_block_unrelated_repair(tmp_path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    original = "VALUE = 1\ndef legacy():\n    return 1\n    print('legacy')\n"
    target.write_text(original)
    builder.apply_response(tmp_path, (PurePosixPath("src"),),
        {"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]})
    assert target.read_text() == original.replace("VALUE = 1", "VALUE = 2")


@pytest.mark.parametrize("exception_type", [OSError, ValueError])
def test_provider_errors_do_not_expose_raw_payload(tmp_path, monkeypatch, exception_type):
    private_payload = "PRIVATE_PROVIDER_PAYLOAD_TEST_ONLY"
    def fail_request(*args):
        raise exception_type(private_payload)
    monkeypatch.setattr(builder, "_post", fail_request)
    with pytest.raises(builder.CodingBuilderError) as error:
        builder.request_edits("task", tmp_path, (PurePosixPath("src"),),
            model="qwen2.5-coder:7b", timeout=1, context_chars=1000, attempts=1)
    assert private_payload not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert "Local Ollama request failed" in str(error.value)


def test_status_never_generates_or_reads_prompt(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['builder', '--status'])
    calls = []
    monkeypatch.setattr(builder, '_post', lambda path, body, timeout: calls.append(path) or {'details': {}})
    assert builder.main() == 0
    assert calls == ['/api/show']
    assert json.loads(capsys.readouterr().out)['coding_execution_verified'] is False


@pytest.mark.parametrize("failure, category", [
    (TimeoutError("PRIVATE_PAYLOAD"), "provider_timeout"),
    (builder.urllib.error.URLError(TimeoutError("PRIVATE_PAYLOAD")), "provider_timeout"),
    (ConnectionRefusedError("PRIVATE_PAYLOAD"), "provider_unavailable"),
    (builder.urllib.error.URLError(ConnectionRefusedError("PRIVATE_PAYLOAD")), "provider_unavailable"),
    (builder.urllib.error.HTTPError("http://private.invalid", 503, "PRIVATE_PAYLOAD", {}, None), "provider_http_error"),
    (ValueError("PRIVATE_PAYLOAD"), "provider_response_invalid"),
    (OSError("PRIVATE_PAYLOAD"), "provider_transport_error"),
])
def test_provider_failure_classification_preserves_files(tmp_path, monkeypatch, failure, category):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n")
    def fail_request(*args):
        raise failure
    monkeypatch.setattr(builder, "_post", fail_request)
    with pytest.raises(builder.CodingBuilderError) as error:
        builder.request_edits("repair", tmp_path, (PurePosixPath("src"),),
            model="qwen2.5-coder:7b", timeout=1, context_chars=1000, attempts=2)
    assert category in str(error.value)
    assert "PRIVATE_PAYLOAD" not in str(error.value)
    assert "private.invalid" not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert target.read_text() == "VALUE = 1\n"


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
    assert [p for p in tmp_path.iterdir() if p.name != ".git"] == []


def test_exact_search_repair_reads_omitted_target_without_fuzzy_write(tmp_path, monkeypatch):
    target = tmp_path / "src/app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n" + "# padding\n" * 200)
    replies = iter([
        response({"edits": [{"path": "src/app.py", "search": "VALUE=1", "replace": "VALUE=2"}]}),
        response({"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]}),
    ])
    calls = []
    def post(path, payload, timeout):
        calls.append(json.loads(json.dumps(payload)))
        assert target.read_text().startswith("VALUE = 1")
        return next(replies)
    monkeypatch.setattr(builder, "_post", post)
    result = builder.request_edits("task", tmp_path, (PurePosixPath("src"),),
        model="qwen2.5-coder:7b", timeout=1, context_chars=10, attempts=2)
    assert "VALUE = 1" not in calls[0]["messages"][-1]["content"]
    assert "Actual file: src/app.py" in calls[1]["messages"][-1]["content"]
    assert "VALUE = 1" in calls[1]["messages"][-1]["content"]
    builder.apply_response(tmp_path, (PurePosixPath("src"),), result)
    assert target.read_text().startswith("VALUE = 2")


def test_repair_context_rejects_outside_and_symlink_targets(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("PRIVATE")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/link.txt").symlink_to(outside)
    result = {"edits": [
        {"path": "outside.txt", "search": "PRIVATE", "replace": "x"},
        {"path": "src/link.txt", "search": "PRIVATE", "replace": "x"},
    ]}
    assert builder._repair_context(tmp_path, (PurePosixPath("src"),), result) == ""


def test_repair_candidate_preserves_whitespace_and_never_writes(tmp_path):
    target = tmp_path / "src/app.py"
    target.parent.mkdir()
    source = "def first():\n    return 1\n\ndef second():\n    return 1\n"
    target.write_text(source)
    result = {"edits": [{"path": "src/app.py", "search": "    return 1", "replace": "    return 2"}]}
    context = builder._repair_context(tmp_path, (PurePosixPath("src"),), result)
    marker = "Unique current-source search candidate (JSON string):\n"
    assert "search matches: 2" in context
    candidate = json.loads(context.split(marker, 1)[1].splitlines()[0])
    assert source.count(candidate) == 1
    assert "    return 1\n" in candidate
    assert target.read_text() == source


def test_repair_candidate_is_complete_under_context_budget(tmp_path):
    target = tmp_path / "src/app.py"
    target.parent.mkdir()
    source = "\n".join(f"VALUE_{i} = {i}  # {'padding ' * 30}" for i in range(80)) + "\n"
    target.write_text(source)
    result = {"edits": [{"path": "src/app.py", "search": "VALUE_40=40", "replace": "VALUE_40=41"}]}
    context = builder._repair_context(tmp_path, (PurePosixPath("src"),), result, limit=2000)
    marker = "Unique current-source search candidate (JSON string):\n"
    candidate = json.loads(context.split(marker, 1)[1].splitlines()[0])
    assert source.count(candidate) == 1
    assert "VALUE_40 = 40" in candidate
    assert len(context) <= 2000


@pytest.fixture(autouse=True)
def repository_for_local_builder_tests(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)


def test_missing_target_repair_gets_real_repository_paths(tmp_path, monkeypatch):
    target = tmp_path / "src/app.py"
    target.parent.mkdir()
    target.write_text("VALUE = 1\n")
    subprocess.run(["git", "add", "src/app.py"], cwd=tmp_path, check=True)
    replies = iter([
        response({"edits": [{"path": "src/invented.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]}),
        response({"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]}),
    ])
    calls = []
    def post(path, payload, timeout):
        calls.append(json.loads(json.dumps(payload)))
        return next(replies)
    monkeypatch.setattr(builder, "_post", post)
    result = builder.request_edits("task", tmp_path, (PurePosixPath("src"),),
        model="qwen2.5-coder:7b", timeout=1, context_chars=1000, attempts=2)
    assert "src/app.py" in calls[0]["messages"][-1]["content"]
    assert "missing_file:" in calls[1]["messages"][-1]["content"]
    assert "src/app.py" in calls[1]["messages"][-1]["content"]
    assert not (tmp_path / "src/invented.py").exists()
    assert target.read_text() == "VALUE = 1\n"
    builder.apply_response(tmp_path, (PurePosixPath("src"),), result)
    assert target.read_text() == "VALUE = 2\n"


def test_inventory_excludes_untracked_outside_and_linked_files(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("VALUE = 1")
    (tmp_path / "src/untracked.txt").write_text("private")
    (tmp_path / "outside.txt").write_text("private")
    (tmp_path / "src/link.txt").symlink_to(tmp_path / "outside.txt")
    subprocess.run(["git", "add", "src/app.py", "src/link.txt", "outside.txt"], cwd=tmp_path, check=True)
    assert builder._file_inventory(tmp_path, (PurePosixPath("src"),)) == "src/app.py"


def test_large_relevant_source_is_excerpted_instead_of_omitted(tmp_path):
    (tmp_path / "src").mkdir()
    target = tmp_path / "src/control_center.py"
    target.write_text("# unrelated padding\n" * 2000 +
                      "def render_dashboard(snapshot):\n    return snapshot['heartbeat']\n" +
                      "# trailing padding\n" * 2000)
    subprocess.run(["git", "add", "src/control_center.py"], cwd=tmp_path, check=True)
    context = builder._local_context(tmp_path, (PurePosixPath("src"),), 1200,
                                     "Add System Health to render_dashboard heartbeat")
    assert "def render_dashboard(snapshot):" in context
    assert "    return snapshot['heartbeat']" in context
    assert "Partial source" in context
    assert len(context) <= 1200


def test_local_context_never_reads_untracked_or_symlink_data(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/private.txt").write_text("PRIVATE")
    (tmp_path / "src/link.txt").symlink_to(tmp_path / "src/private.txt")
    subprocess.run(["git", "add", "src/link.txt"], cwd=tmp_path, check=True)
    assert builder._local_context(tmp_path, (PurePosixPath("src"),), 1000, "PRIVATE") == ""


def test_repairs_replace_history_and_retain_entire_original_task(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    target = tmp_path / "src/app.py"
    target.write_text("VALUE = 1\n")
    subprocess.run(["git", "add", "src/app.py"], cwd=tmp_path, check=True)
    original = "Implement every requirement including accessibility and full acceptance tests. " * 20
    calls = []
    replies = iter([
        response({"edits": [{"path": "src/app.py", "search": "wrong", "replace": "x"}]}),
        response({"edits": [{"path": "src/app.py", "search": "still wrong", "replace": "x"}]}),
        response({"edits": [{"path": "src/app.py", "search": "VALUE = 1", "replace": "VALUE = 2"}]}),
    ])
    def post(path, payload, timeout):
        calls.append(json.loads(json.dumps(payload)))
        return next(replies)
    monkeypatch.setattr(builder, "_post", post)
    builder.request_edits(original, tmp_path, (PurePosixPath("src"),),
        model="qwen2.5-coder:7b", timeout=1, context_chars=16000, attempts=3)
    for call in calls:
        assert len(call["messages"]) == 2
        assert original in call["messages"][1]["content"]
        assert call["options"]["num_ctx"] == 8192
    assert "still wrong" in calls[2]["messages"][1]["content"]
    assert calls[2]["messages"][1]["content"].count("Previous failed proposal") == 1
    assert "VALUE = 1" in calls[2]["messages"][1]["content"]
    assert target.read_text() == "VALUE = 1\n"
