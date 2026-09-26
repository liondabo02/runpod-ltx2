from pathlib import Path

import pytest

from ahos.voice_candidate_lab import VoiceCandidateLab, VoiceCandidateLabError


def plan(path: Path) -> Path:
    path.write_text('''{
      "characters": [
        {"id":"aden","name":"Aden","age_years":3,"gender":"girl","speech_mode":"speech","seed":1703,"direction":"preschool child","en_text":"Hello!","tr_text":"Merhaba!"},
        {"id":"ramin","name":"Ramin","age_years":0.08,"gender":"boy","speech_mode":"infant_vocalization","seed":null,"direction":"coos","en_text":null,"tr_text":null}
      ]
    }''', encoding="utf-8")
    return path


def test_prepare_plans_candidates_but_never_sentence_tts_for_infant(tmp_path):
    manifest = VoiceCandidateLab(tmp_path / "lab").prepare(plan(tmp_path / "plan.json"))
    aden, ramin = manifest["characters"]
    assert [item["candidate_id"] for item in aden["candidates"]] == ["aden-A", "aden-B", "aden-C"]
    assert ramin["status"] == "vocalization_library_required"
    assert ramin["candidates"] == []


class FakeProvider:
    def design(self, **kwargs):
        return b"RIFF" + b"0" * 4 + b"WAVE" + kwargs["candidate_id"].encode() + b"0" * 40


def test_generate_then_owner_approve_is_hash_locked(tmp_path):
    lab = VoiceCandidateLab(tmp_path / "lab")
    lab.prepare(plan(tmp_path / "plan.json"), candidates_per_character=2)
    generated = lab.generate("aden", FakeProvider())
    assert generated["status"] == "awaiting_owner_approval"
    record = lab.approve("aden", "aden-B")
    assert record["owner_approved"] is True
    assert record["reference_origin"] == "synthetic"
    assert record["canonical_binding_created"] is False
    with pytest.raises(VoiceCandidateLabError, match="already has"):
        lab.approve("aden", "aden-A")


def test_infant_generation_is_rejected(tmp_path):
    lab = VoiceCandidateLab(tmp_path / "lab")
    lab.prepare(plan(tmp_path / "plan.json"))
    with pytest.raises(VoiceCandidateLabError, match="vocalization library"):
        lab.generate("ramin", FakeProvider())
