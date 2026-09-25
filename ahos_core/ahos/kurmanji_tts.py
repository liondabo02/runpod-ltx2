from __future__ import annotations

import json
import os
import struct
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

class KurmanjiTTSError(RuntimeError):
    """Base error for the Kurmanji speech provider boundary."""


class KurmanjiTTSConfigurationError(KurmanjiTTSError):
    pass


class KurmanjiTTSResponseError(KurmanjiTTSError):
    pass


class KurmanjiTTSUsageError(KurmanjiTTSError):
    pass


class UsageIntent(str, Enum):
    TEST = "test"
    INTERNAL_EVALUATION = "internal_evaluation"
    COMMERCIAL_PUBLISHING = "commercial_publishing"


@dataclass(frozen=True, slots=True)
class KurdishTTSExecutionApproval:
    owner_approved: bool = False
    execution_enabled: bool = False
    external_provider_enabled: bool = False
    paid_provider_enabled: bool = False

    def require(self) -> None:
        missing = [
            name
            for name, enabled in (
                ("owner_approved", self.owner_approved),
                ("execution_enabled", self.execution_enabled),
                ("external_provider_enabled", self.external_provider_enabled),
                ("paid_provider_enabled", self.paid_provider_enabled),
            )
            if not enabled
        ]
        if missing:
            raise KurmanjiTTSUsageError(
                "KurdishTTS external paid execution blocked: " + ", ".join(missing)
            )


@dataclass(frozen=True, slots=True)
class KurmanjiProviderDescriptor:
    provider_id: str
    model_id: str
    paid: bool
    external: bool
    commercial_publishing_allowed: bool
    license_review_required: bool

    def require_usage(self, intent: UsageIntent) -> None:
        if intent is UsageIntent.COMMERCIAL_PUBLISHING and not self.commercial_publishing_allowed:
            raise KurmanjiTTSUsageError(
                f"provider {self.provider_id!r} is evaluation-only and cannot be "
                "selected for commercial publishing"
            )


MMS_KURMANJI = KurmanjiProviderDescriptor(
    provider_id="meta-mms-kmr-evaluation",
    model_id="facebook/mms-tts-kmr-script_latin",
    paid=False,
    external=False,
    commercial_publishing_allowed=False,
    # Distribution and deployment must complete a current model/card license review.
    license_review_required=True,
)

KURDISH_TTS_PROFESSIONAL = KurmanjiProviderDescriptor(
    provider_id="kurdish-tts-professional",
    model_id="provider-managed-kurmanji",
    paid=True,
    external=True,
    commercial_publishing_allowed=True,
    license_review_required=False,
)


@dataclass(frozen=True, slots=True)
class KurdishTTSConfig:
    base_url: str = "https://www.kurdishtts.com"
    api_key_env: str = "KURDISH_TTS_API_KEY"
    request_timeout_seconds: float = 120.0
    synthesize_path: str = "/api/tts-proxy"

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("KurdishTTS base_url must be an absolute HTTPS URL")
        if parsed.hostname.lower() != "www.kurdishtts.com":
            raise ValueError("KurdishTTS base_url host must be www.kurdishtts.com")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("KurdishTTS base_url must not contain credentials, query or fragment")
        if not self.api_key_env.strip():
            raise ValueError("api_key_env must not be empty")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if not self.synthesize_path.startswith("/") or ".." in self.synthesize_path:
            raise ValueError("synthesize_path must be an absolute safe path")

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + self.synthesize_path

    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "").strip()


@dataclass(frozen=True, slots=True)
class TTSHttpResponse:
    status_code: int
    content_type: str
    body: bytes


class KurdishTTSTransport(Protocol):
    def synthesize(
        self,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object],
        timeout: float,
    ) -> TTSHttpResponse: ...


class UrlLibKurdishTTSTransport:
    def synthesize(
        self,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object],
        timeout: float,
    ) -> TTSHttpResponse:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "Accept": "audio/wav",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return TTSHttpResponse(
                    status_code=int(response.status),
                    content_type=response.headers.get("Content-Type", ""),
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise KurmanjiTTSResponseError(f"KurdishTTS HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise KurmanjiTTSResponseError(f"KurdishTTS request failed: {exc}") from exc


def validate_pcm_wav(body: bytes) -> dict[str, int]:
    """Validate a finite PCM RIFF/WAVE and return safe audio metadata."""
    if len(body) < 44 or body[:4] != b"RIFF" or body[8:12] != b"WAVE":
        raise KurmanjiTTSResponseError("response is not a RIFF/WAVE file")
    declared_size = struct.unpack_from("<I", body, 4)[0] + 8
    if declared_size != len(body):
        raise KurmanjiTTSResponseError("WAV RIFF size does not match response length")

    offset = 12
    fmt: tuple[int, int, int, int] | None = None
    data_size: int | None = None
    while offset + 8 <= len(body):
        chunk_id = body[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", body, offset + 4)[0]
        start = offset + 8
        end = start + chunk_size
        if end > len(body):
            raise KurmanjiTTSResponseError("WAV contains a truncated chunk")
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise KurmanjiTTSResponseError("WAV fmt chunk is too short")
            audio_format, channels, sample_rate, _, _, bits = struct.unpack_from("<HHIIHH", body, start)
            fmt = (audio_format, channels, sample_rate, bits)
        elif chunk_id == b"data":
            data_size = chunk_size
        offset = end + (chunk_size & 1)

    if fmt is None or data_size is None or data_size == 0:
        raise KurmanjiTTSResponseError("WAV must contain non-empty fmt and data chunks")
    audio_format, channels, sample_rate, bits = fmt
    if audio_format != 1:
        raise KurmanjiTTSResponseError("only uncompressed PCM WAV is accepted")
    if channels not in {1, 2} or not 8_000 <= sample_rate <= 96_000 or bits not in {16, 24, 32}:
        raise KurmanjiTTSResponseError("WAV audio parameters are outside production policy")
    return {"channels": channels, "sample_rate": sample_rate, "bits_per_sample": bits, "data_bytes": data_size}


class KurdishTTSProvider:
    provider_id = KURDISH_TTS_PROFESSIONAL.provider_id
    language = "kmr"

    def __init__(self, config: KurdishTTSConfig, *, transport: KurdishTTSTransport | None = None) -> None:
        self.config = config
        self.transport = transport or UrlLibKurdishTTSTransport()

    def configuration_summary(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "language": self.language,
            "endpoint": self.config.endpoint,
            "api_key_env": self.config.api_key_env,
            "api_key_present": bool(self.config.api_key()),
            "paid": True,
            "external": True,
            "commercial_publishing_allowed": True,
        }

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str,
        approval: KurdishTTSExecutionApproval,
        intent: UsageIntent = UsageIntent.COMMERCIAL_PUBLISHING,
    ) -> TTSHttpResponse:
        KURDISH_TTS_PROFESSIONAL.require_usage(intent)
        approval.require()
        api_key = self.config.api_key()
        if not api_key:
            raise KurmanjiTTSConfigurationError(f"{self.config.api_key_env} is not configured")
        clean_text, clean_voice = text.strip(), voice_id.strip()
        if not clean_text or len(clean_text) > 5_000:
            raise ValueError("text must contain 1..5000 characters")
        if (
            not clean_voice.startswith("kurmanji_")
            or len(clean_voice) > 128
            or any(c in clean_voice for c in "\r\n\0")
        ):
            raise ValueError("voice_id must be a Kurmanji speaker_id")
        response = self.transport.synthesize(
            self.config.endpoint,
            api_key=api_key,
            payload={
                "text": clean_text,
                "speaker_id": clean_voice,
                "model_version": "v5",
            },
            timeout=self.config.request_timeout_seconds,
        )
        if response.status_code != 200:
            raise KurmanjiTTSResponseError(f"KurdishTTS returned HTTP {response.status_code}")
        if response.content_type.split(";", 1)[0].strip().lower() not in {"audio/wav", "audio/x-wav", "application/octet-stream"}:
            raise KurmanjiTTSResponseError(f"unexpected KurdishTTS content type: {response.content_type!r}")
        validate_pcm_wav(response.body)
        return response


def select_kurmanji_provider(provider_id: str, *, intent: UsageIntent) -> KurmanjiProviderDescriptor:
    providers = {item.provider_id: item for item in (MMS_KURMANJI, KURDISH_TTS_PROFESSIONAL)}
    try:
        provider = providers[provider_id]
    except KeyError as exc:
        raise KurmanjiTTSUsageError(f"unknown Kurmanji TTS provider: {provider_id!r}") from exc
    provider.require_usage(intent)
    return provider


__all__ = [
    "KURDISH_TTS_PROFESSIONAL", "MMS_KURMANJI", "KurdishTTSConfig", "KurdishTTSExecutionApproval", "KurdishTTSProvider",
    "KurmanjiTTSConfigurationError", "KurmanjiTTSResponseError", "KurmanjiTTSUsageError",
    "TTSHttpResponse", "UsageIntent", "select_kurmanji_provider", "validate_pcm_wav",
]
