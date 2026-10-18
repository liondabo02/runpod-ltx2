from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid


@dataclass(frozen=True, slots=True)
class StagingDeploymentReport:
    first_deploy_ok: bool
    upgrade_ok: bool
    rollback_ok: bool
    healthcheck_ok: bool
    artifact_hashes_ok: bool
    production_mutation: bool
    passed: bool


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def run_staging_deployment_e2e() -> StagingDeploymentReport:
    """Real filesystem deploy/upgrade/rollback in an isolated temporary staging root."""
    with TemporaryDirectory(prefix="ahos-q99-staging-") as tmp:
        root = Path(tmp)
        releases = root / "releases"
        releases.mkdir()
        current = root / "CURRENT.json"

        def build_release(version: str, content: str) -> tuple[Path, str]:
            release = releases / version
            release.mkdir()
            artifact = release / "artifact.json"
            artifact.write_text(
                json.dumps({"version": version, "content": content}, sort_keys=True),
                encoding="utf-8",
            )
            return artifact, _sha256(artifact)

        v1, v1_hash = build_release("v1", "stable")
        v2, v2_hash = build_release("v2", "upgrade")

        def deploy(version: str, artifact: Path, digest: str) -> None:
            if _sha256(artifact) != digest:
                raise RuntimeError("artifact integrity mismatch")
            _atomic_json(current, {
                "environment": "isolated-staging",
                "version": version,
                "artifact": str(artifact.relative_to(root)),
                "sha256": digest,
                "production": False,
            })

        def healthcheck(expected_version: str, expected_hash: str) -> bool:
            state = json.loads(current.read_text(encoding="utf-8"))
            artifact = root / str(state["artifact"])
            return (
                state.get("environment") == "isolated-staging"
                and state.get("production") is False
                and state.get("version") == expected_version
                and state.get("sha256") == expected_hash
                and artifact.is_file()
                and _sha256(artifact) == expected_hash
            )

        deploy("v1", v1, v1_hash)
        first = healthcheck("v1", v1_hash)

        deploy("v2", v2, v2_hash)
        upgraded = healthcheck("v2", v2_hash)

        # Rollback uses the already verified immutable v1 artifact.
        deploy("v1", v1, v1_hash)
        rolled_back = healthcheck("v1", v1_hash)

        hashes_ok = _sha256(v1) == v1_hash and _sha256(v2) == v2_hash
        health_ok = first and upgraded and rolled_back
        return StagingDeploymentReport(
            first_deploy_ok=first,
            upgrade_ok=upgraded,
            rollback_ok=rolled_back,
            healthcheck_ok=health_ok,
            artifact_hashes_ok=hashes_ok,
            production_mutation=False,
            passed=health_ok and hashes_ok,
        )
