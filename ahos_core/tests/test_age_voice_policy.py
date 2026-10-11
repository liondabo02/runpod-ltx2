import pytest

from ahos.age_voice_policy import AgeVoicePolicyError, core_age_voice_policy


def test_infant_never_receives_sentence_tts():
    policy = core_age_voice_policy("ramin")
    assert policy.speech_mode == "infant_vocalization"
    assert policy.sentence_tts_allowed is False
    with pytest.raises(AgeVoicePolicyError, match="vocalization assets"):
        policy.validate_text("Merhaba arkadaşlar")


def test_toddler_is_limited_to_short_natural_utterances():
    policy = core_age_voice_policy("kaan")
    policy.validate_text("Aden bak uçurtma uçuyor")
    with pytest.raises(AgeVoicePolicyError, match="maximum is 8"):
        policy.validate_text("bir iki üç dört beş altı yedi sekiz dokuz")


def test_preschool_and_adult_get_distinct_performance_profiles():
    child = core_age_voice_policy("aden")
    adult = core_age_voice_policy("harun")
    assert child.age_stage == "preschool"
    assert adult.age_stage == "adult"
    assert child.temperature != adult.temperature
    assert child.maximum_words_per_utterance == 18
    assert adult.maximum_words_per_utterance is None
    assert child.synthetic_reference_required is True
