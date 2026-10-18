from __future__ import annotations

import base64
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Mapping, Protocol

from .audio_pipeline import AudioJob, AudioPipelineError, AudioTaskType
from .runpod_ltx2 import (
    PaidExecutionApproval,
    RunPodExecutionGateError,
    RunPodResponseError,
    RunPodTransport,
    UrlLibRunPodTransport,
)


class RunPodChatterboxError(RuntimeError):
    pass


class RunPodChatterboxConfigurationError(RunPodChatterboxError):
    pass


class RunPodChatterboxResponseError(RunPodChatterboxError):
    pass


_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SUPPORTED_LANGUAGES = frozenset({"tr", "de", "ar", "fr", "es", "en"})


@dataclass(frozen=True, slots=True)
class RunPodChatterboxConfig:
    endpoint_id: str
    base_url: str = "https://api.runpod.ai/v2"
    api_key_env: str = "RUNPOD_API_KEY"
    request_timeout_seconds: float = 420.0

    def __post_init__(self) -> None:
        if not _ENDPOINT_RE.fullmatch(self.endpoint_id):
            raise ValueError("invalid RunPod endpoint_id")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme != "https" or parsed.hostname != "api.runpod.ai":
            raise ValueError("RunPod base_url must be https://api.runpod.ai/v2")
        if not self.api_key_env.strip():
            raise ValueError("api_key_env must not be empty")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")

    @property
    def endpoint_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.endpoint_id}"

    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()


class RunPodChatterboxProvider:
    """Guarded AHOS adapter for Chatterbox Multilingual V3 on RunPod Serverless."""

    provider_id = "chatterbox-multilingual"
    supported_languages = SUPPORTED_LANGUAGES

    def __init__(
        self,
        config: RunPodChatterboxConfig,
        *,
        transport: RunPodTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrlLibRunPodTransport()

    def configuration_summary(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "endpoint_id": self.config.endpoint_id,
            "endpoint_base": self.config.endpoint_base,
            "api_key_env": self.config.api_key_env,
            "api_key_present": bool(self.config.api_key()),
            "supported_languages": sorted(self.supported_languages),
            "paid": True,
            "external": True,
            "model": "Chatterbox Multilingual V3",
        }

    def _require_api_key(self) -> str:
        api_key = self.config.api_key()
        if not api_key:
            raise RunPodChatterboxConfigurationError(
                f"{self.config.api_key_env} is not configured"
            )
        return api_key

    @staticmethod
    def speech_payload(
        *,
        text: str,
        language_id: str,
        voice_id: str,
        reference_audio_base64: str | None,
        allow_builtin_voice: bool = False,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        temperature: float = 0.8,
    ) -> dict[str, object]:
        text = text.strip()
        language_id = language_id.strip().lower()
        voice_id = voice_id.strip()

        if not text:
            raise ValueError("text must not be empty")
        if language_id not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported production language: {language_id}")
        if not voice_id:
            raise ValueError("voice_id must not be empty")
        if not reference_audio_base64 and not allow_builtin_voice:
            raise ValueError(
                "reference_audio_base64 is required for character-consistent production"
            )

        if reference_audio_base64:
            try:
                raw = base64.b64decode(reference_audio_base64, validate=True)
            except Exception as exc:
                raise ValueError("reference_audio_base64 is invalid") from exc
            if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
                raise ValueError("reference audio must be RIFF/WAVE")

        return {
            "input": {
                "text": text,
                "language_id": language_id,
                "voice_id": voice_id,
                "reference_audio_base64": reference_audio_base64,
                "allow_builtin_voice": bool(allow_builtin_voice),
                "exaggeration": float(exaggeration),
                "cfg_weight": float(cfg_weight),
                "temperature": float(temperature),
            }
        }

    @staticmethod
    def _extract_wav(response: object) -> bytes:
        if not isinstance(response, Mapping):
            raise RunPodChatterboxResponseError("RunPod returned a non-object response")

        status = str(response.get("status", "")).upper()
        if status and status not in {"COMPLETED", "SUCCESS"}:
            raise RunPodChatterboxResponseError(
                f"RunPod Chatterbox job status is {status}"
            )

        output = response.get("output")
        if not isinstance(output, Mapping):
            raise RunPodChatterboxResponseError("RunPod response has no output object")
        if output.get("ok") is not True:
            raise RunPodChatterboxResponseError(
                f"Chatterbox worker returned failure: {output}"
            )

        encoded = output.get("audio_base64")
        if not isinstance(encoded, str) or not encoded:
            raise RunPodChatterboxResponseError("Chatterbox returned no audio_base64")

        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise RunPodChatterboxResponseError(
                "Chatterbox returned invalid base64 audio"
            ) from exc

        if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
            raise RunPodChatterboxResponseError(
                "Chatterbox returned data that is not a RIFF/WAVE file"
            )
        return raw

    def synthesize(
        self,
        *,
        text: str,
        language_id: str,
        voice_id: str,
        reference_audio_base64: str | None,
        approval: PaidExecutionApproval,
        allow_builtin_voice: bool = False,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        temperature: float = 0.8,
    ) -> bytes:
        approval.require()
        api_key = self._require_api_key()
        payload = self.speech_payload(
            text=text,
            language_id=language_id,
            voice_id=voice_id,
            reference_audio_base64=reference_audio_base64,
            allow_builtin_voice=allow_builtin_voice,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
        )

        try:
            response = self.transport.request_json(
                "POST",
                self.config.endpoint_base + "/runsync",
                api_key=api_key,
                payload=payload,
                timeout=self.config.request_timeout_seconds,
            )
        except RunPodResponseError as exc:
            raise RunPodChatterboxResponseError(str(exc)) from exc

        return self._extract_wav(response)

    def synthesize_job(
        self,
        job: AudioJob,
        *,
        reference_audio_base64: str,
        approval: PaidExecutionApproval,
    ) -> bytes:
        if job.task_type not in {
            AudioTaskType.DIALOGUE_TTS,
            AudioTaskType.NARRATION_TTS,
        }:
            raise AudioPipelineError(f"audio job {job.job_id} is not a TTS job")
        if job.provider_id != self.provider_id:
            raise AudioPipelineError(
                f"audio job {job.job_id} is assigned to {job.provider_id!r}, "
                f"not {self.provider_id!r}"
            )
        if job.language not in self.supported_languages:
            raise AudioPipelineError(
                f"Chatterbox does not support production language {job.language!r}"
            )

        text = str(job.payload.get("text", "")).strip()
        voice_id = str(job.payload.get("voice_id", "")).strip()
        reference_uri = str(job.payload.get("reference_audio_uri") or "").strip()
        if not text:
            raise AudioPipelineError(f"audio job {job.job_id} has no TTS text")
        if not voice_id:
            raise AudioPipelineError(f"audio job {job.job_id} has no voice_id")
        if not reference_uri:
            raise AudioPipelineError(
                f"audio job {job.job_id} has no approved reference_audio_uri"
            )

        return self.synthesize(
            text=text,
            language_id=job.language,
            voice_id=voice_id,
            reference_audio_base64=reference_audio_base64,
            approval=approval,
        )


__all__ = [
    "PaidExecutionApproval",
    "RunPodChatterboxConfig",
    "RunPodChatterboxConfigurationError",
    "RunPodChatterboxError",
    "RunPodChatterboxProvider",
    "RunPodChatterboxResponseError",
    "RunPodExecutionGateError",
]
