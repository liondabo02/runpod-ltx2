from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


class AssemblyValidationError(RuntimeError):
    pass


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    asset_id: str
    kind: str
    path: str
    duration_seconds: float | None = None
    language: str | None = None
    content_hash: str | None = None


@dataclass(frozen=True, slots=True)
class QAResult:
    check_id: str
    category: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class EpisodeReleasePackage:
    episode_id: str
    target_duration_seconds: int
    assets: tuple[ReleaseAsset, ...]
    assembly_steps: tuple[dict[str, object], ...]
    qa_results: tuple[QAResult, ...]
    release_ready: bool
    package_hash: str

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.episode-release-package.v1",
            "episode_id": self.episode_id,
            "target_duration_seconds": self.target_duration_seconds,
            "assets": [
                {
                    "asset_id": a.asset_id,
                    "kind": a.kind,
                    "path": a.path,
                    "duration_seconds": a.duration_seconds,
                    "language": a.language,
                    "content_hash": a.content_hash,
                }
                for a in self.assets
            ],
            "assembly_steps": list(self.assembly_steps),
            "qa_results": [
                {
                    "check_id": q.check_id,
                    "category": q.category,
                    "passed": q.passed,
                    "message": q.message,
                }
                for q in self.qa_results
            ],
            "release_ready": self.release_ready,
            "package_hash": self.package_hash,
        }


class EpisodeAssemblyPlanner:
    """Builds a deterministic, non-executing assembly and release QA plan."""

    REQUIRED_QA_CATEGORIES = frozenset(
        {"continuity", "child_safety", "picture", "audio", "subtitles", "technical"}
    )

    def build(
        self,
        *,
        graph: Mapping[str, object],
        assets: Sequence[ReleaseAsset],
        child_safe_approved: bool,
        continuity_approved: bool,
    ) -> EpisodeReleasePackage:
        episode_id = str(graph.get("episode_id") or "").strip()
        if not episode_id:
            raise AssemblyValidationError("production graph is missing episode_id")
        target = int(graph.get("target_duration_seconds") or 0)
        shots = graph.get("shots")
        if target <= 0 or not isinstance(shots, list) or not shots:
            raise AssemblyValidationError("production graph has no valid timeline")

        by_id = {a.asset_id: a for a in assets}
        if len(by_id) != len(assets):
            raise AssemblyValidationError("release assets contain duplicate ids")

        required_video_ids = [str(s.get("output_asset_id")) for s in shots if isinstance(s, Mapping)]
        missing_video = [asset_id for asset_id in required_video_ids if asset_id not in by_id]
        audio = [a for a in assets if a.kind == "final_mix"]
        subtitles = [a for a in assets if a.kind == "subtitle"]
        video_duration = sum(
            float(by_id[x].duration_seconds or 0) for x in required_video_ids if x in by_id
        )

        qa = (
            QAResult("continuity", "continuity", continuity_approved, "Continuity approval recorded." if continuity_approved else "Continuity approval missing."),
            QAResult("child-safety", "child_safety", child_safe_approved, "Child-safety approval recorded." if child_safe_approved else "Child-safety approval missing."),
            QAResult("picture-assets", "picture", not missing_video, "All shot outputs present." if not missing_video else "Missing shot outputs: " + ", ".join(missing_video)),
            QAResult("picture-duration", "technical", abs(video_duration - target) <= 0.5, f"Picture duration {video_duration:.3f}s; target {target}s."),
            QAResult("final-mix", "audio", bool(audio), "Final mix present." if audio else "Final mix missing."),
            QAResult("subtitle-package", "subtitles", bool(subtitles), "Subtitle package present." if subtitles else "Subtitle package missing."),
            QAResult("asset-hashes", "technical", all(bool(a.content_hash) for a in assets), "Every release asset has provenance hash." if all(bool(a.content_hash) for a in assets) else "One or more release assets lack provenance hash."),
        )

        steps: list[dict[str, object]] = []
        for index, asset_id in enumerate(required_video_ids, start=1):
            steps.append({"ordinal": index, "operation": "append_video", "asset_id": asset_id})
        for item in sorted(audio, key=lambda a: (a.language or "", a.asset_id)):
            steps.append({"operation": "mux_audio", "asset_id": item.asset_id, "language": item.language})
        for item in sorted(subtitles, key=lambda a: (a.language or "", a.asset_id)):
            steps.append({"operation": "attach_subtitle", "asset_id": item.asset_id, "language": item.language})

        semantic = {
            "episode_id": episode_id,
            "target_duration_seconds": target,
            "assets": [a.__dict__ if hasattr(a, "__dict__") else {
                "asset_id": a.asset_id, "kind": a.kind, "path": a.path,
                "duration_seconds": a.duration_seconds, "language": a.language,
                "content_hash": a.content_hash,
            } for a in assets],
            "assembly_steps": steps,
            "qa": [(q.check_id, q.passed, q.message) for q in qa],
        }
        return EpisodeReleasePackage(
            episode_id=episode_id,
            target_duration_seconds=target,
            assets=tuple(assets),
            assembly_steps=tuple(steps),
            qa_results=qa,
            release_ready=all(q.passed for q in qa),
            package_hash=_sha256(semantic),
        )


def export_release_package(package: EpisodeReleasePackage, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output
