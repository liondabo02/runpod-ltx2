    guest_character_ids: tuple[str, ...]
    voice_briefs: tuple[VoiceDesignBrief, ...]


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "guest"


def _human_speech_mode(age_years: float | None, age_stage: str) -> str:
    normalized = age_stage.strip().lower()
    if age_years is not None:
        if age_years < 0.5:
            return "infant_vocalization"
        if age_years < 2.5:
            return "early_speech"
        return "speech"
    if normalized in {"newborn", "infant", "baby"}:
        return "infant_vocalization"
    if normalized in {"toddler"}:
        return "early_speech"
    return "speech"


def _human_voice_instruction(
    *,
    age_years: float | None,
    age_stage: str,
    gender_presentation: str,
    role: str,
    personality_hint: str = "",
    voice_hint: str = "",
) -> str:
    age = age_stage.strip().lower() or "adult"
    gender = gender_presentation.strip().lower() or "unspecified"

    if age_years is not None and age_years <= 5:
        if age_years < 0.5:
            return (
                "Fictional very young infant vocal character. Use only natural baby coos, "
                "soft babble, tiny laughs, fussing or crying as directed by the scene; "
                "never produce adult-like sentence speech."
            )
        if age_years < 1.5:
            base = (
                f"Fictional {gender} toddler around one year old. Very young child timbre, "
                "tiny vocal tract, natural toddler cadence, only short early words or "
                "simple sounds, playful and warm. Never sound like an adult and never use "
                "an adult falsetto pretending to be a child."
            )
        elif age_years < 3:
            base = (
                f"Fictional {gender} toddler about {age_years:g} years old. Natural small-child "
                "timbre, short simple phrases, lively but believable toddler rhythm, warm "
                "and clear enough for children's animation. No adult timbre and no falsetto."
            )
        else:
            base = (
                f"Fictional preschool-age {gender} child about {age_years:g} years old. "
                "Bright, playful, warm and innocent; natural child cadence and small youthful "
                "vocal quality; clear articulation for children's animation. Never sound "
                "like an adult and never use an adult falsetto imitation."
            )
    elif age in {"child", "school-age", "young child"}:
        base = (
            f"Fictional {gender} child voice. Natural youthful timbre, age-appropriate "
            "cadence, expressive but believable, clear for children's animation; no adult timbre."
        )
    elif age in {"teen", "teenager", "adolescent"}:
        base = (
            f"Fictional {gender} teenager. Youthful adolescent timbre, natural conversational "
            "delivery, emotionally believable and not adult-aged."
        )
    elif age in {"elder", "elderly", "senior", "older adult"} or (
        age_years is not None and age_years >= 65
    ):
        base = (
            f"Fictional older {gender} adult. Mature natural voice with gentle age texture, "
            "clear diction and believable pacing. Respectful and human; never caricature age "
            "with exaggerated frailty or comic stereotypes."
        )
    else:
        exact_age = (
            f"{int(age_years)}-year-old "
            if age_years is not None
            else ""
        )
        base = (
            f"Fictional {exact_age}adult {gender} voice for the role of {role}. "
            "Natural conversational delivery, age-appropriate and distinct but realistic timbre, "
            "clear diction and emotionally appropriate performance. Do not imitate any real person."
        )

    extras = [x.strip() for x in (personality_hint, voice_hint) if x.strip()]
    if extras:
        base += " Character direction: " + "; ".join(extras) + "."
    return base


def build_voice_design_brief(
    *,
    character_id: str,
    display_name: str,
    role: str,
    species: str,
    age_years: float | None,
    age_stage: str,
    gender_presentation: str,
    speaking: bool = True,
    talking_animal: bool = False,
    personality_hint: str = "",
    voice_hint: str = "",
    persistent_scope: str,
) -> VoiceDesignBrief:
    species_normalized = species.strip().lower()
    target_languages = ("tr", "de", "ar", "fr", "es", "en")