from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence


class MusicSfxSupervisionError(ValueError):
    pass


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SoundAssetEvidence:
    asset_id: str
    kind: str
    uri: str
    sha256: str
    source_uri: str
    license_id: str
    rights_holder: str
    commercial_rights_confirmed: bool
    attribution_text: str | None = None
    generated_with_ai: bool = False
    generator_id: str | None = None


@dataclass(frozen=True, slots=True)
class SoundCue:
    cue_id: str
    scene_id: str
    asset_id: str
    kind: str
    start_seconds: float
    end_seconds: float
    purpose: str
    dialogue_ducking_db: float
    child_safe_reviewed: bool
    creative_reviewed: bool


@dataclass(frozen=True, slots=True)
class SoundSupervisionPackage:
    episode_id: str
    episode_duration_seconds: float
    assets: tuple[SoundAssetEvidence, ...]
    cues: tuple[SoundCue, ...]
    qa: Mapping[str, bool]
    package_hash: str

    @property
    def ready(self) -> bool:
        return all(self.qa.values())


class MusicSfxSupervisor:
    """Builds a deterministic, rights-aware sound plan without generating media."""

    VALID_KINDS = frozenset({"music", "sfx", "ambience"})

    def build(
        self,
        *,
        episode_id: str,
        episode_duration_seconds: float,
        assets: Sequence[SoundAssetEvidence],
        cues: Sequence[SoundCue],
    ) -> SoundSupervisionPackage:
        if not episode_id.strip() or episode_duration_seconds <= 0:
            raise MusicSfxSupervisionError("valid episode id and duration are required")
        if not assets or not cues:
            raise MusicSfxSupervisionError("at least one sound asset and cue are required")

        by_id = {asset.asset_id: asset for asset in assets}
        if len(by_id) != len(assets):
            raise MusicSfxSupervisionError("sound asset ids must be unique")
        if len({cue.cue_id for cue in cues}) != len(cues):
            raise MusicSfxSupervisionError("sound cue ids must be unique")

        for asset in assets:
            if asset.kind not in self.VALID_KINDS:
                raise MusicSfxSupervisionError(f"unsupported sound asset kind: {asset.kind}")
            if len(asset.sha256) != 64 or any(c not in "0123456789abcdef" for c in asset.sha256.lower()):
                raise MusicSfxSupervisionError(f"invalid SHA-256 for {asset.asset_id}")
            if not all((asset.uri.strip(), asset.source_uri.strip(), asset.license_id.strip(), asset.rights_holder.strip())):
                raise MusicSfxSupervisionError(f"incomplete provenance for {asset.asset_id}")
            if asset.generated_with_ai and not (asset.generator_id or "").strip():
                raise MusicSfxSupervisionError(f"AI generator identity required for {asset.asset_id}")

        ordered = tuple(sorted(cues, key=lambda cue: (cue.start_seconds, cue.cue_id)))
        timeline_valid = True
        references_valid = True
        purposes_present = True
        kinds_match = True
        ducking_safe = True
        for cue in ordered:
            asset = by_id.get(cue.asset_id)
            references_valid &= asset is not None
            kinds_match &= asset is not None and asset.kind == cue.kind
            purposes_present &= bool(cue.scene_id.strip() and cue.purpose.strip())
            timeline_valid &= (
                cue.kind in self.VALID_KINDS
                and cue.start_seconds >= 0
                and cue.end_seconds > cue.start_seconds
                and cue.end_seconds <= episode_duration_seconds
            )
            ducking_safe &= -18.0 <= cue.dialogue_ducking_db <= 0.0

        music = [cue for cue in ordered if cue.kind == "music"]
        music_non_overlapping = all(
            current.start_seconds >= previous.end_seconds
            for previous, current in zip(music, music[1:])
        )
        qa = {
            "timeline_valid": timeline_valid,
            "asset_references_valid": references_valid,
            "asset_kinds_match": kinds_match,
            "cue_purposes_present": purposes_present,
            "music_non_overlapping": music_non_overlapping,
            "dialogue_ducking_safe": ducking_safe,
            "commercial_rights_confirmed": all(a.commercial_rights_confirmed for a in assets),
            "child_safety_reviewed": all(c.child_safe_reviewed for c in cues),
            "creative_reviewed": all(c.creative_reviewed for c in cues),
            "music_present": any(c.kind == "music" for c in cues),
            "sfx_present": any(c.kind == "sfx" for c in cues),
        }
        semantic = {
            "episode_id": episode_id,
            "duration": episode_duration_seconds,
            "assets": [
                {
                    "id": a.asset_id, "kind": a.kind, "uri": a.uri, "sha256": a.sha256,
                    "source": a.source_uri, "license": a.license_id,
                    "rights_holder": a.rights_holder, "commercial": a.commercial_rights_confirmed,
                    "attribution": a.attribution_text, "ai": a.generated_with_ai,
                    "generator": a.generator_id,
                }
                for a in sorted(assets, key=lambda item: item.asset_id)
            ],
            "cues": [
                {
                    "id": c.cue_id, "scene": c.scene_id, "asset": c.asset_id, "kind": c.kind,
                    "start": c.start_seconds, "end": c.end_seconds, "purpose": c.purpose,
                    "ducking": c.dialogue_ducking_db, "child_safe": c.child_safe_reviewed,
                    "creative_review": c.creative_reviewed,
                }
                for c in ordered
            ],
            "qa": qa,
        }
        return SoundSupervisionPackage(
            episode_id=episode_id,
            episode_duration_seconds=episode_duration_seconds,
            assets=tuple(sorted(assets, key=lambda item: item.asset_id)),
            cues=ordered,
            qa=qa,
            package_hash=_digest(semantic),
        )
