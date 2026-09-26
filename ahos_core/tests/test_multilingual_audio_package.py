import pytest

from ahos.multilingual_audio_package import (
    AudioPackageAsset,
    MultilingualAudioPackageError,
    MultilingualAudioPackager,
)


LANGUAGES = ("tr", "ku-latn", "de", "ar", "fr", "es", "en")
SHA = "a" * 64


def complete_assets():
    assets = [
        AudioPackageAsset("music", "music_stem", "private://music.wav", SHA),
        AudioPackageAsset("sfx", "sfx_stem", "private://sfx.wav", SHA),
    ]
    for language in LANGUAGES:
        assets.extend((
            AudioPackageAsset(f"mix:{language}", "final_mix", f"private://{language}.wav", SHA, language, 480),
            AudioPackageAsset(f"sub:{language}", "subtitle", f"private://{language}.srt", SHA, language, 480),
        ))
    return tuple(assets)


def test_complete_seven_language_package_is_ready_and_deterministic():
    kwargs = dict(
        episode_id="S01E001", episode_duration_seconds=480,
        speaking_character_ids=("aden", "harun"),
        canonical_voice_enrollments=((speaker, lang) for speaker in ("aden", "harun") for lang in LANGUAGES),
        assets=complete_assets(),
    )
    first = MultilingualAudioPackager().build(**kwargs)
    second = MultilingualAudioPackager().build(
        episode_id="S01E001", episode_duration_seconds=480,
        speaking_character_ids=("aden", "harun"),
        canonical_voice_enrollments=((speaker, lang) for speaker in ("aden", "harun") for lang in LANGUAGES),
        assets=complete_assets(),
    )
    assert first.ready is True
    assert first.required_languages == LANGUAGES
    assert first.package_hash == second.package_hash


def test_missing_voice_mix_subtitle_and_shared_stems_fail_closed():
    package = MultilingualAudioPackager().build(
        episode_id="E1", episode_duration_seconds=10,
        speaking_character_ids=("aden",), canonical_voice_enrollments=(), assets=(),
        required_languages=("tr",),
    )
    assert package.ready is False
    status = package.language_statuses[0]
    assert status.voice_enrollments_complete is False
    assert status.final_mix_present is False
    assert status.subtitle_present is False


def test_wrong_mix_duration_fails_language_package():
    assets = (
        AudioPackageAsset("music", "music_stem", "m", SHA),
        AudioPackageAsset("sfx", "sfx_stem", "s", SHA),
        AudioPackageAsset("mix:tr", "final_mix", "mix", SHA, "tr", 9.8),
        AudioPackageAsset("sub:tr", "subtitle", "sub", SHA, "tr", 10),
    )
    package = MultilingualAudioPackager().build(
        episode_id="E1", episode_duration_seconds=10, speaking_character_ids=(),
        canonical_voice_enrollments=(), assets=assets, required_languages=("tr",),
    )
    assert package.language_statuses[0].duration_matches is False
    assert package.ready is False


@pytest.mark.parametrize("assets", [
    (AudioPackageAsset("x", "unknown", "x", SHA),),
    (AudioPackageAsset("x", "subtitle", "x", "bad", "tr"),),
])
def test_invalid_asset_contract_is_rejected(assets):
    with pytest.raises(MultilingualAudioPackageError):
        MultilingualAudioPackager().build(
            episode_id="E1", episode_duration_seconds=10, speaking_character_ids=(),
            canonical_voice_enrollments=(), assets=assets, required_languages=("tr",),
        )
