from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
from typing import Iterable

from .episode_delivery import PRODUCTION_LANGUAGES


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    path: str
    sha256: str
    size_bytes: int
    kind: str
    language: str | None = None


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema: str
    episode_id: str
    commit_sha: str
    languages: tuple[str, ...]
    assets: tuple[ReleaseAsset, ...]
    delivery_evidence_hash: str
    execution_ledger_hash: str
    owner_release_hash: str
    manifest_sha256: str
    signature_algorithm: str | None
    signature: str | None


def _valid_sha(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _canonical_payload(
    *,
    episode_id: str,
    commit_sha: str,
    assets: tuple[ReleaseAsset, ...],
    delivery_evidence_hash: str,
    execution_ledger_hash: str,
    owner_release_hash: str,
) -> dict[str, object]:
    return {
        "schema": "ahos.release-manifest.v1",
        "episode_id": episode_id,
        "commit_sha": commit_sha,
        "languages": list(PRODUCTION_LANGUAGES),
        "assets": [
            asdict(asset)
            for asset in sorted(assets, key=lambda item: (item.kind, item.language or "", item.path))
        ],
        "delivery_evidence_hash": delivery_evidence_hash,
        "execution_ledger_hash": execution_ledger_hash,
        "owner_release_hash": owner_release_hash,
    }


class ReleaseManifestBuilder:
    def build(
        self,
        *,
        episode_id: str,
        commit_sha: str,
        assets: Iterable[ReleaseAsset],
        delivery_evidence_hash: str,
        execution_ledger_hash: str,
        owner_release_hash: str,
        signing_key: bytes | None = None,
    ) -> ReleaseManifest:
        episode = episode_id.strip()
        commit = commit_sha.strip()
        rows = tuple(assets)
        if not episode or not commit:
            raise ValueError("episode_id and commit_sha are required")
        if not rows:
            raise ValueError("release assets are required")
        if len({row.path for row in rows}) != len(rows):
            raise ValueError("release asset paths must be unique")
        for row in rows:
            if not row.path.strip() or not row.kind.strip() or row.size_bytes <= 0:
                raise ValueError("invalid release asset")
            if not _valid_sha(row.sha256):
                raise ValueError("invalid asset sha256")
            if row.language is not None and row.language not in PRODUCTION_LANGUAGES:
                raise ValueError("unsupported release language")
        for digest in (delivery_evidence_hash, execution_ledger_hash, owner_release_hash):
            if not _valid_sha(digest):
                raise ValueError("release evidence hashes must be sha256")

        payload = _canonical_payload(
            episode_id=episode,
            commit_sha=commit,
            assets=rows,
            delivery_evidence_hash=delivery_evidence_hash,
            execution_ledger_hash=execution_ledger_hash,
            owner_release_hash=owner_release_hash,
        )
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest_hash = hashlib.sha256(raw).hexdigest()
        signature = None
        algorithm = None
        if signing_key is not None:
            if len(signing_key) < 32:
                raise ValueError("signing key must contain at least 32 bytes")
            signature = hmac.new(signing_key, raw, hashlib.sha256).hexdigest()
            algorithm = "HMAC-SHA256"

        return ReleaseManifest(
            schema=str(payload["schema"]),
            episode_id=episode,
            commit_sha=commit,
            languages=PRODUCTION_LANGUAGES,
            assets=tuple(sorted(rows, key=lambda item: (item.kind, item.language or "", item.path))),
            delivery_evidence_hash=delivery_evidence_hash,
            execution_ledger_hash=execution_ledger_hash,
            owner_release_hash=owner_release_hash,
            manifest_sha256=manifest_hash,
            signature_algorithm=algorithm,
            signature=signature,
        )

    def verify_signature(self, manifest: ReleaseManifest, *, signing_key: bytes) -> bool:
        rebuilt = self.build(
            episode_id=manifest.episode_id,
            commit_sha=manifest.commit_sha,
            assets=manifest.assets,
            delivery_evidence_hash=manifest.delivery_evidence_hash,
            execution_ledger_hash=manifest.execution_ledger_hash,
            owner_release_hash=manifest.owner_release_hash,
            signing_key=signing_key,
        )
        return (
            rebuilt.manifest_sha256 == manifest.manifest_sha256
            and rebuilt.signature == manifest.signature
            and manifest.signature_algorithm == "HMAC-SHA256"
        )
