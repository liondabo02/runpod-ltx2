from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .episode_casting import (
    EpisodeCastPreparation,
    EpisodeGuestCastDirector,
    StructuredGuestCastPlanner,
    VoiceDesignBrief,
    core_cast_voice_briefs,
)
from .story_engine import EpisodeProductionPacket, EpisodeRequest


class EpisodeVoiceReadinessError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VoiceReadyEpisodePlan:
    preparation: EpisodeCastPreparation
    all_voice_briefs: tuple[VoiceDesignBrief, ...]

    def by_character(self) -> dict[str, VoiceDesignBrief]:
        return {item.character_id: item for item in self.all_voice_briefs}


class VoiceReadyEpisodeOrchestrator:
    """Prepare complete character/voice casting before final screenplay output.

    Flow:
      owner prompt/topic
        -> guest-cast outline pass
        -> episode-scoped guest Character Bible entries
        -> age/gender/species-aware voice briefs for recurring + guest cast
        -> expanded allowed cast for the strict story planner
        -> final screenplay
        -> verify every speaking/vocal character has an audio mode

    No paid provider is called here. This is planning/validation only.
    """

    def __init__(
        self,
        *,
        guest_planner: StructuredGuestCastPlanner,
        guest_director: EpisodeGuestCastDirector,
    ) -> None:
        self.guest_planner = guest_planner
        self.guest_director = guest_director

    def prepare(self, request: EpisodeRequest) -> VoiceReadyEpisodePlan:
        guests = self.guest_planner.plan(request)
        preparation = self.guest_director.prepare(request, guests)

        core = {
            item.character_id: item
            for item in core_cast_voice_briefs()
            if item.character_id in request.cast_ids
        }
        missing_core = set(request.cast_ids) - set(core)
        if missing_core:
            raise EpisodeVoiceReadinessError(
                "recurring cast has no canonical voice-design metadata: "
                + ", ".join(sorted(missing_core))
            )

        all_briefs = tuple(
            [core[cid] for cid in request.cast_ids]
            + list(preparation.voice_briefs)
        )
        return VoiceReadyEpisodePlan(
            preparation=preparation,
            all_voice_briefs=all_briefs,
        )

    @staticmethod
    def verify_final_packet(
        packet: EpisodeProductionPacket,
        ready: VoiceReadyEpisodePlan,
    ) -> None:
        briefs = ready.by_character()
        allowed = set(ready.preparation.expanded_request.cast_ids)
        packet_cast = set(packet.cast_ids)

        if packet_cast != allowed:
            raise EpisodeVoiceReadinessError(
                "final screenplay cast differs from pre-materialized voice-ready cast"
            )

        speakers = {
            line.speaker_character_id
            for scene in packet.scenes
            for line in scene.dialogue
        }
        scene_cast = {
            character_id
            for scene in packet.scenes
            for character_id in scene.cast_ids
        }
        missing = (speakers | scene_cast) - set(briefs)
        if missing:
            raise EpisodeVoiceReadinessError(
                "screenplay contains characters without voice/audio plans: "
                + ", ".join(sorted(missing))
            )

        # No full sentence dialogue for infant-only or non-talking animal modes.
        invalid_dialogue = []
        for scene in packet.scenes:
            for line in scene.dialogue:
                brief = briefs[line.speaker_character_id]
                if brief.speech_mode in {
                    "infant_vocalization",
                    "animal_vocalization",
                } and line.text.strip():
                    invalid_dialogue.append(
                        f"{line.speaker_character_id}@{scene.scene_id}"
                    )
        if invalid_dialogue:
            raise EpisodeVoiceReadinessError(
                "non-speech characters received sentence dialogue: "
                + ", ".join(sorted(invalid_dialogue))
            )

    @staticmethod
    def audio_modes(
        ready: VoiceReadyEpisodePlan,
    ) -> Mapping[str, str]:
        return {
            item.character_id: item.speech_mode
            for item in ready.all_voice_briefs
        }
