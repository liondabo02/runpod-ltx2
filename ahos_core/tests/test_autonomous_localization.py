import json

import pytest

from ahos.autonomous_localization import (
    AutonomousLocalizationPipeline,
    LocalizationPolicy,
    LocalizationQualityRejected,
)


LANGUAGES = ("tr", "ku-latn", "de", "ar", "fr", "es", "en")


def units():
    return [
        {
            "unit_id": f"S01E001:SC01:L001:{language}",
            "scene_id": "SC01",
            "line_id": "L001",
            "speaker_character_id": "aden",
            "source_language": "tr",
            "target_language": language,
            "source_text": "Aden kırmızı uçurtmayı buldu.",
            "localized_text": "Aden kırmızı uçurtmayı buldu." if language == "tr" else "",
        }
        for language in LANGUAGES
    ]


def valid_response(prompt_text):
    prompt = json.loads(prompt_text)
    words = {
        "tr": "Aden kırmızı uçurtmayı buldu.",
        "ku-latn": "Aden pepûka sor dît.",
        "de": "Aden fand den roten Drachen.",
        "ar": "وجد Aden الطائرة الورقية الحمراء.",
        "fr": "Aden a trouvé le cerf-volant rouge.",
        "es": "Aden encontró la cometa roja.",
        "en": "Aden found the red kite.",
    }
    return json.dumps({
        "translations": [
            {"unit_id": unit["unit_id"], "localized_text": words[unit["target_language"]]}
            for unit in prompt["units"]
        ]
    }, ensure_ascii=False)


def test_pipeline_produces_complete_schema_valid_seven_language_package():
    result = AutonomousLocalizationPipeline(generator=valid_response).localize(
        units(),
        languages=LANGUAGES,
        character_name_locks={"aden": "Aden"},
    )

    assert result["status"] == "machine_qa_approved"
    assert result["fail_closed"] is True
    assert result["qa_rounds"] == 1
    assert len(result["units"]) == 7
    assert {item["target_language"] for item in result["units"]} == set(LANGUAGES)
    assert all(item["status"] == "machine_qa_approved" for item in result["units"])


def test_pipeline_retries_malformed_schema_without_external_calls():
    calls = []

    def generator(prompt):
        calls.append(json.loads(prompt))
        return "not-json" if len(calls) == 1 else valid_response(prompt)

    result = AutonomousLocalizationPipeline(generator=generator).localize(
        units(), languages=LANGUAGES, character_name_locks={"aden": "Aden"}
    )

    assert result["qa_rounds"] == 2
    assert calls[1]["quality_failures"][0]["code"] == "schema.invalid"


def test_locked_terminology_and_character_names_drive_revision():
    calls = []

    def generator(prompt):
        parsed = json.loads(prompt)
        calls.append(parsed)
        response = json.loads(valid_response(prompt))
        de = next(row for row in response["translations"] if row["unit_id"].endswith(":de"))
        if len(calls) == 1:
            de["localized_text"] = "Sie fand das rote Spielzeug."
        else:
            de["localized_text"] = "Aden fand den roten Flugdrachen."
        return json.dumps(response, ensure_ascii=False)

    result = AutonomousLocalizationPipeline(generator=generator).localize(
        units(),
        languages=LANGUAGES,
        character_name_locks={"aden": "Aden"},
        terminology_locks={"de": {"uçurtma": "Flugdrachen"}},
    )

    assert result["qa_rounds"] == 2
    codes = {item["code"] for item in calls[1]["quality_failures"]}
    assert codes == {"name.lock", "terminology.lock"}


def test_pipeline_fails_closed_after_bounded_revision_budget():
    def bad_response(prompt):
        parsed = json.loads(prompt)
        return json.dumps({
            "translations": [
                {"unit_id": item["unit_id"], "localized_text": "TODO"}
                for item in parsed["units"]
            ]
        })

    pipeline = AutonomousLocalizationPipeline(
        generator=bad_response, policy=LocalizationPolicy(maximum_rounds=2)
    )
    with pytest.raises(LocalizationQualityRejected, match="failed closed after 2 rounds"):
        pipeline.localize(
            units(), languages=LANGUAGES, character_name_locks={"aden": "Aden"}
        )


def test_pipeline_rejects_partial_language_configuration():
    with pytest.raises(ValueError, match="exactly seven"):
        AutonomousLocalizationPipeline(generator=valid_response).localize(
            units(), languages=("tr", "en"), character_name_locks={"aden": "Aden"}
        )


def test_pipeline_rejects_source_text_copied_into_foreign_languages():
    def copied_source(prompt):
        parsed = json.loads(prompt)
        return json.dumps({
            "translations": [
                {"unit_id": item["unit_id"], "localized_text": item["source_text"]}
                for item in parsed["units"]
            ]
        }, ensure_ascii=False)

    with pytest.raises(LocalizationQualityRejected, match="translation.unchanged"):
        AutonomousLocalizationPipeline(
            generator=copied_source,
            policy=LocalizationPolicy(maximum_rounds=1),
        ).localize(units(), languages=LANGUAGES, character_name_locks={"aden": "Aden"})
