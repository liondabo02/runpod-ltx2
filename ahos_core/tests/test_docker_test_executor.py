import io
import json
import subprocess
import tarfile

import pytest
from ahos import docker_test_executor as sandbox

IMAGE = 'sha256:' + 'a' * 64


def repo(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=tmp_path, check=True)
    (tmp_path / 'app.py').write_text('VALUE=1\n')
    subprocess.run(['git', 'add', 'app.py'], cwd=tmp_path, check=True)
    subprocess.run(['git', 'commit', '-qm', 'base'], cwd=tmp_path, check=True)
    return tmp_path


def test_candidate_contains_changes_new_scoped_source_and_no_secrets(tmp_path):
    root = repo(tmp_path)
    (root / 'app.py').write_text('VALUE=2\n')
    (root / 'src').mkdir()
    (root / 'src/new.py').write_text('NEW=1\n')
    (root / 'src/.env').write_text('API_KEY=PRIVATE')
    blob = sandbox.candidate_archive(root, ('src',))
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        assert archive.getnames() == ['app.py', 'src/new.py']
        # Preserve candidate bytes including platform-specific newline endings.
        assert archive.extractfile('app.py').read() == (root / 'app.py').read_bytes()
    assert b'PRIVATE' not in blob


def test_deleted_candidate_not_restored_and_sparse_blob_available(tmp_path):
    root = repo(tmp_path)
    (root / 'app.py').unlink()
    blob = sandbox.candidate_archive(root, ())
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        assert archive.getnames() == []


def test_links_outside_additions_and_oversize_fail_closed(tmp_path):
    root = repo(tmp_path)
    (root / 'new.py').write_text('NEW=1')
    with pytest.raises(sandbox.DockerSandboxError, match='outside'):
        sandbox.candidate_archive(root, ())
    (root / 'new.py').unlink()
    with pytest.raises(sandbox.DockerSandboxError, match='budget'):
        sandbox.candidate_archive(root, (), max_bytes=2)
    (root / 'app.py').unlink()
    (root / 'app.py').symlink_to(root / 'outside')
    with pytest.raises(sandbox.DockerSandboxError, match='escapes'):
        sandbox.candidate_archive(root, ())


@pytest.mark.parametrize('command', [
    ['bash', '-c', 'anything'], ['python', '-m', 'pytest', '../owner'],
    ['python', '-m', 'pytest', 'C:\\owner'],
])
def test_commands_fail_before_execution(command):
    with pytest.raises(sandbox.DockerSandboxError):
        sandbox._pytest_command(command)


def test_windows_python_is_mapped_to_image_python():
    assert sandbox._pytest_command(['C:\\venv\\python.exe', '-m', 'pytest', '-q', 'ahos_core/tests']) == [
        'python', '-m', 'pytest', '-p', 'no:cacheprovider', '-q', 'ahos_core/tests']


@pytest.mark.parametrize('image', ['python:latest', 'python:3.12', 'sha256:abc'])
def test_mutable_or_invalid_images_rejected(image):
    with pytest.raises(sandbox.DockerSandboxError):
        sandbox.DockerTestExecutor(image)


class Process:
    def __init__(self, *args, **kwargs):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(b'x' * 5000)
        self.stderr = io.BytesIO(b'')
        self.returncode = 0
    def wait(self, timeout): return self.returncode
    def kill(self): self.returncode = -9


def fake_docker(monkeypatch, *, cleanup=True, timeout=False, image_available=True):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[1:3] == ['image', 'inspect']:
            return subprocess.CompletedProcess(args, 0 if image_available else 1, json.dumps([{'Os': 'linux', 'Config': {}}]), '')
        if args[1] == 'inspect':
            return subprocess.CompletedProcess(args, 0, json.dumps({'Running': False, 'Status': 'exited', 'ExitCode': 0}), '')
        if args[1] == 'ps':
            return subprocess.CompletedProcess(args, 0, '' if cleanup else 'still-present', '')
        return subprocess.CompletedProcess(args, 0, '', '')
    class TimedProcess(Process):
        def wait(self, timeout):
            if self.returncode == 0: raise subprocess.TimeoutExpired('docker', timeout)
            return self.returncode
    monkeypatch.setattr(sandbox.subprocess, 'run', run)
    monkeypatch.setattr(sandbox.subprocess, 'Popen', TimedProcess if timeout else Process)
    monkeypatch.setattr(sandbox, 'candidate_archive', lambda *a: b'archive')
    return calls


def test_restricted_execution_sanitizes_env_bounds_output_and_verifies_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'PRIVATE')
    calls = fake_docker(monkeypatch)
    executor = sandbox.DockerTestExecutor(IMAGE, output_limit=1024)
    result = executor(tmp_path, ['python', '-m', 'pytest', '-q'])
    assert result.returncode == 0 and len(result.stdout) == 1024
    create = next(args for args, kwargs in calls if args[1] == 'create')
    assert '--network' in create and create[create.index('--network') + 1] == 'none'
    assert '--read-only' in create and '--cap-drop' in create
    assert create[create.index('--pids-limit') + 1] == '128'
    assert '--mount' not in create and '-v' not in create
    assert create[create.index('--pull') + 1] == 'never'
    assert all('OPENROUTER_API_KEY' not in kwargs['env'] for args, kwargs in calls)
    assert executor.last_receipt['cleanup_verified'] is True
    assert executor.last_receipt['off_host_verified'] is False
    assert executor.last_receipt['limits']['process_limit'] == 128


def test_timeout_kills_container_and_returns_failure(tmp_path, monkeypatch):
    calls = fake_docker(monkeypatch, timeout=True)
    executor = sandbox.DockerTestExecutor(IMAGE, timeout_seconds=1)
    assert executor(tmp_path, ['python', '-m', 'pytest']).returncode == 124
    assert any(args[1] == 'kill' for args, kwargs in calls)
    assert executor.last_receipt['timed_out'] is True


def test_cleanup_failure_never_returns_success(tmp_path, monkeypatch):
    fake_docker(monkeypatch, cleanup=False)
    with pytest.raises(sandbox.DockerSandboxError, match='cleanup'):
        sandbox.DockerTestExecutor(IMAGE)(tmp_path, ['python', '-m', 'pytest'])


def test_unavailable_image_never_pulls_or_runs(tmp_path, monkeypatch):
    calls = fake_docker(monkeypatch, image_available=False)
    with pytest.raises(sandbox.DockerSandboxError, match='no pull'):
        sandbox.DockerTestExecutor(IMAGE)(tmp_path, ['python', '-m', 'pytest'])
    assert len(calls) == 1


def test_failed_call_clears_previous_receipt(tmp_path, monkeypatch):
    fake_docker(monkeypatch)
    executor = sandbox.DockerTestExecutor(IMAGE)
    executor(tmp_path, ['python', '-m', 'pytest'])
    assert executor.last_receipt
    with pytest.raises(sandbox.DockerSandboxError):
        executor(tmp_path, ['bash'])
    assert executor.last_receipt is None
