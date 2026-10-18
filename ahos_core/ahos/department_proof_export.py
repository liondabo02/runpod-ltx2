from __future__ import annotations

import hashlib
import json

from .episode_delivery import EpisodeDeliveryReport, PRODUCTION_LANGUAGES
from .kurmanji_quality import KurmanjiQualityReport
from .multilingual_audio_package import MultilingualAudioPackage
from .voice_quality import VoiceQualityReport


def _digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class DepartmentProofExporter:
    """Translate existing studio QA into final proof payloads.

    Human acceptance remains explicit input; this exporter cannot self-approve
    character identity or native-language listening quality.
    """

    def export(
        self,
        *,
        delivery: EpisodeDeliveryReport,
        voice_quality: VoiceQualityReport,
        audio_package: MultilingualAudioPackage,
        kurmanji_quality: KurmanjiQualityReport,
        human_identity_review_passed: bool,
        human_language_review_passed: bool,
    ) -> dict[str, dict[str, object]]:
        studio_ok = bool(delivery.release_candidate_ready)
        identity_ok = bool(
            voice_quality.ready
            and not voice_quality.missing_pairs
            and human_identity_review_passed
        )
        language_ok = bool(
            audio_package.ready
            and tuple(audio_package.required_languages) == PRODUCTION_LANGUAGES
            and kurmanji_quality.ready
            and human_language_review_passed
        )

        studio_hash = delivery.evidence_hash if len(delivery.evidence_hash) == 64 else _digest(delivery.to_payload())
        identity_hash = voice_quality.report_hash if len(voice_quality.report_hash) == 64 else _digest({
            "ready": voice_quality.ready,
            "pairs": voice_quality.expected_pairs,
            "missing": voice_quality.missing_pairs,
        })
        language_hash = _digest({
            "audio_package_hash": audio_package.package_hash,
            "kurmanji_report_hash": kurmanji_quality.report_hash,
            "languages": audio_package.required_languages,
        })

        return {
            "studio_acceptance": {
                "kind": "studio",
                "accepted": studio_ok,
                "evidence_hash": studio_hash,
                "human_review_required": False,
            },
            "identity_acceptance": {
                "kind": "identity",
                "accepted": identity_ok,
                "evidence_hash": identity_hash,
                "human_review_required": True,
                "human_review_passed": bool(human_identity_review_passed),
            },
            "language_acceptance": {
                "kind": "languages",
                "accepted": language_ok,
                "evidence_hash": language_hash,
                "human_review_required": True,
                "human_review_passed": bool(human_language_review_passed),
            },
        }
