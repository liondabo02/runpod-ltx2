from __future__ import annotations

import base64
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Mapping

from .runpod_ltx2 import (
    PaidExecutionApproval,
    RunPodResponseError,
    RunPodTransport,
    UrlLibRunPodTransport,
)


class RunPodOpenVoiceError(RuntimeError):
    pass


class RunPodOpenVoiceConfigurationError(RunPodOpenVoiceError):
    pass


class RunPodOpenVoiceResponseError(RunPodOpenVoiceError):
    pass


_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _wav(value: bytes, label: str) -> None:
    if len(value) < 44 or value[:4] != b"RIFF" or value[8:12] != b"WAVE":
        raise ValueError(f"{label} must be RIFF/WAVE audio")


@dataclass(frozen=True, slots=True)
class RunPodOpenVoiceConfig:
    endpoint_id: str
    base_url: str = "https://api.runpod.ai/v2"
    api_key_env: str = "RUNPOD_API_KEY"
    request_timeout_seconds: float = 900.0

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


class RunPodOpenVoiceProvider:
    """Tone-colour conversion only; source pronunciation remains untouched."""

    provider_id = "openvoice-v2-tone-transfer"

    def __init__(self, config: RunPodOpenVoiceConfig, *, transport: RunPodTransport | None = None) -> None:
        self.config = config
        self.transport = transport or UrlLibRunPodTransport()

    def configuration_summary(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "endpoint_id": self.config.endpoint_id,
            "api_key_env": self.config.api_key_env,
            "api_key_present": bool(self.config.api_key()),
            "mode": "speech-to-speech-tone-colour-conversion",
            "commercial_license_review": "MIT upstream; deployed image SBOM still required",
        }

    @staticmethod
    def conversion_payload(
        *, source_audio: bytes, target_reference_audio: bytes, character_id: str,
        language: str = "ku-latn", tau: float = 0.3,
    ) -> dict[str, object]:
        _wav(source_audio, "source_audio")
        _wav(target_reference_audio, "target_reference_audio")
        character_id = character_id.strip()
        if not character_id:
            raise ValueError("character_id must not be empty")
        if language != "ku-latn":
            raise ValueError("this identity bridge is restricted to ku-latn")
        if not 0.0 <= tau <= 1.0:
            raise ValueError("tau must be between 0 and 1")
        return {"input": {
            "operation": "tone_color_convert",
            "source_audio_base64": base64.b64encode(source_audio).decode("ascii"),
            "target_reference_audio_base64": base64.b64encode(target_reference_audio).decode("ascii"),
            "character_id": character_id,
            "language": language,
            "tau": float(tau),
            "preserve_source_linguistics": True,
        }}

    def convert(
        self, *, source_audio: bytes, target_reference_audio: bytes,
        character_id: str, approval: PaidExecutionApproval, tau: float = 0.3,
    ) -> bytes:
        approval.require()
        api_key = self.config.api_key()
        if not api_key:
            raise RunPodOpenVoiceConfigurationError(
                f"{self.config.api_key_env} is not configured"
            )
        payload = self.conversion_payload(
            source_audio=source_audio,
            target_reference_audio=target_reference_audio,
            character_id=character_id,
            tau=tau,
        )
        try:
            response = self.transport.request_json(
                "POST", self.config.endpoint_base + "/runsync", api_key=api_key,
                payload=payload, timeout=self.config.request_timeout_seconds,
            )
        except RunPodResponseError as exc:
            raise RunPodOpenVoiceResponseError(str(exc)) from exc
        return self._extract(response)

    @staticmethod
    def _extract(response: object) -> bytes:
        if not isinstance(response, Mapping):
            raise RunPodOpenVoiceResponseError("RunPod returned a non-object response")
        status = str(response.get("status", "")).upper()
        if status and status not in {"COMPLETED", "SUCCESS"}:
            raise RunPodOpenVoiceResponseError(f"OpenVoice job status is {status}")
        output = response.get("output")
        if not isinstance(output, Mapping) or output.get("ok") is not True:
            raise RunPodOpenVoiceResponseError("OpenVoice worker returned failure")
        if output.get("identity_transfer") is not True or output.get("source_linguistics_preserved") is not True:
            raise RunPodOpenVoiceResponseError("worker omitted identity-transfer evidence")
        encoded = output.get("audio_base64")
        if not isinstance(encoded, str) or not encoded:
            raise RunPodOpenVoiceResponseError("worker returned no audio")
        try:
            audio = base64.b64decode(encoded, validate=True)
            _wav(audio, "converted audio")
        except (ValueError, TypeError) as exc:
            raise RunPodOpenVoiceResponseError(str(exc)) from exc
        return audio


__all__ = [
    "RunPodOpenVoiceConfig", "RunPodOpenVoiceConfigurationError",
    "RunPodOpenVoiceError", "RunPodOpenVoiceProvider", "RunPodOpenVoiceResponseError",
]
