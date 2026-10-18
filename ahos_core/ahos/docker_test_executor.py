"""Explicit local Docker test isolation; not an off-host sandbox attestation."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import threading
import uuid
from collections.abc import Sequence


class DockerSandboxError(ValueError):
    pass


_BOOTSTRAP = r'''
import io,json,os,subprocess,sys,tarfile
blob=sys.stdin.buffer.read(67108865)
if len(blob)>67108864: raise SystemExit("candidate archive exceeds limit")
with tarfile.open(fileobj=io.BytesIO(blob),mode="r:") as archive:
    for member in archive.getmembers():
        parts=member.name.split("/")
        if not member.isfile() or member.name.startswith("/") or ".." in parts:
            raise SystemExit("unsafe archive member")
        target=os.path.join("/work",*parts)
        os.makedirs(os.path.dirname(target),exist_ok=True)
        with archive.extractfile(member) as source,open(target,"wb") as output:
            output.write(source.read())
os.chdir("/work")
env={"PATH":"/usr/local/bin:/usr/bin:/bin","HOME":"/tmp", "PYTHONPATH":"/work/ahos_core", "PYTHONNOUSERSITE":"1", "PYTHONDONTWRITEBYTECODE":"1"}
raise SystemExit(subprocess.call(json.loads(sys.argv[1]),env=env))
'''


def _excluded(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return (any(part in {".git", ".venv", "venv", "node_modules", "runtime", "__pycache__"} for part in parts)
            or any(part.lower().startswith(".env") for part in parts)
            or PurePosixPath(name).suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
            or PurePosixPath(name).name.lower() in {"credentials", "credentials.json", "id_rsa", "id_ed25519"})


def _safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or not path.parts:
        raise DockerSandboxError("unsafe candidate path")
    return path


def candidate_archive(worktree: Path, allowed_paths: Sequence[str], max_bytes=64 * 1024 * 1024) -> bytes:
    """Snapshot tracked base/current source and scoped additions, never Git pointers."""
    def git(*args):
        result = subprocess.run(["git", *args], cwd=worktree, capture_output=True, check=False)
        if result.returncode:
            raise DockerSandboxError("candidate Git inventory failed")
        return result.stdout
    records = git("ls-files", "--stage", "-z").decode("utf-8").split("\0")
    tracked = {}
    for record in filter(None, records):
        metadata, name = record.split("\t", 1)
        mode, object_id, stage = metadata.split()
        if stage != "0":
            raise DockerSandboxError("unmerged candidate source")
        if mode != "100644" and mode != "100755":
            raise DockerSandboxError("candidate links or special files are forbidden")
        tracked[name] = object_id
    roots = tuple(PurePosixPath(root) for root in allowed_paths)
    extras = git("ls-files", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    for name in filter(None, extras):
        relative = _safe_relative(name)
        if _excluded(name):
            continue
        if not any(relative == root or root in relative.parents for root in roots):
            raise DockerSandboxError("untracked candidate file is outside approved scope")
        tracked[name] = None
    output = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, object_id in sorted(tracked.items()):
            relative = _safe_relative(name)
            if _excluded(name):
                continue
            path = worktree.joinpath(*relative.parts)
            if path.is_symlink() or not path.resolve().is_relative_to(worktree.resolve()):
                raise DockerSandboxError("candidate path escapes source checkout")
            if path.exists():
                if not path.is_file():
                    raise DockerSandboxError("candidate is not a regular file")
                size = path.stat().st_size
                if total + size > max_bytes:
                    raise DockerSandboxError("candidate exceeds archive budget")
                content = path.read_bytes()
            elif object_id:
                # Sparse Windows checkouts omit untouched tracked files. Read
                # their indexed blobs, but honor actual candidate deletions.
                deleted = git("diff", "HEAD", "--name-only", "--diff-filter=D", "--", name).strip()
                if deleted:
                    continue
                size = int(git("cat-file", "-s", object_id))
                if total + size > max_bytes:
                    raise DockerSandboxError("candidate exceeds archive budget")
                content = git("cat-file", "blob", object_id)
            else:
                raise DockerSandboxError("candidate disappeared during snapshot")
            total += len(content)
            if total > max_bytes:
                raise DockerSandboxError("candidate exceeds archive budget")
            member = tarfile.TarInfo(name)
            member.size = len(content)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(content))
    blob = output.getvalue()
    if len(blob) > max_bytes:
        raise DockerSandboxError("candidate archive exceeds budget")
    return blob


def _pytest_command(command: Sequence[str]) -> list[str]:
    if len(command) < 3 or command[1:3] != ("-m", "pytest") and list(command[1:3]) != ["-m", "pytest"]:
        raise DockerSandboxError("Docker backend accepts Python -m pytest only")
    executable = command[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable not in {"python", "python3", "python.exe", "python3.exe"}:
        raise DockerSandboxError("unsupported sandbox test executable")
    args = list(command[3:])
    for arg in args:
        if arg.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", arg) or ".." in PurePosixPath(arg).parts:
            raise DockerSandboxError("sandbox test argument escapes candidate")
        if arg == "-p" or arg.startswith(("--override-ini", "--confcutdir", "--basetemp")):
            raise DockerSandboxError("unsupported sandbox pytest option")
    return ["python", "-m", "pytest", "-p", "no:cacheprovider", *args]


class DockerTestExecutor:
    execution_mode = "docker"

    def __init__(self, image: str, timeout_seconds: float = 300, allowed_paths: Sequence[str] = (),
                 docker_host: str | None = None, output_limit: int = 1024 * 1024):
        if not re.fullmatch(r"(?:[^\s]+@)?sha256:[0-9a-f]{64}", image):
            raise DockerSandboxError("Docker image must be pinned by SHA256 digest")
        if not 1 <= timeout_seconds <= 900 or not 1024 <= output_limit <= 4 * 1024 * 1024:
            raise DockerSandboxError("invalid sandbox timeout or output budget")
        if docker_host and not docker_host.startswith(("unix://", "npipe://")):
            raise DockerSandboxError("only an explicit local Docker socket endpoint is supported")
        self.image, self.timeout_seconds = image, timeout_seconds
        self.allowed_paths, self.docker_host, self.output_limit = tuple(allowed_paths), docker_host, output_limit
        self.last_receipt = None

    def __call__(self, worktree: Path, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.last_receipt = None
        translated = _pytest_command(command)
        blob = candidate_archive(Path(worktree).resolve(), self.allowed_paths)
        name = "ahos-test-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix="ahos-docker-cli-") as config:
            environment = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
            environment.update({"DOCKER_CONFIG": config, "HOME": config, "USERPROFILE": config})
            prefix = ["docker"] + (["--host", self.docker_host] if self.docker_host else [])
            def control(*args):
                return subprocess.run([*prefix, *args], env=environment, capture_output=True,
                                      text=True, timeout=30, check=False)
            inspection = control("image", "inspect", self.image)
            if inspection.returncode:
                raise DockerSandboxError("pinned sandbox image is not available locally; no pull attempted")
            try:
                image_info = json.loads(inspection.stdout)[0]
                if image_info.get("Os") != "linux" or image_info.get("Config", {}).get("Volumes"):
                    raise DockerSandboxError("sandbox requires Linux image without declared volumes")
            except (ValueError, IndexError, TypeError) as exc:
                raise DockerSandboxError("sandbox image metadata is invalid") from exc
            create = control("create", "--name", name, "--pull", "never", "--network", "none",
                             "--read-only", "--user", "65534:65534", "--cap-drop", "ALL",
                             "--security-opt", "no-new-privileges", "--pids-limit", "128", "--cpus", "1",
                             "--memory", "1024m", "--memory-swap", "1024m", "--log-driver", "none",
                             "--tmpfs", "/work:rw,noexec,nosuid,nodev,size=128m,mode=1777",
                             "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777",
                             "--entrypoint", "python", "-i", self.image, "-c", _BOOTSTRAP, json.dumps(translated))
            if create.returncode:
                raise DockerSandboxError("sandbox container creation failed")
            timed_out = False
            try:
                process = subprocess.Popen([*prefix, "start", "-a", "-i", name], env=environment,
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                captured = [bytearray(), bytearray()]
                def drain(stream, bucket):
                    while chunk := stream.read(8192):
                        bucket.extend(chunk[:max(0, self.output_limit - len(bucket))])
                readers = [threading.Thread(target=drain, args=(process.stdout, captured[0]), daemon=True),
                           threading.Thread(target=drain, args=(process.stderr, captured[1]), daemon=True)]
                for reader in readers: reader.start()
                def feed():
                    try:
                        process.stdin.write(blob)
                        process.stdin.close()
                    except (BrokenPipeError, OSError):
                        pass
                writer = threading.Thread(target=feed, daemon=True)
                writer.start()
                try:
                    process.wait(timeout=self.timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    control("kill", name)
                    process.kill()
                    process.wait(timeout=10)
                writer.join(timeout=5)
                for reader in readers: reader.join(timeout=5)
                if any(reader.is_alive() for reader in readers) or writer.is_alive():
                    raise DockerSandboxError("sandbox I/O did not terminate")
                state = control("inspect", "--format", "{{json .State}}", name)
                if state.returncode:
                    raise DockerSandboxError("sandbox exit state unavailable")
                metadata = json.loads(state.stdout)
                if metadata.get("Running") or metadata.get("Status") != "exited":
                    raise DockerSandboxError("sandbox did not reach a verified exited state")
                code = 124 if timed_out else int(metadata["ExitCode"])
                result = subprocess.CompletedProcess(list(command), code,
                    captured[0].decode("utf-8", "replace"), captured[1].decode("utf-8", "replace"))
            finally:
                removed = control("rm", "--force", name)
                remaining = control("ps", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}")
                if removed.returncode or remaining.returncode or remaining.stdout.strip():
                    raise DockerSandboxError("sandbox cleanup could not be verified")
            self.last_receipt = {"mode": "local_docker", "off_host_verified": False, "image": self.image,
                "candidate_sha256": hashlib.sha256(blob).hexdigest(), "exit_code": code,
                "timed_out": timed_out, "cleanup_verified": True,
                "limits": {"cpu_cores": 1, "memory_mb": 1024, "process_limit": 128,
                           "workspace_mb": 128, "temporary_mb": 32,
                           "timeout_seconds": self.timeout_seconds, "output_bytes_per_stream": self.output_limit},
                "stdout_sha256": hashlib.sha256(captured[0]).hexdigest(),
                "stderr_sha256": hashlib.sha256(captured[1]).hexdigest()}
            return result
