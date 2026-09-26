from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .kurmanji_tts import (
    KurdishTTSConfig,
    KurdishTTSExecutionApproval,
    KurdishTTSProvider,
)
from .runpod_chatterbox import RunPodChatterboxConfig, RunPodChatterboxProvider
from .runpod_ltx2 import PaidExecutionApproval, RunPodLTX2Config, RunPodLTX2Provider
from .studio_approval import _atomic_write, _read_object
from .studio_executor import StageHandler, StageResult
from .visual_pipeline import RenderJob


class StudioProviderConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProductionProviderConfig:
    ltx2_endpoint_id: str
    chatterbox_endpoint_id: str
    runpod_api_key_env: str = "RUNPOD_API_KEY"
    kurmanji_api_key_env: str = "KURDISH_TTS_API_KEY"
    render_cost_ceiling_usd: float = 0.0
    tts_cost_ceiling_usd: float = 0.0

    @classmethod
    def from_environment(cls) -> "ProductionProviderConfig":
        def money(name: str) -> float:
            raw = os.getenv(name, "0").strip()
            try:
                value = float(raw)
            except ValueError as exc:
                raise StudioProviderConfigurationError(f"{name} must be numeric") from exc
            if value < 0:
                raise StudioProviderConfigurationError(f"{name} must not be negative")
            return value

        return cls(
            ltx2_endpoint_id=os.getenv("RUNPOD_LTX2_ENDPOINT_ID", "").strip(),
            chatterbox_endpoint_id=os.getenv("RUNPOD_CHATTERBOX_ENDPOINT_ID", "").strip(),
            runpod_api_key_env=os.getenv("AHOS_RUNPOD_API_KEY_ENV", "RUNPOD_API_KEY").strip(),
            kurmanji_api_key_env=os.getenv("AHOS_KURMANJI_API_KEY_ENV", "KURDISH_TTS_API_KEY").strip(),
            render_cost_ceiling_usd=money("AHOS_RENDER_COST_CEILING_USD"),
            tts_cost_ceiling_usd=money("AHOS_TTS_COST_CEILING_USD"),
        )

    def validate(self) -> None:
        missing = []
        if not self.ltx2_endpoint_id:
            missing.append("RUNPOD_LTX2_ENDPOINT_ID")
        if not self.chatterbox_endpoint_id:
            missing.append("RUNPOD_CHATTERBOX_ENDPOINT_ID")
        if not os.getenv(self.runpod_api_key_env, "").strip():
            missing.append(self.runpod_api_key_env)
        if not os.getenv(self.kurmanji_api_key_env, "").strip():
            missing.append(self.kurmanji_api_key_env)
        if self.render_cost_ceiling_usd <= 0:
            missing.append("AHOS_RENDER_COST_CEILING_USD")
        if self.tts_cost_ceiling_usd <= 0:
            missing.append("AHOS_TTS_COST_CEILING_USD")
        if missing:
            raise StudioProviderConfigurationError(
                "production providers are not ready: " + ", ".join(missing)
            )

    def status(self) -> dict[str, object]:
        return {
            "ltx2_endpoint_present": bool(self.ltx2_endpoint_id),
            "chatterbox_endpoint_present": bool(self.chatterbox_endpoint_id),
            "runpod_api_key_present": bool(os.getenv(self.runpod_api_key_env, "").strip()),
            "kurmanji_api_key_present": bool(os.getenv(self.kurmanji_api_key_env, "").strip()),
            "render_cost_ceiling_usd": self.render_cost_ceiling_usd,
            "tts_cost_ceiling_usd": self.tts_cost_ceiling_usd,
        }


def _paid_approval(ledger: Mapping[str, object]) -> PaidExecutionApproval:
    return PaidExecutionApproval(
        owner_approved=True,
        execution_enabled=ledger.get("status") in {"running", "retryable"},
        paid_provider_enabled=True,
    )


def _render_job(value: Mapping[str, object]) -> RenderJob:
    def strings(name: str) -> tuple[str, ...]:
        raw = value.get(name, [])
        if not isinstance(raw, list):
            raise StudioProviderConfigurationError(f"render job {name} must be a list")
        return tuple(str(item) for item in raw)

    return RenderJob(
        job_id=str(value["job_id"]), episode_id=str(value["episode_id"]),
        shot_id=str(value["shot_id"]), prompt_id=str(value["prompt_id"]),
        output_asset_id=str(value["output_asset_id"]), mode=str(value["mode"]),
        seed=int(value["seed"]), positive_prompt=str(value["positive_prompt"]),
        negative_prompt=str(value["negative_prompt"]),
        reference_asset_ids=strings("reference_asset_ids"),
        continuity_constraints=strings("continuity_constraints"),
        style_id=str(value["style_id"]), duration_seconds=int(value["duration_seconds"]),
        output_prefix=str(value["output_prefix"]),
    )


def _local_file(root: Path, uri: str, *, label: str) -> Path:
    raw = uri.removeprefix("file://")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise StudioProviderConfigurationError(f"{label} escapes studio directory") from exc
    if not candidate.is_file():
        raise StudioProviderConfigurationError(f"{label} is missing: {candidate}")
    return candidate


def build_production_handlers(
    config: ProductionProviderConfig,
    *,
    ltx2: RunPodLTX2Provider | None = None,
    chatterbox: RunPodChatterboxProvider | None = None,
    kurmanji: KurdishTTSProvider | None = None,
) -> tuple[dict[str, StageHandler], dict[str, float]]:
    """Bind real paid providers to the first two executor stages.

    Mixing, assembly and delivery QA remain intentionally unbound until their
    local FFmpeg executors are configured. This prevents a remote render/TTS
    response from being mislabeled as a finished episode.
    """
    config.validate()
    ltx2 = ltx2 or RunPodLTX2Provider(RunPodLTX2Config(
        endpoint_id=config.ltx2_endpoint_id, api_key_env=config.runpod_api_key_env,
        request_timeout_seconds=900.0,
    ))
    chatterbox = chatterbox or RunPodChatterboxProvider(RunPodChatterboxConfig(
        endpoint_id=config.chatterbox_endpoint_id, api_key_env=config.runpod_api_key_env,
        request_timeout_seconds=900.0,
    ))
    kurmanji = kurmanji or KurdishTTSProvider(KurdishTTSConfig(
        api_key_env=config.kurmanji_api_key_env, request_timeout_seconds=300.0,
    ))

    def render(root: Path, ledger: Mapping[str, object]) -> StageResult:
        manifest = _read_object(root / "artifacts" / "render-jobs.json")
        raw_jobs = manifest.get("jobs")
        if not isinstance(raw_jobs, list) or not raw_jobs:
            raise StudioProviderConfigurationError("render manifest has no jobs")
        references = _read_object(root / "artifacts" / "reference-images.json")
        reference_map = references.get("assets")
        if not isinstance(reference_map, Mapping):
            raise StudioProviderConfigurationError("reference-images.json has no assets map")
        output_dir = root / "runtime-artifacts" / "renders"
        output_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[str] = []
        evidence: list[dict[str, object]] = []
        for raw in raw_jobs:
            if not isinstance(raw, Mapping):
                raise StudioProviderConfigurationError("render job must be an object")
            job = _render_job(raw)
            if not job.reference_asset_ids:
                raise StudioProviderConfigurationError(
                    f"render job {job.job_id} has no locked character reference"
                )
            reference_uri = reference_map.get(job.reference_asset_ids[0])
            if not isinstance(reference_uri, str):
                raise StudioProviderConfigurationError(
                    f"reference asset is unresolved: {job.reference_asset_ids[0]}"
                )
            reference = _local_file(root, reference_uri, label="render reference")
            encoded = base64.b64encode(reference.read_bytes()).decode("ascii")
            response = ltx2.submit(
                ltx2.render_payload(job, input_image_base64=encoded,
                                    wait=True, return_output_base64=True),
                approval=_paid_approval(ledger), synchronous=True,
            )
            target = output_dir / f"{job.output_asset_id}.mp4"
            materialized = ltx2.materialize_inline_output(response, target)
            relative = target.relative_to(root).as_posix()
            artifacts.append(relative)
            evidence.append({"job_id": job.job_id, "asset_id": job.output_asset_id,
                             "path": relative, "sha256": materialized.sha256,
                             "size_bytes": materialized.size_bytes})
        evidence_path = output_dir / "render-evidence.json"
        _atomic_write(evidence_path, {"schema": "ahos.render-execution-evidence.v1",
                                      "episode_id": ledger["episode_id"], "outputs": evidence})
        artifacts.append(evidence_path.relative_to(root).as_posix())
        return StageResult(tuple(artifacts), config.render_cost_ceiling_usd,
                           f"materialized {len(evidence)} verified LTX-2 renders")

    def tts(root: Path, ledger: Mapping[str, object]) -> StageResult:
        localization = _read_object(root / "artifacts" / "localization-plan.json")
        casting = _read_object(root / "artifacts" / "voice-casting.json")
        raw_units, raw_characters = localization.get("units"), casting.get("characters")
        if not isinstance(raw_units, list) or not isinstance(raw_characters, list):
            raise StudioProviderConfigurationError("localization or voice plan is invalid")
        voices = {str(item.get("character_id")): item for item in raw_characters
                  if isinstance(item, Mapping)}
        output_dir = root / "runtime-artifacts" / "tts"
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs: list[dict[str, object]] = []
        artifacts: list[str] = []
        paid = _paid_approval(ledger)
        kurdish_approval = KurdishTTSExecutionApproval(True, True, True, True)
        for raw in raw_units:
            if not isinstance(raw, Mapping):
                raise StudioProviderConfigurationError("localization unit must be an object")
            text = str(raw.get("localized_text") or "").strip()
            if not text:
                raise StudioProviderConfigurationError(
                    f"translation is missing: {raw.get('unit_id')}"
                )
            character_id = str(raw.get("speaker_character_id") or "")
            voice = voices.get(character_id)
            if not isinstance(voice, Mapping):
                raise StudioProviderConfigurationError(f"voice casting missing: {character_id}")
            language = str(raw.get("target_language") or "")
            voice_ids = voice.get("voice_ids")
            if not isinstance(voice_ids, Mapping) or not str(voice_ids.get(language) or "").strip():
                raise StudioProviderConfigurationError(
                    f"approved {language} voice_id missing for {character_id}"
                )
            voice_id = str(voice_ids[language])
            if language == "ku-latn":
                audio = kurmanji.synthesize(text=text, voice_id=voice_id,
                                             approval=kurdish_approval).body
                provider_id = kurmanji.provider_id
            else:
                reference_uri = str(voice.get("reference_audio_uri") or "")
                reference = _local_file(root, reference_uri, label="voice reference")
                encoded = base64.b64encode(reference.read_bytes()).decode("ascii")
                audio = chatterbox.synthesize(text=text, language_id=language,
                                               voice_id=voice_id,
                                               reference_audio_base64=encoded,
                                               approval=paid)
                provider_id = chatterbox.provider_id
            safe_id = str(raw.get("unit_id") or "unit").replace(":", "_").replace("/", "_")
            target = output_dir / f"{safe_id}.wav"
            target.write_bytes(audio)
            relative = target.relative_to(root).as_posix()
            artifacts.append(relative)
            outputs.append({"unit_id": raw.get("unit_id"), "language": language,
                            "provider_id": provider_id, "path": relative})
        evidence_path = output_dir / "tts-evidence.json"
        _atomic_write(evidence_path, {"schema": "ahos.tts-execution-evidence.v1",
                                      "episode_id": ledger["episode_id"], "outputs": outputs})
        artifacts.append(evidence_path.relative_to(root).as_posix())
        return StageResult(tuple(artifacts), config.tts_cost_ceiling_usd,
                           f"materialized {len(outputs)} verified TTS files in seven languages")

    return (
        {"render": render, "tts_7_languages": tts},
        {"render": config.render_cost_ceiling_usd,
         "tts_7_languages": config.tts_cost_ceiling_usd},
    )


__all__ = [
    "ProductionProviderConfig", "StudioProviderConfigurationError",
    "build_production_handlers",
]
