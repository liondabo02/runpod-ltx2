from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FictionalVoiceDesignSpec:
    character_id: str
    age_years: int
    gender_presentation: str
    design_language: str
    instruction: str
    target_languages: tuple[str, ...]
    forbidden_traits: tuple[str, ...]


ADEN_VOICE_DESIGN = FictionalVoiceDesignSpec(
    character_id="aden",
    age_years=3,
    gender_presentation="girl",
    design_language="en",
    instruction=(
        "A fictional preschool-age girl, about three years old. Bright, playful, "
        "warm and innocent. Small youthful vocal quality, natural child cadence, "
        "short energetic phrases, clear enough for children's animation. "
        "Do not sound like an adult woman, do not use an adult falsetto, and do "
        "not imitate or resemble any real person."
    ),
    target_languages=("tr", "ku-latn", "de", "ar", "fr", "es", "en"),
    forbidden_traits=(
        "adult-woman-timbre",
        "adult-man-timbre",
        "adult-falsetto-child-imitation",
        "real-person-imitation",
    ),
)


def require_character_fit(spec: FictionalVoiceDesignSpec, *, apparent_age: str) -> None:
    normalized = apparent_age.strip().lower()
    if spec.age_years <= 5 and normalized not in {
        "toddler",
        "preschool",
        "preschool-child",
        "young-child",
    }:
        raise ValueError(
            f"{spec.character_id} requires a preschool/young-child voice, "
            f"not apparent_age={apparent_age!r}"
        )
