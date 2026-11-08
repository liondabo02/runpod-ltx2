from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable, Mapping, Sequence

from .character_memory import CharacterBibleStore, CharacterProfile
from .core_cast_voice_catalog import CORE_CAST_VOICE_SPECS, CoreCastVoiceSpec
from .story_engine import EpisodeRequest


class EpisodeCastingError(RuntimeError):
    pass


class InvalidGuestCharacterError(EpisodeCastingError):
    pass


@dataclass(frozen=True, slots=True)
class GuestCharacterBrief:
    guest_key: str
    display_name: str
    role: str
    species: str = "human"
    age_years: float | None = None
    age_stage: str = "adult"
    gender_presentation: str = "unspecified"
    speaking: bool = True
    talking_animal: bool = False
    recurring_hint: bool = False
    personality_hint: str = ""
    voice_hint: str = ""

    def __post_init__(self) -> None:
        if not self.guest_key.strip():
            raise ValueError("guest_key must not be empty")
        if not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if not self.role.strip():
            raise ValueError("role must not be empty")
        if not self.species.strip():
            raise ValueError("species must not be empty")
        if self.age_years is not None and not 0 <= self.age_years <= 120:
            raise ValueError("age_years must be between 0 and 120")


@dataclass(frozen=True, slots=True)
class VoiceDesignBrief:
    character_id: str
    display_name: str
    role: str
    species: str
    age_stage: str
    gender_presentation: str
    speech_mode: str
    design_provider: str | None
    design_language: str | None
    design_instruction: str
    target_languages: tuple[str, ...]
    persistent_scope: str
    requires_tts: bool
    requires_sfx: bool


@dataclass(frozen=True, slots=True)
class EpisodeCastPreparation:
    episode_id: str
    expanded_request: EpisodeRequest
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

    if species_normalized != "human":
        if talking_animal and speaking:
            instruction = (
                f"Fictional talking {species_normalized} character for children's animation. "
                f"Keep a readable speech voice while preserving playful species flavor. "
                f"Role: {role}. Avoid frightening or harsh animal sounds. "
                "Do not imitate any real person."
            )
            return VoiceDesignBrief(
                character_id=character_id,
                display_name=display_name,
                role=role,
                species=species_normalized,
                age_stage=age_stage,
                gender_presentation=gender_presentation,
                speech_mode="talking_animal",
                design_provider="qwen3-tts-voice-design",
                design_language="en",
                design_instruction=instruction,
                target_languages=target_languages,
                persistent_scope=persistent_scope,
                requires_tts=True,
                requires_sfx=True,
            )

        return VoiceDesignBrief(
            character_id=character_id,
            display_name=display_name,
            role=role,
            species=species_normalized,
            age_stage=age_stage,
            gender_presentation=gender_presentation,
            speech_mode="animal_vocalization",
            design_provider=None,
            design_language=None,
            design_instruction=(
                f"Use species-appropriate {species_normalized} vocalizations matched to scene "
                "emotion and action; no human sentence TTS unless the script explicitly marks "
                "the animal as a talking character."
            ),
            target_languages=target_languages,
            persistent_scope=persistent_scope,
            requires_tts=False,
            requires_sfx=True,
        )

    speech_mode = _human_speech_mode(age_years, age_stage)
    if speech_mode == "infant_vocalization":
        instruction = _human_voice_instruction(
            age_years=age_years,
            age_stage=age_stage,
            gender_presentation=gender_presentation,
            role=role,
            personality_hint=personality_hint,
            voice_hint=voice_hint,
        )
        return VoiceDesignBrief(
            character_id=character_id,
            display_name=display_name,
            role=role,
            species="human",
            age_stage=age_stage,
            gender_presentation=gender_presentation,
            speech_mode=speech_mode,
            design_provider=None,
            design_language=None,
            design_instruction=instruction,
            target_languages=target_languages,
            persistent_scope=persistent_scope,
            requires_tts=False,
            requires_sfx=True,
        )

    return VoiceDesignBrief(
        character_id=character_id,
        display_name=display_name,
        role=role,
        species="human",
        age_stage=age_stage,
        gender_presentation=gender_presentation,
        speech_mode=speech_mode,
        design_provider="qwen3-tts-voice-design",
        design_language="en",
        design_instruction=_human_voice_instruction(
            age_years=age_years,
            age_stage=age_stage,
            gender_presentation=gender_presentation,
            role=role,
            personality_hint=personality_hint,
            voice_hint=voice_hint,
        ),
        target_languages=target_languages,
        persistent_scope=persistent_scope,
        requires_tts=True,
        requires_sfx=speech_mode == "early_speech",
    )


def core_cast_voice_briefs() -> tuple[VoiceDesignBrief, ...]:
    result = []
    for spec in CORE_CAST_VOICE_SPECS:
        result.append(
            build_voice_design_brief(
                character_id=spec.character_id,
                display_name=spec.display_name,
                role=spec.role,
                species=spec.species,
                age_years=spec.age_years,
                age_stage=spec.age_stage,
                gender_presentation=spec.gender_presentation,
                speaking=spec.speech_mode != "infant_vocalization",
                personality_hint=(
                    "recurring series character; preserve identity across episodes; "
                    + spec.voice_direction
                ),
                persistent_scope="series",
            )
        )
    return tuple(result)


class EpisodeGuestCastDirector:
    """Materialize scenario-specific guests before the final story pass.

    The intended production flow is two-pass:
    1) topic/outline -> guest briefs,
    2) register episode-scoped guests + voice briefs,
    3) final story planner receives the expanded allowed cast,
    4) every dialogue speaker therefore already has a visual/voice plan.
    """

    def __init__(self, character_store: CharacterBibleStore) -> None:
        self.character_store = character_store

    def prepare(
        self,
        request: EpisodeRequest,
        guest_briefs: Sequence[GuestCharacterBrief],
    ) -> EpisodeCastPreparation:
        guest_ids: list[str] = []
        voice_briefs: list[VoiceDesignBrief] = []

        for index, guest in enumerate(guest_briefs, start=1):
            guest_id = (
                f"guest:{request.episode_id}:"
                f"{_slug(guest.guest_key or guest.role)}-{index:02d}"
            )
            if guest_id in guest_ids:
                raise InvalidGuestCharacterError(f"duplicate guest id: {guest_id}")

            if guest.species.lower() == "human" and guest.speaking:
                if guest.gender_presentation.strip().lower() == "unspecified":
                    raise InvalidGuestCharacterError(
                        f"speaking human guest {guest.display_name!r} requires "
                        "explicit gender_presentation from the scenario metadata"
                    )

            brief = build_voice_design_brief(
                character_id=guest_id,
                display_name=guest.display_name,
                role=guest.role,
                species=guest.species,
                age_years=guest.age_years,
                age_stage=guest.age_stage,
                gender_presentation=guest.gender_presentation,
                speaking=guest.speaking,
                talking_animal=guest.talking_animal,
                personality_hint=guest.personality_hint,
                voice_hint=guest.voice_hint,
                persistent_scope=(
                    "series-recurring-candidate"
                    if guest.recurring_hint
                    else f"episode:{request.episode_id}"
                ),
            )

            profile = CharacterProfile(
                character_id=guest_id,
                display_name=guest.display_name,
                canonical_role=f"episode_guest:{guest.role}",
                family_group=f"episode-guest:{request.episode_id}",
                age_stage=guest.age_stage,
                personality_anchors=tuple(
                    x
                    for x in (
                        guest.personality_hint.strip(),
                        "scenario-generated guest",
                    )
                    if x
                ),
                voice_anchors=(
                    f"species={guest.species}",
                    f"gender_presentation={guest.gender_presentation}",
                    f"speech_mode={brief.speech_mode}",
                    f"voice_design={brief.design_instruction}",
                ),
                continuity_rules=(
                    f"{guest.display_name} keeps the same episode voice and appearance within {request.episode_id}.",
                    "Do not reuse this guest as a recurring series character unless promoted explicitly.",
                ),
            )
            self.character_store.upsert_profile(
                profile,
                author="studio-voice-director-01",
                reason=f"materialize scenario guest for {request.episode_id}",
            )
            guest_ids.append(guest_id)
            voice_briefs.append(brief)

        expanded = replace(
            request,
            cast_ids=tuple((*request.cast_ids, *guest_ids)),
        )
        return EpisodeCastPreparation(
            episode_id=request.episode_id,
            expanded_request=expanded,
            guest_character_ids=tuple(guest_ids),
            voice_briefs=tuple(voice_briefs),
        )


class StructuredGuestCastPlanner:
    """JSON-only contract for the AI outline pass that discovers guest cast.

    The injected generator is deliberately separate from the final story
    generator so all guest IDs and voice requirements exist before dialogue is
    written.
    """

    def __init__(self, generator: Callable[[str], str]) -> None:
        self._generator = generator

    def plan(self, request: EpisodeRequest) -> tuple[GuestCharacterBrief, ...]:
        import json

        contract = {
            "contract": "ahos.guest-cast.v1",
            "instruction": (
                "Return JSON only with guest_characters. Add guests only when the episode "
                "needs them. For every speaking human guest provide explicit age_years or "
                "age_stage and explicit gender_presentation. For animals provide species "
                "and whether it is a talking_animal. Do not choose a voice by name; describe "
                "the character. Police, doctors, teachers, care-home residents and similar "
                "roles must be cast naturally without stereotypes. Non-talking pets use "
                "animal vocalizations, not human TTS."
            ),
            "episode": {
                "episode_id": request.episode_id,
                "topic": request.topic,
                "learning_goal": request.learning_goal,
                "age_band": request.age_band,
                "primary_language": request.primary_language,
            },
        }
        raw = self._generator(json.dumps(contract, ensure_ascii=False, indent=2))
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidGuestCharacterError(
                f"guest cast planner returned invalid JSON: {exc}"
            ) from exc

        result = []
        for item in payload.get("guest_characters", ()):
            result.append(
                GuestCharacterBrief(
                    guest_key=str(item["guest_key"]),
                    display_name=str(item["display_name"]),
                    role=str(item["role"]),
                    species=str(item.get("species") or "human"),
                    age_years=(
                        float(item["age_years"])
                        if item.get("age_years") is not None
                        else None
                    ),
                    age_stage=str(item.get("age_stage") or "adult"),
                    gender_presentation=str(
                        item.get("gender_presentation") or "unspecified"
                    ),
                    speaking=bool(item.get("speaking", True)),
                    talking_animal=bool(item.get("talking_animal", False)),
                    recurring_hint=bool(item.get("recurring_hint", False)),
                    personality_hint=str(item.get("personality_hint") or ""),
                    voice_hint=str(item.get("voice_hint") or ""),
                )
            )
        return tuple(result)