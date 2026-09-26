import json

import pytest
import urllib.error

from ahos.autonomous_story_room import (
    AutonomousWritersRoom,
    DeterministicStoryQualityGate,
    StoryQualityRejected,
    StoryRoomMemory,
    StoryRoomPolicy,
    OpenAICompatibleStoryGenerator,
)
from ahos.story_engine import EpisodeRequest, StoryCharacterContext, StoryContext, _packet_from_mapping


def request():
    return EpisodeRequest(1, 2, "Renkli uçurtma", "yardımlaşma", ("aden", "kaan"), age_band="2-5", target_duration_seconds=480)


def context():
    return StoryContext(
        "S01E002",
        (
            StoryCharacterContext("aden", "Aden", "lead", "3-year-old child", (), (), ("kaan",)),
            StoryCharacterContext("kaan", "Kaan", "younger brother", "1-year-old infant", (), (), ("aden",)),
        ), (), (),
    )


def payload(*, infant_text="Bak!", suffix=""):
    durations = [90, 95, 100, 105, 90]
    scenes = []
    for index, duration in enumerate(durations, 1):
        scenes.append({
            "scene_id": f"SCENE-{index:02d}", "title": f"Sahne {index}{suffix}",
            "setting": "park", "cast_ids": ["aden", "kaan"],
            "duration_seconds": duration, "objective": "birlikte çözmek",
            "action_summary": f"Aden ve Kaan görsel bir sorunu adım {index} ile çözer{suffix}.",
            "dialogue": [
                {"speaker_character_id": "aden", "text": f"Kaan, şuna bak {index}!", "intent": "merak"},
                {"speaker_character_id": "kaan", "text": f"{infant_text} {index}", "intent": "tepki"},
                {"speaker_character_id": "aden", "text": f"Ben bunu tutayım {index}.", "intent": "eylem"},
                {"speaker_character_id": "kaan", "text": f"Hop {index}!", "intent": "oyun"},
                {"speaker_character_id": "aden", "text": f"Oldu, devam {index}!", "intent": "ilerleme"},
                {"speaker_character_id": "kaan", "text": f"Yaşasın {index}!", "intent": "sevinç"},
            ],
        })
    return {
        "title": f"Uçurtma Dostları{suffix}", "logline": "İki kardeş uçurtmayı birlikte kurtarır.",
        "continuity_notes": [],
        "beats": [{"beat_id": f"B{i}", "purpose": "story", "summary": f"Olay {i}{suffix}", "emotional_value": "merak", "learning_value": "yardımlaşma"} for i in range(1, 6)],
        "scenes": scenes, "owner_approved": False,
    }


def test_quality_gate_rejects_adult_infant_speech():
    packet = _packet_from_mapping(payload(infant_text="Şimdi birlikte dikkatlice düşünmeliyiz"), request())
    report = DeterministicStoryQualityGate(StoryRoomPolicy()).evaluate(packet, context())
    assert not report.passed
    assert "dialogue.infant_language" in {issue.code for issue in report.issues}


def test_room_revises_until_deterministic_gate_passes(tmp_path):
    calls = []
    drafts = [payload(infant_text="Şimdi birlikte dikkatlice düşünmeliyiz"), payload(suffix=" final")]
    def generator(prompt):
        calls.append(json.loads(prompt))
        return json.dumps(drafts[len(calls) - 1], ensure_ascii=False)
    memory = StoryRoomMemory(tmp_path / "room.db")
    packet = AutonomousWritersRoom(generator=generator, memory=memory).plan(request(), context())
    assert packet.title.endswith("final")
    assert len(calls) == 2
    assert calls[1]["deterministic_review"]["passed"] is False
    with memory._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 2


def test_room_fails_closed_after_revision_limit(tmp_path):
    bad = payload(infant_text="Bu cümle bir bebek için kesinlikle çok uzun")
    room = AutonomousWritersRoom(generator=lambda _: json.dumps(bad, ensure_ascii=False), memory=StoryRoomMemory(tmp_path / "room.db"), policy=StoryRoomPolicy(maximum_rounds=2))
    with pytest.raises(StoryQualityRejected, match="after 2 rounds"):
        room.plan(request(), context())


def test_room_repairs_provider_schema_instead_of_crashing(tmp_path):
    malformed = payload()
    malformed["scenes"][0]["dialogue"][0] = {
        "speaker": "aden", "text": "Kaan, şuna bak!", "intent": "merak"
    }
    calls = []
    drafts = [malformed, payload(suffix=" repaired")]

    def generator(prompt):
        calls.append(json.loads(prompt))
        return json.dumps(drafts[len(calls) - 1], ensure_ascii=False)

    memory = StoryRoomMemory(tmp_path / "room.db")
    packet = AutonomousWritersRoom(generator=generator, memory=memory).plan(request(), context())

    assert packet.title.endswith("repaired")
    assert len(calls) == 2
    assert calls[1]["deterministic_review"]["issues"][0]["code"] == "schema.invalid"
    assert calls[1]["previous_draft"]["scenes"][0]["dialogue"][0]["speaker"] == "aden"
    assert calls[1]["required_response_shape"]["scenes"][0]["dialogue"][0]["speaker_character_id"]
    assert memory.attempt_count(next(iter(_run_ids(memory)))) == 2


def _run_ids(memory):
    with memory._connect() as conn:
        return [row[0] for row in conn.execute("SELECT DISTINCT run_id FROM attempts")]


def test_room_repairs_json_fenced_provider_response(tmp_path):
    fenced = "```json\n" + json.dumps(payload(), ensure_ascii=False) + "\n```"
    packet = AutonomousWritersRoom(
        generator=lambda _: fenced, memory=StoryRoomMemory(tmp_path / "room.db")
    ).plan(request(), context())
    assert packet.title == "Uçurtma Dostları"


def test_room_fails_closed_after_repeated_schema_errors(tmp_path):
    malformed = json.dumps({"title": "Eksik"})
    memory = StoryRoomMemory(tmp_path / "room.db")
    room = AutonomousWritersRoom(
        generator=lambda _: malformed,
        memory=memory,
        policy=StoryRoomPolicy(maximum_rounds=2),
    )
    with pytest.raises(StoryQualityRejected, match="schema.invalid"):
        room.plan(request(), context())
    assert sum(memory.attempt_count(run_id) for run_id in _run_ids(memory)) == 2


def test_accepted_story_cannot_be_reused(tmp_path):
    memory = StoryRoomMemory(tmp_path / "room.db")
    AutonomousWritersRoom(generator=lambda _: json.dumps(payload(), ensure_ascii=False), memory=memory).plan(request(), context())
    room = AutonomousWritersRoom(generator=lambda _: json.dumps(payload(), ensure_ascii=False), memory=memory, policy=StoryRoomPolicy(maximum_rounds=1))
    with pytest.raises(StoryQualityRejected, match="originality.duplicate"):
        room.plan(request(), context())


def test_provider_retries_transient_timeout(monkeypatch):
    calls = []
    progress = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "{}"}}]}
            ).encode()

    def urlopen(*_, **__):
        calls.append(True)
        if len(calls) == 1:
            raise TimeoutError("temporary free-model queue timeout")
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("ahos.autonomous_story_room.urllib.request.urlopen", urlopen)
    monkeypatch.setattr("ahos.autonomous_story_room.time.sleep", lambda _: None)
    generator = OpenAICompatibleStoryGenerator(
        model_id="openrouter/free",
        allow_external=True,
        retry_attempts=3,
        retry_delay_seconds=0,
        progress=progress.append,
    )

    assert generator("prompt") == "{}"
    assert len(calls) == 2
    assert any("retrying" in message for message in progress)
