from ahos.department_proof_export import DepartmentProofExporter
from ahos.episode_delivery import DeliveryCheck, EpisodeDeliveryReport, PRODUCTION_LANGUAGES
from ahos.kurmanji_quality import KurmanjiQualityReport
from ahos.multilingual_audio_package import MultilingualAudioPackage
from ahos.voice_quality import VoiceQualityReport


def _delivery():
    return EpisodeDeliveryReport(
        episode_id="S01E001",
        checks=(DeliveryCheck("all", True, "ok"),),
        release_candidate_ready=True,
        evidence_hash="a" * 64,
    )


def _voice():
    return VoiceQualityReport(
        clips=(),
        expected_pairs=(),
        missing_pairs=(),
        ready=True,
        report_hash="b" * 64,
    )


def _audio():
    return MultilingualAudioPackage(
        episode_id="S01E001",
        required_languages=PRODUCTION_LANGUAGES,
        language_statuses=(),
        assets=(),
        shared_music_present=True,
        shared_sfx_present=True,
        package_hash="c" * 64,
    )


def _kurmanji():
    return KurmanjiQualityReport(
        language="ku-latn",
        register="child",
        regions=(),
        line_count=1,
        blocking_issues=(),
        advisory_issues=(),
        ready=True,
        report_hash="d" * 64,
    )


def test_department_proof_export_requires_human_acceptance():
    payloads = DepartmentProofExporter().export(
        delivery=_delivery(),
        voice_quality=_voice(),
        audio_package=_audio(),
        kurmanji_quality=_kurmanji(),
        human_identity_review_passed=False,
        human_language_review_passed=False,
    )
    assert payloads["studio_acceptance"]["accepted"] is True
    assert payloads["identity_acceptance"]["accepted"] is False
    assert payloads["language_acceptance"]["accepted"] is False


def test_department_proof_export_can_complete_all_three():
    payloads = DepartmentProofExporter().export(
        delivery=_delivery(),
        voice_quality=_voice(),
        audio_package=_audio(),
        kurmanji_quality=_kurmanji(),
        human_identity_review_passed=True,
        human_language_review_passed=True,
    )
    assert all(row["accepted"] is True for row in payloads.values())
