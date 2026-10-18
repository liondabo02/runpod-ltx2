from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class StudioRehearsalEvidenceReport:
    valid: bool
    release_ready: bool
    blockers: tuple[str, ...]


class StudioRehearsalEvidenceValidator:
    def evaluate(self, payload: Mapping[str, object]) -> StudioRehearsalEvidenceReport:
        blockers: list[str] = []
        required = {
            "episode_id", "status", "release_ready", "story_hash",
            "production_graph_hash", "counts", "checks", "blockers",
            "evidence_hash", "external_calls_made"
        }
        missing = sorted(required - set(payload))
        blockers.extend(f"missing:{name}" for name in missing)

        counts = payload.get("counts")
        if not isinstance(counts, Mapping):
            blockers.append("counts_invalid")
        else:
            expected = {
                "canonical_characters": 16,
                "scenes": 5,
                "shots": 10,
                "render_jobs": 10,
                "dialogue_lines": 43,
                "localization_units": 301,
                "languages": 7,
            }
            for key, value in expected.items():
                if int(counts.get(key) or -1) != value:
                    blockers.append(f"count_mismatch:{key}")

        for digest_field in ("story_hash", "production_graph_hash", "evidence_hash"):
            digest = str(payload.get(digest_field) or "")
            if len(digest) != 64:
                blockers.append(f"invalid_hash:{digest_field}")

        if payload.get("external_calls_made") is not False:
            blockers.append("external_call_detected")
        if payload.get("release_ready") is True:
            blockers.append("unexpected_release_ready")

        episode_blockers = payload.get("blockers")
        if not isinstance(episode_blockers, Sequence) or isinstance(episode_blockers, (str, bytes)):
            blockers.append("episode_blockers_invalid")

        return StudioRehearsalEvidenceReport(
            valid=not blockers,
            release_ready=payload.get("release_ready") is True,
            blockers=tuple(sorted(set(blockers))),
        )
