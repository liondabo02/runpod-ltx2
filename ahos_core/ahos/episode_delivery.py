from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from .kurmanji_quality import KURMANJI_LANGUAGE, REGIONAL_COVERAGE, KurmanjiQualityReport
from .multilingual_audio_package import MultilingualAudioPackage
from .studio_acceptance import AcceptancePreflight
from .voice_quality import VoiceQualityReport


PRODUCTION_LANGUAGES = ("tr", "ku-latn", "de", "ar", "fr", "es", "en")


class EpisodeDeliveryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DeliveryCheck:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class EpisodeDeliveryReport:
    episode_id: str
    checks: tuple[DeliveryCheck, ...]
    release_candidate_ready: bool
    evidence_hash: str

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "ahos.episode-delivery-evidence.v1",
            "episode_id": self.episode_id,
            "checks": [
                {"check_id": item.check_id, "passed": item.passed, "detail": item.detail}
                for item in self.checks
            ],
            "release_candidate_ready": self.release_candidate_ready,
            "evidence_hash": self.evidence_hash,
        }


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and value == value.lower() and all(c in "0123456789abcdef" for c in value)


class EpisodeDeliveryGate:
    """Cross-artifact, fail-closed gate for a seven-language episode master.

    The gate does not render media or publish it. It proves that independently
    generated acceptance, package, localization, and rendered-voice evidence all
    describe the same professional release candidate.
    """

    def evaluate(
        self,
        *,
        episode_id: str,
        speaking_character_ids: Iterable[str],
        audio_package: MultilingualAudioPackage,
        voice_quality_report: VoiceQualityReport,
        kurmanji_quality_report: KurmanjiQualityReport,
        acceptance_preflight: AcceptancePreflight,
        picture_master_sha256: str,
    ) -> EpisodeDeliveryReport:
        episode = episode_id.strip()
        speakers = tuple(sorted({speaker.strip() for speaker in speaking_character_ids if speaker.strip()}))
        if not episode:
            raise EpisodeDeliveryError("episode_id is required")
        if not speakers:
            raise EpisodeDeliveryError("at least one speaking character is required")

        languages = tuple(audio_package.required_languages)
        expected_pairs = tuple(sorted(f"{speaker}:{language}" for speaker in speakers for language in languages))
        declared_pairs = tuple(sorted(voice_quality_report.expected_pairs))
        clip_pairs = tuple(sorted({
            f"{clip.character_id}:{clip.language}"
            for clip in voice_quality_report.clips
            if clip.ready and clip.metrics is not None and _valid_sha256(clip.metrics.sha256)
        }))
        asset_hashes_valid = all(_valid_sha256(asset.sha256) for asset in audio_package.assets)
        asset_ids_unique = len({asset.asset_id for asset in audio_package.assets}) == len(audio_package.assets)
        package_languages_exact = languages == PRODUCTION_LANGUAGES
        status_languages_exact = tuple(status.language for status in audio_package.language_statuses) == languages
        preflight_passed = (
            acceptance_preflight.ready_for_paid_execution
            and not acceptance_preflight.publish_requested
            and all(gate.passed for gate in acceptance_preflight.gates if gate.blocking)
        )
        kurmanji_professional = (
            kurmanji_quality_report.language == KURMANJI_LANGUAGE
            and kurmanji_quality_report.ready
            and kurmanji_quality_report.line_count > 0
            and tuple(kurmanji_quality_report.regions) == tuple(REGIONAL_COVERAGE)
        )

        checks = (
            DeliveryCheck(
                "episode-identity",
                audio_package.episode_id == episode and acceptance_preflight.episode_id == episode,
                "Audio package and acceptance evidence reference the requested episode.",
            ),
            DeliveryCheck(
                "canonical-seven-languages",
                package_languages_exact and status_languages_exact,
                "Required ordered language set is tr, ku-latn, de, ar, fr, es, en.",
            ),
            DeliveryCheck(
                "multilingual-package-ready",
                audio_package.ready and asset_ids_unique and asset_hashes_valid,
                "Every language mix/subtitle and shared music/SFX asset is complete and content-addressed.",
            ),
            DeliveryCheck(
                "rendered-voice-coverage",
                voice_quality_report.ready
                and not voice_quality_report.missing_pairs
                and declared_pairs == expected_pairs
                and clip_pairs == expected_pairs,
                "Rendered-voice QA covers every speaking character in every required language.",
            ),
            DeliveryCheck(
                "professional-kurmanji",
                kurmanji_professional,
                "Kurmanji passed native editorial QA for the configured Southeast regional coverage.",
            ),
            DeliveryCheck(
                "acceptance-chain",
                preflight_passed,
                "Protected acceptance gates passed and automatic publishing remains disabled.",
            ),
            DeliveryCheck(
                "picture-master-integrity",
                _valid_sha256(picture_master_sha256),
                "Picture master is identified by a canonical lowercase SHA-256 digest.",
            ),
        )
        material = {
            "episode_id": episode,
            "speakers": speakers,
            "languages": languages,
            "audio_package_hash": audio_package.package_hash,
            "voice_quality_hash": voice_quality_report.report_hash,
            "kurmanji_quality_hash": kurmanji_quality_report.report_hash,
            "picture_master_sha256": picture_master_sha256,
            "checks": [(item.check_id, item.passed) for item in checks],
        }
        evidence_hash = hashlib.sha256(
            json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return EpisodeDeliveryReport(
            episode_id=episode,
            checks=checks,
            release_candidate_ready=all(item.passed for item in checks),
            evidence_hash=evidence_hash,
        )
