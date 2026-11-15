from pathlib import Path

import pytest

from ahos.audio_pipeline import (
    AudioPipelineError,
    AudioProductionPlanner,
    AudioProviderDescriptor,
    AudioProviderRegistry,
    UnsupportedLanguageError,
    VoiceProfile,
    AudioManifestStore,
)
from ahos.character_memory import CharacterBibleStore, CharacterProfile


def store(tmp_path: Path):
    db = CharacterBibleStore(tmp_path / "characters.db")
    db.upsert_profile(
        CharacterProfile(
            character_id="aden",
            display_name="Aden",
            canonical_role="lead_child",
            family_group="central-family",
            age_stage="young child",
        ),
        author="test",
        reason="seed",
    )
    return db


def test_translation_stub_never_fakes_translation(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Merhaba",
    )
    assert line.localized_text == ""
    assert line.localization_status == "translation_required"


def test_source_language_can_be_tts_ready(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="en",
        target_language="en",
        source_text="Hello",
    )
    voice = VoiceProfile(
        character_id="aden",
        voice_id="aden-v1",
        provider_preference=("runpod-kokoro",),
    )
    job = planner.make_tts_job(
        line,
        voice=voice,
        allow_paid=True,
        allow_external=True,
    )
    assert job.provider_id == "runpod-kokoro"
    assert job.paid is True


def test_multilingual_commercial_selection_prefers_chatterbox(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="tr",
        source_text="Merhaba",
    )
    voice = VoiceProfile(
        character_id="aden",
        voice_id="aden-v1",
        provider_preference=("chatterbox-multilingual",),
    )
    job = planner.make_tts_job(
        line,
        voice=voice,
        allow_paid=True,
        allow_external=True,
        commercial_use=True,
    )
    assert job.provider_id == "chatterbox-multilingual"


def test_translation_required_blocks_tts(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="tr",
        target_language="de",
        source_text="Merhaba",
    )
    with pytest.raises(AudioPipelineError):
        planner.make_tts_job(
            line,
            voice=VoiceProfile("aden", "aden-v1", ("chatterbox-multilingual",)),
            allow_paid=True,
            allow_external=True,
        )


def test_commercial_policy_blocks_research_only_provider():
    registry = AudioProviderRegistry(
        (
            AudioProviderDescriptor(
                provider_id="research-only",
                name="Research",
                supported_languages=frozenset({"en"}),
                capabilities=frozenset({"tts"}),
                paid=False,
                external=False,
                commercial_default=False,
                priority=1,
            ),
        )
    )
    with pytest.raises(UnsupportedLanguageError):
        registry.choose(
            language="en",
            capability="tts",
            allow_paid=True,
            allow_external=True,
            commercial_use=True,
        )


def test_audio_manifest_is_persistent(tmp_path: Path):
    planner = AudioProductionPlanner(character_store=store(tmp_path))
    line = planner.make_localization_stub(
        line_id="L1",
        episode_id="S01E001",
        scene_id="SCENE-01",
        speaker_character_id="aden",
        source_language="en",
        target_language="en",
        source_text="Hello",
    )
    job = planner.make_tts_job(
        line,
        voice=VoiceProfile("aden", "aden-v1", ("runpod-kokoro",)),
        allow_paid=True,
        allow_external=True,
    )
    db = tmp_path / "audio.db"
    AudioManifestStore(db).upsert_planned(job)
    assert AudioManifestStore(db).count("S01E001") == 1


def _tiny_episode():
    from ahos.studio_2d import Episode, Line, Scene

    return Episode(title="d", language="tr", scenes=[
        Scene("s1", "Açılış", "day", ["aden"],
              [Line("s1", "aden", "merhaba", 2.0), Line("s1", "aden", "devam", 1.0)]),
        Scene("s2", "Kapanış", "night", ["kaan"], [Line("s2", "kaan", "hoşça kal", 2.0)]),
    ])


def test_speaking_profile_age_overrides_role():
    """Yaş bandı pitch/rate'i belirler; rol yalnızca stil ekler."""

    from ahos.audio_pipeline import speaking_profile

    child_hero = speaking_profile("kahraman", "child")
    assert child_hero["pitch"] == "+25Hz"
    assert child_hero["rate"] == "+8%"
    assert speaking_profile(None, "elder")["pitch"] == "-20Hz"
    assert speaking_profile("bilge", None)["pitch"] == "-12Hz"
    assert speaking_profile(None, None)["pitch"] == "+0Hz"


def test_stage_gate_accepts_voice_directory(tmp_path):
    """Dizin kanıtı: `voice/` altında dosya varsa voice aşaması geçer."""

    from ahos.studio_department import require_evidence

    (tmp_path / "voices.json")  # yok: dizin alternatifi kullanılacak
    (tmp_path / "voice").mkdir()
    (tmp_path / "voice" / "line_00.wav").write_bytes(b"RIFF" + b"\x00" * 40)

    report = require_evidence("voice", tmp_path)
    assert report["ok"] is True
    assert "voices.json" in report["present"]


def test_default_adapters_registers_local_edge():
    """Adapter haritası: gerçek motor (`local-edge`) kayıtlı, uydurma yok."""

    from ahos.audio_pipeline import default_adapters

    adapters = default_adapters()
    assert "local-edge" in adapters
    assert callable(adapters["local-edge"])


def test_fallback_skips_unregistered_provider(tmp_path):
    """Kayıtlı adapter yoksa sessizce başarı sayılmaz: açık hata."""

    import pytest

    from ahos.audio_pipeline import (AudioBudgetPolicy, AudioPipelineError,
                                     AudioProviderDescriptor, AudioProviderRegistry,
                                     plan_jobs, synthesize_with_fallback)

    paid = AudioProviderDescriptor(
        provider_id="paid-only", name="paid", supported_languages=frozenset({"tr"}),
        capabilities=frozenset({"tts"}), paid=True, external=True,
        commercial_default=True, priority=1)
    registry = AudioProviderRegistry((paid,))
    policy = AudioBudgetPolicy(allow_paid=True, approval="owner-ok",
                               budget_remaining_usd=5.0)
    job = plan_jobs(_tiny_episode(), policy, registry=registry)[0]

    with pytest.raises(AudioPipelineError):
        synthesize_with_fallback(job, tmp_path / "x.wav", {}, policy=policy,
                                 registry=registry)

    from ahos.audio_pipeline import AudioBudgetPolicy, plan_jobs

    policy = AudioBudgetPolicy()
    first = plan_jobs(_tiny_episode(), policy)
    second = plan_jobs(_tiny_episode(), policy)

    assert [job.job_id for job in first] == [job.job_id for job in second]
    assert all(job.paid is False for job in first)
    # 3 replik + 2 sahne müziği
    assert len(first) == 5
    assert [job.task_type.value for job in first].count("dialogue_tts") == 3


def test_resolve_provider_by_language_capability_and_priority():
    from ahos.audio_pipeline import (AudioBudgetPolicy, AudioProviderDescriptor,
                                     AudioProviderRegistry, resolve_provider)

    def provider(pid, languages, priority, paid=False, caps=("tts",)):
        return AudioProviderDescriptor(
            provider_id=pid, name=pid, supported_languages=frozenset(languages),
            capabilities=frozenset(caps), paid=paid, external=False,
            commercial_default=True, priority=priority)

    registry = AudioProviderRegistry((
        provider("slow-tr", {"tr"}, 50),
        provider("fast-tr", {"tr"}, 5),
        provider("en-only", {"en"}, 1),
        provider("video-only", {"tr"}, 1, caps=("video",)),
    ))
    policy = AudioBudgetPolicy(allow_external=True)
    assert resolve_provider("tts", "tr", policy, registry=registry).provider_id == "fast-tr"
    assert resolve_provider("tts", "de", policy, registry=registry) is None


def test_paid_provider_requires_approval_and_budget():
    from ahos.audio_pipeline import (AudioBudgetPolicy, AudioProviderDescriptor,
                                     AudioProviderRegistry, resolve_provider)

    paid = AudioProviderDescriptor(
        provider_id="paid-tts", name="paid", supported_languages=frozenset({"tr"}),
        capabilities=frozenset({"tts"}), paid=True, external=True,
        commercial_default=True, priority=1)
    registry = AudioProviderRegistry((paid,))

    assert resolve_provider("tts", "tr", AudioBudgetPolicy(), registry=registry) is None
    assert resolve_provider(
        "tts", "tr", AudioBudgetPolicy(allow_paid=True, approval="owner-ok"),
        registry=registry) is None  # bütçe yok -> çağrı yok
    allowed = AudioBudgetPolicy(allow_paid=True, approval="owner-ok",
                                budget_remaining_usd=5.0)
    assert resolve_provider("tts", "tr", allowed, registry=registry).provider_id == "paid-tts"


def test_fallback_rejects_wrong_language_adapter(tmp_path):
    from ahos.audio_pipeline import (AudioBudgetPolicy, AudioProviderDescriptor,
                                     AudioProviderRegistry, plan_jobs,
                                     synthesize_with_fallback)

    def provider(pid, priority):
        return AudioProviderDescriptor(
            provider_id=pid, name=pid, supported_languages=frozenset({"tr"}),
            capabilities=frozenset({"tts"}), paid=False, external=False,
            commercial_default=True, priority=priority)

    registry = AudioProviderRegistry((provider("first", 1), provider("second", 2)))
    policy = AudioBudgetPolicy(allow_external=True)
    job = plan_jobs(_tiny_episode(), policy, registry=registry)[0]

    def wrong_language(_job, out_path):
        return {"path": str(out_path), "language": "en", "engine": "fake"}

    def good(_job, out_path):
        Path(out_path).write_bytes(b"RIFF")
        return {"path": str(out_path), "language": "tr", "engine": "fake"}

    result = synthesize_with_fallback(
        job, tmp_path / "a.wav",
        {"first": wrong_language, "second": good},
        policy=policy, registry=registry)
    assert result["provider_id"] == "second"
    assert result["tried"] == ["first", "second"]

