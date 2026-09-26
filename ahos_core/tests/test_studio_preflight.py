import json

from ahos.studio_preflight import build_execution_preflight


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_preflight_fails_closed_and_reports_real_blockers(tmp_path):
    write(tmp_path / "OWNER-APPROVAL.json", {"episode_id": "S01E003"})
    write(tmp_path / "artifacts/render-jobs.json", {"jobs": [{"duration_seconds": 10}]})
    write(tmp_path / "artifacts/localization-plan.json", {"units": [
        {"localized_text": "Merhaba"}, {"localized_text": ""}
    ]})
    write(tmp_path / "artifacts/voice-casting.json", {"characters": [
        {"character_id": "aden"}
    ]})
    result = build_execution_preflight(
        tmp_path, ltx2_hourly_usd=1.0, tts_hourly_usd=0.5,
        environment={"RUNPOD_API_KEY": "secret"},
    )
    assert result["approval_ready"] is False
    assert "ltx2_endpoint_present" in result["blockers"]
    assert "translations_complete" in result["blockers"]
    assert result["details"]["unsupported_tts_languages"] == ["ku-latn"]
    assert result["cost_estimate"]["recommended_budget_ceiling"] > 0
    assert result["external_calls_made"] is False


def test_preflight_can_be_ready_with_complete_supported_policy(monkeypatch, tmp_path):
    write(tmp_path / "OWNER-APPROVAL.json", {"episode_id": "S01E003"})
    write(tmp_path / "artifacts/render-jobs.json", {"jobs": [{"duration_seconds": 5}]})
    write(tmp_path / "artifacts/localization-plan.json", {"units": [{"localized_text": "Hello"}]})
    write(tmp_path / "artifacts/voice-casting.json", {"characters": [
        {"character_id": "aden", "reference_audio_uri": "voices/aden.wav"}
    ]})
    monkeypatch.setattr("ahos.studio_preflight.DEFAULT_LANGUAGE_POLICIES", ())
    result = build_execution_preflight(
        tmp_path, ltx2_hourly_usd=1, tts_hourly_usd=1,
        environment={
            "RUNPOD_API_KEY": "secret",
            "RUNPOD_LTX2_ENDPOINT_ID": "video",
            "RUNPOD_CHATTERBOX_ENDPOINT_ID": "voice",
        },
    )
    assert result["approval_ready"] is True
    assert result["blockers"] == []
