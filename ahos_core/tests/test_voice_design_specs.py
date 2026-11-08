import pytest

from ahos.voice_design_specs import ADEN_VOICE_DESIGN, require_character_fit


def test_aden_is_explicitly_preschool_age_girl():
    assert ADEN_VOICE_DESIGN.character_id == "aden"
    assert ADEN_VOICE_DESIGN.age_years == 3
    assert ADEN_VOICE_DESIGN.gender_presentation == "girl"
    assert "adult-woman-timbre" in ADEN_VOICE_DESIGN.forbidden_traits
    assert "real-person-imitation" in ADEN_VOICE_DESIGN.forbidden_traits


def test_preschool_voice_fit_is_allowed():
    require_character_fit(ADEN_VOICE_DESIGN, apparent_age="preschool-child")


@pytest.mark.parametrize("bad_age", ["adult-woman", "adult-man", "teen", "middle-aged"])
def test_adult_or_older_voice_fit_is_rejected(bad_age):
    with pytest.raises(ValueError):
        require_character_fit(ADEN_VOICE_DESIGN, apparent_age=bad_age)
