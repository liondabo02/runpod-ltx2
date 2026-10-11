from __future__ import annotations

import base64
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Mapping

from .runpod_ltx2 import (
    PaidExecutionApproval,
    RunPodExecutionGateError,
    RunPodResponseError,
    RunPodTransport,
    UrlLibRunPodTransport,
)


class RunPodQwen3VoiceDesignError(RuntimeError):
    pass


class RunPodQwen3VoiceDesignConfigurationError(RunPodQwen3VoiceDesignError):
    pass


class RunPodQwen3VoiceDesignResponseError(RunPodQwen3VoiceDesignError):
    pass


_ENDPOINT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SUPPORTED_DESIGN_LANGUAGES = frozenset(
    {
        "Chinese",
        "English",
        "Japanese",
        "Korean",
        "German",
        "French",
        "Russian",
        "Portuguese",
        "Spanish",
        "Italian",
    }
)


@dataclass(frozen=True, slots=True)
class RunPodQwen3VoiceDesignConfig:
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


class RunPodQwen3VoiceDesignProvider:
    """Guarded AHOS adapter for Qwen3-TTS VoiceDesign on RunPod Serverless.

    This provider creates synthetic reference voices only. It does not bind a
    generated voice to a canonical character and it does not claim Turkish
    VoiceDesign support.
    """

    provider_id = "qwen3-tts-voice-design"
    supported_languages = SUPPORTED_DESIGN_LANGUAGES

    def __init__(
        self,
        config: RunPodQwen3VoiceDesignConfig,
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
            "supported_design_languages": sorted(self.supported_languages),
            "paid": True,
            "external": True,
            "model": "Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            "canonical_binding_created": False,
        }

    def _require_api_key(self) -> str:
        api_key = self.config.api_key()
        if not api_key:
            raise RunPodQwen3VoiceDesignConfigurationError(
                f"{self.config.api_key_env} is not configured"
            )
        return api_key

    @staticmethod
    def design_payload(
        *,
        text: str,
        language: str,
        instruct: str,
        candidate_id: str,
        seed: int = 0,
        max_new_tokens: int = 1024,
    ) -> dict[str, object]:
        text = text.strip()
        language = language.strip()
        instruct = instruct.strip()
        candidate_id = candidate_id.strip()

        if not text:
            raise ValueError("text must not be empty")
        if language not in SUPPORTED_DESIGN_LANGUAGES:
            raise ValueError(f"unsupported VoiceDesign language: {language}")
        if not instruct:
            raise ValueError("instruct must not be empty")
        if not candidate_id:
            raise ValueError("candidate_id must not be empty")
        if seed < 0 or seed > 2_147_483_647:
            raise ValueError("seed out of range")
        if max_new_tokens < 128 or max_new_tokens > 2048:
            raise ValueError("max_new_tokens must be between 128 and 2048")

        return {
            "input": {
                "text": text,
                "language": language,
                "instruct": instruct,
                "candidate_id": candidate_id,
                "seed": int(seed),
                "max_new_tokens": int(max_new_tokens),
            }
        }

    @staticmethod
    def _extract_wav(response: object) -> bytes:
        if not isinstance(response, Mapping):
            raise RunPodQwen3VoiceDesignResponseError(
                "RunPod returned a non-object response"
            )

        status = str(response.get("status", "")).upper()
        if status and status not in {"COMPLETED", "SUCCESS"}:
            raise RunPodQwen3VoiceDesignResponseError(
                f"RunPod Qwen3 VoiceDesign job status is {status}"
            )

        output = response.get("output")
        if not isinstance(output, Mapping):
            raise RunPodQwen3VoiceDesignResponseError(
                "RunPod response has no output object"
            )
        if output.get("ok") is not True:
            raise RunPodQwen3VoiceDesignResponseError(
                f"Qwen3 worker returned failure: {output}"
            )
        if output.get("synthetic_voice") is not True:
            raise RunPodQwen3VoiceDesignResponseError(
                "Qwen3 worker did not mark output as synthetic_voice"
            )
        if output.get("canonical_binding_created") is not False:
            raise RunPodQwen3VoiceDesignResponseError(
                "trial generation must not create canonical binding"
            )

        encoded = output.get("audio_base64")
        if not isinstance(encoded, str) or not encoded:
            raise RunPodQwen3VoiceDesignResponseError(
                "Qwen3 worker returned no audio_base64"
            )

        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise RunPodQwen3VoiceDesignResponseError(
                "Qwen3 worker returned invalid base64 audio"
            ) from exc

        if len(raw) < 44 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
            raise RunPodQwen3VoiceDesignResponseError(
                "Qwen3 worker returned data that is not RIFF/WAVE"
            )
        return raw

    def design(
        self,
        *,
        text: str,
        language: str,
        instruct: str,
        candidate_id: str,
        approval: PaidExecutionApproval,
        seed: int = 0,
        max_new_tokens: int = 1024,
    ) -> bytes:
        approval.require()
        api_key = self._require_api_key()
        payload = self.design_payload(
            text=text,
            language=language,
            instruct=instruct,
            candidate_id=candidate_id,
            seed=seed,
            max_new_tokens=max_new_tokens,
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
            raise RunPodQwen3VoiceDesignResponseError(str(exc)) from exc

        return self._extract_wav(response)


__all__ = [
    "PaidExecutionApproval",
    "RunPodExecutionGateError",
    "RunPodQwen3VoiceDesignConfig",
    "RunPodQwen3VoiceDesignConfigurationError",
    "RunPodQwen3VoiceDesignError",
    "RunPodQwen3VoiceDesignProvider",
    "RunPodQwen3VoiceDesignResponseError",
    "SUPPORTED_DESIGN_LANGUAGES",
]
