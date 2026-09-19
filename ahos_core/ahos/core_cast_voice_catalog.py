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
    recurring: bool = True


# Canonical voice-casting metadata for the 16 recurring characters.
# Very young babies are intentionally routed to infant vocalizations instead of
# adult-like sentence TTS. Ages are production metadata, not public biography.
CORE_CAST_VOICE_SPECS: tuple[CoreCastVoiceSpec, ...] = (
    CoreCastVoiceSpec("aden", "Aden", "human", 3.0, "preschool", "girl", "lead child", "speech"),
    CoreCastVoiceSpec("kaan", "Kaan", "human", 1.0, "toddler", "boy", "lead child", "early_speech"),
    CoreCastVoiceSpec("esra", "Esra", "human", None, "adult", "woman", "mother", "speech"),
    CoreCastVoiceSpec("ahmet", "Ahmet", "human", None, "adult", "man", "father", "speech"),
    CoreCastVoiceSpec("esma", "Esma", "human", None, "adult", "woman", "aunt", "speech"),
    CoreCastVoiceSpec("harun", "Harun", "human", None, "adult", "man", "uncle", "speech"),
    CoreCastVoiceSpec("veysel", "Veysel", "human", None, "adult", "man", "family friend", "speech"),
    CoreCastVoiceSpec("oznur", "Öznur", "human", None, "adult", "woman", "family friend", "speech"),
    CoreCastVoiceSpec("salih", "Salih", "human", 2.0, "toddler", "boy", "child", "early_speech"),
    CoreCastVoiceSpec("medine", "Medine", "human", 2.0 / 12.0, "infant", "girl", "baby", "infant_vocalization"),
    CoreCastVoiceSpec("davut", "Davut", "human", None, "adult", "man", "family friend", "speech"),
    CoreCastVoiceSpec("fatos", "Fatoş", "human", None, "adult", "woman", "family friend", "speech"),
    CoreCastVoiceSpec("emos", "Emoş", "human", 4.0, "preschool", "girl", "child", "speech"),
    CoreCastVoiceSpec("berzan", "Berzan", "human", 2.0, "toddler", "boy", "child", "early_speech"),
    CoreCastVoiceSpec("aras", "Aras", "human", 2.0, "toddler", "boy", "child", "early_speech"),
    CoreCastVoiceSpec("ramin", "Ramin", "human", 1.0 / 12.0, "infant", "boy", "baby", "infant_vocalization"),
)


def core_voice_spec(character_id: str) -> CoreCastVoiceSpec:
    for item in CORE_CAST_VOICE_SPECS:
        if item.character_id == character_id:
            return item
    raise KeyError(character_id)
