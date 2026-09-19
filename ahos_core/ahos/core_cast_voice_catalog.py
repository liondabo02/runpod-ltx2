from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CoreCastVoiceSpec:
    character_id: str
    display_name: str
    species: str
    age_years: float | None
    age_stage: str
    gender_presentation: str
    role: str
    speech_mode: str
    voice_direction: str
    recurring: bool = True


# Canonical voice-casting metadata for the 16 recurring characters.
# Very young babies are intentionally routed to infant vocalizations instead of
# adult-like sentence TTS. The goal is a distinct series cast, not one generic
# male/female voice reused for everyone.
CORE_CAST_VOICE_SPECS: tuple[CoreCastVoiceSpec, ...] = (
    CoreCastVoiceSpec(
        "aden", "Aden", "human", 3.0, "preschool", "girl", "lead child", "speech",
        "bright, curious, playful, hopeful lead energy; tiny natural child voice, not squeaky",
    ),
    CoreCastVoiceSpec(
        "kaan", "Kaan", "human", 1.0, "toddler", "boy", "lead child", "early_speech",
        "soft cheerful toddler, simple early words, spontaneous little laughs and reactions",
    ),
    CoreCastVoiceSpec(
        "esra", "Esra", "human", None, "adult", "woman", "mother", "speech",
        "warm reassuring mother, calm, affectionate, clear and patient",
    ),
    CoreCastVoiceSpec(
        "ahmet", "Ahmet", "human", None, "adult", "man", "father", "speech",
        "kind relaxed father, grounded and supportive, natural conversational warmth",
    ),
    CoreCastVoiceSpec(
        "esma", "Esma", "human", None, "adult", "woman", "aunt", "speech",
        "friendly warm aunt, lively but gentle, expressive without exaggeration",
    ),
    CoreCastVoiceSpec(
        "harun", "Harun", "human", None, "adult", "man", "uncle", "speech",
        "warm confident optimistic anchor figure, calm humor, reassuring and energetic when needed",
    ),
    CoreCastVoiceSpec(
        "veysel", "Veysel", "human", None, "adult", "man", "family friend", "speech",
        "friendly sociable adult, upbeat natural rhythm, distinct from Harun and Ahmet",
    ),
    CoreCastVoiceSpec(
        "oznur", "Öznur", "human", None, "adult", "woman", "family friend", "speech",
        "warm composed adult woman, friendly and clear, gentle conversational energy",
    ),
    CoreCastVoiceSpec(
        "salih", "Salih", "human", 2.0, "toddler", "boy", "child", "early_speech",
        "playful two-year-old, short phrases, curious reactions, believable toddler rhythm",
    ),
    CoreCastVoiceSpec(
        "medine", "Medine", "human", 2.0 / 12.0, "infant", "girl", "baby", "infant_vocalization",
        "very young infant coos, tiny laughs, soft fussing and crying only; no sentence speech",
    ),
    CoreCastVoiceSpec(
        "davut", "Davut", "human", None, "adult", "man", "family friend", "speech",
        "good-humored relaxed adult man, warm and distinct, natural comic timing when appropriate",
    ),
    CoreCastVoiceSpec(
        "fatos", "Fatoş", "human", None, "adult", "woman", "family friend", "speech",
        "friendly expressive adult woman, warm family tone, natural and not theatrical",
    ),
    CoreCastVoiceSpec(
        "emos", "Emoş", "human", 4.0, "preschool", "girl", "child", "speech",
        "energetic four-year-old girl, confident playful preschool rhythm, clearly distinct from Aden",
    ),
    CoreCastVoiceSpec(
        "berzan", "Berzan", "human", 2.0, "toddler", "boy", "child", "early_speech",
        "two-year-old twin, slightly brighter and more impulsive toddler voice, short phrases",
    ),
    CoreCastVoiceSpec(
        "aras", "Aras", "human", 2.0, "toddler", "boy", "child", "early_speech",
        "two-year-old twin, slightly softer calmer toddler voice, short phrases; distinct from Berzan",
    ),
    CoreCastVoiceSpec(
        "ramin", "Ramin", "human", 1.0 / 12.0, "infant", "boy", "baby", "infant_vocalization",
        "newborn coos, breaths, tiny fussing and crying only; no sentence speech",
    ),
)


def core_voice_spec(character_id: str) -> CoreCastVoiceSpec:
    for item in CORE_CAST_VOICE_SPECS:
        if item.character_id == character_id:
            return item
    raise KeyError(character_id)
