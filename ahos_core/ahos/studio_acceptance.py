from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .multilingual_audio_package import MultilingualAudioPackage
from .music_sfx_supervision import SoundSupervisionPackage
from .voice_readiness import VoiceReadinessReport


class AcceptancePreflightError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptanceGate:
    gate_id: str
    passed: bool
    blocking: bool
    message: str


@dataclass(frozen=True, slots=True)
class AcceptancePreflight:
    episode_id: str
    gates: tuple[AcceptanceGate, ...]
    ready_for_paid_execution: bool
    paid_execution_requested: bool
    publish_requested: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.studio-acceptance-preflight.v1",
            "episode_id": self.episode_id,
            "gates": [
                {
                    "gate_id": gate.gate_id,
                    "passed": gate.passed,
                    "blocking": gate.blocking,
                    "message": gate.message,
                }
                for gate in self.gates
            ],
            "ready_for_paid_execution": self.ready_for_paid_execution,
            "paid_execution_requested": self.paid_execution_requested,
            "publish_requested": self.publish_requested,
        }


class StudioAcceptancePreflight:
    REQUIRED_COMPLETED_STEPS = tuple(f"STUDIO-{n:03d}" for n in range(1, 8))

    def evaluate(
        self,
        *,
        episode_id: str,
        backlog: Mapping[str, object],
        required_artifacts: Sequence[str | Path],
        multilingual_audio_package: MultilingualAudioPackage | None,
        sound_supervision_package: SoundSupervisionPackage | None,
        voice_readiness_report: VoiceReadinessReport | None,
        voice_similarity_approved: bool,
        owner_approved: bool,
        execution_enabled: bool,
        paid_provider_enabled: bool,
        paid_execution_requested: bool = False,
        publish_requested: bool = False,
    ) -> AcceptancePreflight:
        if not episode_id.strip():
            raise AcceptancePreflightError("episode_id is required")
        tasks_raw = backlog.get("tasks")
        if not isinstance(tasks_raw, list):
            raise AcceptancePreflightError("studio backlog tasks must be a list")
        statuses = {
            str(task.get("id")): str(task.get("status"))
            for task in tasks_raw
            if isinstance(task, Mapping)
        }
        incomplete = [
            step for step in self.REQUIRED_COMPLETED_STEPS
            if statuses.get(step) != "completed"
        ]
        missing_artifacts = [str(path) for path in required_artifacts if not Path(path).is_file()]

        audio_package_present = multilingual_audio_package is not None
        audio_package_matches = (
            audio_package_present and multilingual_audio_package.episode_id == episode_id
        )
        audio_package_ready = audio_package_matches and multilingual_audio_package.ready
        if not audio_package_present:
            audio_package_message = "Multilingual audio package evidence is required."
        elif not audio_package_matches:
            audio_package_message = (
                "Multilingual audio package episode mismatch: "
                f"expected {episode_id}, got {multilingual_audio_package.episode_id}."
            )
        elif not audio_package_ready:
            incomplete_languages = [
                status.language
                for status in multilingual_audio_package.language_statuses
                if not status.ready
            ]
            missing_shared = []
            if not multilingual_audio_package.shared_music_present:
                missing_shared.append("music stem")
            if not multilingual_audio_package.shared_sfx_present:
                missing_shared.append("SFX stem")
            details = incomplete_languages + missing_shared
            audio_package_message = "Multilingual audio package is incomplete"
            if details:
                audio_package_message += ": " + ", ".join(details)
            audio_package_message += "."
        else:
            audio_package_message = (
                "Multilingual audio package is complete for: "
                + ", ".join(multilingual_audio_package.required_languages)
                + "."
            )

        sound_package_present = sound_supervision_package is not None
        sound_package_matches = (
            sound_package_present and sound_supervision_package.episode_id == episode_id
        )
        sound_package_ready = sound_package_matches and sound_supervision_package.ready
        if not sound_package_present:
            sound_package_message = "Music/SFX supervision evidence is required."
        elif not sound_package_matches:
            sound_package_message = (
                "Music/SFX supervision episode mismatch: "
                f"expected {episode_id}, got {sound_supervision_package.episode_id}."
            )
        elif not sound_package_ready:
            failed_checks = [name for name, passed in sound_supervision_package.qa.items() if not passed]
            sound_package_message = "Music/SFX supervision failed: " + ", ".join(failed_checks) + "."
        else:
            sound_package_message = "Music/SFX rights, safety, timing, and creative reviews passed."

        voice_report_ready = voice_readiness_report is not None and voice_readiness_report.ready
        if voice_readiness_report is None:
            voice_report_message = "Canonical core-cast voice readiness report is required."
        elif not voice_readiness_report.ready:
            preview = ", ".join(voice_readiness_report.missing[:8])
            remainder = len(voice_readiness_report.missing) - 8
            voice_report_message = "Missing canonical voices: " + preview
            if remainder > 0:
                voice_report_message += f" (+{remainder} more)"
            voice_report_message += "."
        else:
            voice_report_message = "Canonical core-cast voice coverage is complete."

        gates = (
            AcceptanceGate(
                "studio-roadmap",
                not incomplete,
                True,
                "STUDIO-001 through STUDIO-007 are complete."
                if not incomplete else "Incomplete prerequisites: " + ", ".join(incomplete),
            ),
            AcceptanceGate(
                "required-artifacts",
                not missing_artifacts,
                True,
                "All acceptance artifacts are present."
                if not missing_artifacts else "Missing artifacts: " + ", ".join(missing_artifacts),
            ),
            AcceptanceGate(
                "multilingual-audio-package",
                audio_package_ready,
                True,
                audio_package_message,
            ),
            AcceptanceGate(
                "music-sfx-supervision",
                sound_package_ready,
                True,
                sound_package_message,
            ),
            AcceptanceGate(
                "canonical-voice-readiness",
                voice_report_ready,
                True,
                voice_report_message,
            ),
            AcceptanceGate(
                "voice-similarity",
                voice_similarity_approved,
                True,
                "Human voice-similarity approval recorded."
                if voice_similarity_approved else "Human voice-similarity approval is required.",
            ),
            AcceptanceGate(
                "owner-approval",
                owner_approved,
                True,
                "Owner approval recorded." if owner_approved else "Explicit owner approval is required.",
            ),
            AcceptanceGate(
                "execution-enable",
                execution_enabled,
                True,
                "Execution is enabled." if execution_enabled else "Execution remains disabled.",
            ),
            AcceptanceGate(
                "paid-provider-enable",
                paid_provider_enabled,
                True,
                "Paid provider is enabled." if paid_provider_enabled else "Paid provider remains disabled.",
            ),
            AcceptanceGate(
                "no-publish",
                not publish_requested,
                True,
                "Publishing is not requested."
                if not publish_requested else "Acceptance production may not auto-publish.",
            ),
        )
        ready = paid_execution_requested and all(g.passed for g in gates if g.blocking)
        return AcceptancePreflight(
            episode_id=episode_id,
            gates=gates,
            ready_for_paid_execution=ready,
            paid_execution_requested=paid_execution_requested,
            publish_requested=publish_requested,
        )


def load_backlog(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AcceptancePreflightError("studio backlog must be an object")
    return payload


def export_preflight(preflight: AcceptancePreflight, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(preflight.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output
