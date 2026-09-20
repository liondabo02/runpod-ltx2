from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
from typing import Mapping, Protocol


class SandboxPolicyError(RuntimeError):
    pass


class SandboxStatus(str, Enum):
    PREPARED = "prepared"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    timeout_seconds: int = 300
    cpu_cores: float = 1.0
    memory_mb: int = 1024
    disk_mb: int = 2048
    process_limit: int = 64

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_seconds <= 900 or not 0.25 <= self.cpu_cores <= 2 or not 128 <= self.memory_mb <= 4096 or not 128 <= self.disk_mb <= 8192 or not 1 <= self.process_limit <= 128:
            raise ValueError("sandbox limits exceed policy")


@dataclass(frozen=True, slots=True)
class SandboxRequest:
    request_id: str
    proposal_id: str
    source_url: str
    source_commit: str
    commands: tuple[tuple[str, ...], ...]
    limits: SandboxLimits = SandboxLimits()
    network_enabled: bool = False
    secrets_enabled: bool = False
    persistent_workspace: bool = False
    docker_socket: bool = False
    host_runner: bool = False


@dataclass(frozen=True, slots=True)
class SandboxPlan:
    request_id: str
    proposal_id: str
    immutable_source: str
    commands: tuple[tuple[str, ...], ...]
    limits: SandboxLimits
    environment: tuple[str, ...]
    status: SandboxStatus = SandboxStatus.PREPARED

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self); payload["schema"] = "ahos.sandbox-plan.v1"; payload["status"] = self.status.value
        return payload


@dataclass(frozen=True, slots=True)
class SandboxReceipt:
    request_id: str
    backend_run_id: str
    exit_code: int
    timed_out: bool
    network_observed: bool
    secrets_mounted: bool
    workspace_destroyed: bool
    stdout_sha256: str
    stderr_sha256: str
    status: SandboxStatus


class EphemeralSandboxBackend(Protocol):
    def run(self, plan: SandboxPlan) -> Mapping[str, object]: ...


_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
_HASH64 = re.compile(r"^[0-9a-fA-F]{64}$")


class SandboxPlanner:
    ALLOWED_EXECUTABLES = frozenset({"python", "python3", "pytest", "npm", "node"})

    def prepare(self, request: SandboxRequest) -> SandboxPlan:
        if not request.request_id or not request.proposal_id or not request.source_url.startswith("https://github.com/") or not _SHA40.fullmatch(request.source_commit):
            raise SandboxPolicyError("pinned GitHub source required")
        forbidden = request.network_enabled or request.secrets_enabled or request.persistent_workspace or request.docker_socket or request.host_runner
        if forbidden:
            raise SandboxPolicyError("sandbox must be ephemeral, secretless, network-denied and off-host")
        if not request.commands:
            raise SandboxPolicyError("at least one bounded command required")
        for command in request.commands:
            if not command or command[0].lower() not in self.ALLOWED_EXECUTABLES or any(".." in part or part.startswith(("/", "\\")) for part in command):
                raise SandboxPolicyError("command outside allowlist")
        return SandboxPlan(request.request_id, request.proposal_id, f"{request.source_url}@{request.source_commit}", request.commands, request.limits, ("NETWORK=DENY", "SECRETS=NONE", "WORKSPACE=EPHEMERAL", "DOCKER_SOCKET=NONE", "HOST_RUNNER=NO"))


class SandboxController:
    def __init__(self, backend: EphemeralSandboxBackend) -> None:
        self.backend = backend

    def execute(self, plan: SandboxPlan, *, owner_execution_approved: bool) -> SandboxReceipt:
        if not owner_execution_approved:
            raise SandboxPolicyError("separate owner execution approval required")
        raw = self.backend.run(plan)
        receipt = SandboxReceipt(plan.request_id, str(raw.get("run_id", "")), int(raw.get("exit_code", -1)), bool(raw.get("timed_out", False)), bool(raw.get("network_observed", True)), bool(raw.get("secrets_mounted", True)), bool(raw.get("workspace_destroyed", False)), str(raw.get("stdout_sha256", "")), str(raw.get("stderr_sha256", "")), SandboxStatus.COMPLETED)
        if not receipt.backend_run_id or receipt.network_observed or receipt.secrets_mounted or not receipt.workspace_destroyed or not _HASH64.fullmatch(receipt.stdout_sha256) or not _HASH64.fullmatch(receipt.stderr_sha256):
            raise SandboxPolicyError("backend attestation failed closed")
        return receipt
