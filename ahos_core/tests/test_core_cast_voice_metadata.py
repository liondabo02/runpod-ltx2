from ahos.core_cast_voice_catalog import CORE_CAST_VOICE_SPECS
from ahos.episode_casting import core_cast_voice_briefs


def test_exact_recurring_adult_ages_and_genders_are_in_catalog():
    specs = {item.character_id: item for item in CORE_CAST_VOICE_SPECS}
    expected = {
        "harun": (30.0, "man"),
        "davut": (30.0, "man"),
        "ahmet": (33.0, "man"),
        "esma": (29.0, "woman"),
        "fatos": (30.0, "woman"),
        "esra": (33.0, "woman"),
        "veysel": (33.0, "man"),
        "oznur": (31.0, "woman"),
    }
    for character_id, (age, gender) in expected.items():
        assert specs[character_id].age_years == age
        assert specs[character_id].gender_presentation == gender


def test_exact_age_and_gender_reach_voice_design_instructions():
    briefs = {item.character_id: item for item in core_cast_voice_briefs()}
    expected_fragments = {
        "harun": "30-year-old adult man",
        "davut": "30-year-old adult man",
        "ahmet": "33-year-old adult man",
        "esma": "29-year-old adult woman",
        "fatos": "30-year-old adult woman",
        "esra": "33-year-old adult woman",
        "veysel": "33-year-old adult man",
        "oznur": "31-year-old adult woman",
    }
    for character_id, fragment in expected_fragments.items():
        assert fragment in briefs[character_id].design_instruction


def test_infants_are_vocalization_only():
    specs = {item.character_id: item for item in CORE_CAST_VOICE_SPECS}
    assert specs["medine"].speech_mode == "infant_vocalization"
    assert specs["ramin"].speech_mode == "infant_vocalization"
