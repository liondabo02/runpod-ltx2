from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol

from .audio_pipeline import AudioJob, AudioPipelineError, AudioTaskType
from .runpod_ltx2 import PaidExecutionApproval, RunPodExecutionGateError


class RunPodKokoroError(RuntimeError):
    pass


class RunPodKokoroConfigurationError(RunPodKokoroError):
    pass


class RunPodKokoroResponseError(RunPodKokoroError):
    pass


_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_KOKORO_VOICE_RE = re.compile(
    r"^(?:[abefhijpz][fm]_[A-Za-z0-9_-]+|"
    r"alloy|echo|fable|onyx|nova|shimmer|ash|coral|sage|verse)$"
)
_ALLOWED_FORMATS = frozenset({"mp3", "opus", "aac", "flac", "wav", "pcm"})


@dataclass(frozen=True, slots=True)
class RunPodKokoroConfig:
    endpoint_id: str
    api_key_env: str = "RUNPOD_API_KEY"
    request_timeout_seconds: float = 330.0

    def __post_init__(self) -> None:
        if not _ENDPOINT_RE.fullmatch(self.endpoint_id):
            raise ValueError("invalid RunPod endpoint_id")
        if not self.api_key_env.strip():
            raise ValueError("api_key_env must not be empty")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")

    @property
    def endpoint_base(self) -> str:
        return f"https://{self.endpoint_id}.api.runpod.ai"

    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()

    def configured(self) -> bool:
        return bool(self.endpoint_id and self.api_key())


@dataclass(frozen=True, slots=True)
class BinaryHttpResponse:
    status_code: int
    content_type: str
    body: bytes


class RunPodBinaryTransport(Protocol):
    def request_bytes(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object] | None = None,
        timeout: float = 330.0,
    ) -> BinaryHttpResponse:
        ...


class UrlLibRunPodBinaryTransport:
    def request_bytes(
        self,
        method: str,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object] | None = None,
        timeout: float = 330.0,
    ) -> BinaryHttpResponse:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "*/*",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return BinaryHttpResponse(
                    status_code=int(response.status),
                    content_type=response.headers.get("Content-Type", ""),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise RunPodKokoroResponseError(
                f"RunPod Kokoro HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise RunPodKokoroResponseError(str(exc)) from exc


class RunPodKokoroProvider:
    """Guarded RunPod Load Balancer adapter for the proven Kokoro TTS endpoint.

    The RunPod API key is read from the environment and never serialized.
    Paid execution requires the same owner/execution/provider triple gate used
    by the LTX-2 adapter.
    """

    provider_id = "runpod-kokoro"
    supported_languages = frozenset({"en"})

    def __init__(
        self,
        config: RunPodKokoroConfig,
        *,
        transport: RunPodBinaryTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport or UrlLibRunPodBinaryTransport()

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
        }

    @staticmethod
    def speech_payload(
        *,
        text: str,
        voice_id: str,
        response_format: str = "wav",
        speed: float = 1.0,
        model: str = "tts-1",
    ) -> dict[str, object]:
        clean_text = text.strip()
        clean_voice = voice_id.strip()
        fmt = response_format.strip().lower()

        if not clean_text:
            raise ValueError("text must not be empty")
        if not _KOKORO_VOICE_RE.fullmatch(clean_voice):
            raise ValueError(
                "voice_id must be a native Kokoro voice ID or supported OpenAI alias"
            )
        if fmt not in _ALLOWED_FORMATS:
            raise ValueError(f"unsupported response_format: {fmt}")
        if not 0.25 <= float(speed) <= 4.0:
            raise ValueError("speed must be between 0.25 and 4.0")
        if not model.strip():
            raise ValueError("model must not be empty")

        return {
            "model": model,
            "input": clean_text,
            "voice": clean_voice,
            "response_format": fmt,
            "speed": float(speed),
        }

    def _require_api_key(self) -> str:
        api_key = self.config.api_key()
        if not api_key:
            raise RunPodKokoroConfigurationError(
                f"{self.config.api_key_env} is not configured"
            )
        return api_key

    @staticmethod
    def _validate_wav(body: bytes) -> None:
        if len(body) < 12 or body[:4] != b"RIFF" or body[8:12] != b"WAVE":
            raise RunPodKokoroResponseError(
                "Kokoro returned HTTP 200 but body is not a RIFF/WAVE file"
            )

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        approval: PaidExecutionApproval,
        response_format: str = "wav",
        speed: float = 1.0,
        model: str = "tts-1",
    ) -> BinaryHttpResponse:
        approval.require()
        api_key = self._require_api_key()
        payload = self.speech_payload(
            text=text,
            voice_id=voice_id,
            response_format=response_format,
            speed=speed,
            model=model,
        )
        response = self.transport.request_bytes(
            "POST",
            self.config.endpoint_base + "/v1/audio/speech",
            api_key=api_key,
            payload=payload,
            timeout=self.config.request_timeout_seconds,
        )
        if response.status_code != 200:
            raise RunPodKokoroResponseError(
                f"Kokoro returned unexpected HTTP status {response.status_code}"
            )
        if not response.body:
            raise RunPodKokoroResponseError("Kokoro returned an empty audio body")
        if response_format.lower() == "wav":
            self._validate_wav(response.body)
        return response

    def synthesize_job(
        self,
        job: AudioJob,
        *,
        voice_id: str,
        approval: PaidExecutionApproval,
        response_format: str = "wav",
        speed: float = 1.0,
    ) -> BinaryHttpResponse:
        if job.task_type not in {
            AudioTaskType.DIALOGUE_TTS,
            AudioTaskType.NARRATION_TTS,
        }:
            raise AudioPipelineError(
                f"audio job {job.job_id} is not a TTS job"
            )
        if job.provider_id != self.provider_id:
            raise AudioPipelineError(
                f"audio job {job.job_id} is assigned to {job.provider_id!r}, "
                f"not {self.provider_id!r}"
            )
        if job.language not in self.supported_languages:
            raise AudioPipelineError(
                f"RunPod Kokoro does not support production language {job.language!r}"
            )

        text = str(job.payload.get("text", "")).strip()
        if not text:
            raise AudioPipelineError(f"audio job {job.job_id} has no TTS text")

        return self.synthesize(
            text=text,
            voice_id=voice_id,
            approval=approval,
            response_format=response_format,
            speed=speed,
        )


__all__ = [
    "BinaryHttpResponse",
    "RunPodKokoroConfig",
    "RunPodKokoroConfigurationError",
    "RunPodKokoroError",
    "RunPodKokoroProvider",
    "RunPodKokoroResponseError",
    "RunPodBinaryTransport",
    "UrlLibRunPodBinaryTransport",
    "PaidExecutionApproval",
    "RunPodExecutionGateError",
]
