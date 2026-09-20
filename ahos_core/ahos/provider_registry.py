from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


class ProviderSelectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MediaProviderDescriptor:
    provider_id: str
    name: str
    capabilities: frozenset[str]
    paid: bool
    external: bool
    priority: int
    notes: str = ""
    free_tier: bool = False
    requires_api_key: bool = False
    supports_local_deployment: bool = False

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.capabilities:
            raise ValueError("capabilities must not be empty")


class MediaProviderRegistry:
    """Provider catalog that keeps AHOS independent from a single backend."""

    def __init__(self, providers: Iterable[MediaProviderDescriptor] = ()) -> None:
        self._providers: dict[str, MediaProviderDescriptor] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: MediaProviderDescriptor) -> None:
        if provider.provider_id in self._providers:
            raise ValueError(f"duplicate provider_id: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> MediaProviderDescriptor | None:
        return self._providers.get(provider_id)

    def list(self) -> tuple[MediaProviderDescriptor, ...]:
        return tuple(sorted(self._providers.values(), key=lambda p: (p.priority, p.provider_id)))

    def select(self, capability: str, *, allow_paid: bool = False,
               allow_external: bool = False,
               preferred_provider_id: str | None = None) -> MediaProviderDescriptor:
        candidates = [p for p in self._providers.values()
                      if capability in p.capabilities
                      and (allow_paid or not p.paid)
                      and (allow_external or not p.external)]
        if preferred_provider_id:
            preferred = next((p for p in candidates if p.provider_id == preferred_provider_id), None)
            if preferred is not None:
                return preferred
        if not candidates:
            raise ProviderSelectionError(f"no allowed provider for capability={capability!r}")
        return sorted(candidates, key=lambda p: (p.priority, p.provider_id))[0]


def default_media_provider_registry() -> MediaProviderRegistry:
    general_ai = frozenset({"chat", "reasoning", "coding", "translation", "multimodal"})
    return MediaProviderRegistry((
        MediaProviderDescriptor(
            provider_id="local-comfyui", name="Local ComfyUI",
            capabilities=frozenset({"image_generation", "video_generation", "image_to_video", "comfyui_workflow"}),
            paid=False, external=False, priority=100,
            notes="Local adapter. Useful when a capable local GPU exists.",
            supports_local_deployment=True,
        ),
        MediaProviderDescriptor(
            provider_id="openrouter", name="OpenRouter",
            capabilities=general_ai, paid=False, external=True, priority=40,
            notes="Free models only by default; paid routes require owner approval.",
            free_tier=True, requires_api_key=True,
        ),
        MediaProviderDescriptor(
            provider_id="nvidia-nim", name="NVIDIA NIM",
            capabilities=general_ai | frozenset({"speech_to_text", "text_to_speech", "embeddings", "reranking", "vision"}),
            paid=False, external=True, priority=50,
            notes="Hosted free inference is evaluation-only; production/self-hosting has separate licensing and cost gates.",
            free_tier=True, requires_api_key=True, supports_local_deployment=True,
        ),
        MediaProviderDescriptor(
            provider_id="bytez", name="Bytez",
            capabilities=general_ai | frozenset({"image_generation", "video_generation", "text_to_speech", "speech_to_text", "classification", "segmentation"}),
            paid=False, external=True, priority=60,
            notes="Experimental catalog provider; only explicitly verified free models may run.",
            free_tier=True, requires_api_key=True, supports_local_deployment=True,
        ),
        MediaProviderDescriptor(
            provider_id="runpod-ltx2", name="RunPod Serverless LTX-2",
            capabilities=frozenset({"video_generation", "image_to_video", "ltx2", "gpu_render"}),
            paid=True, external=True, priority=20,
            notes="Remote GPU provider. Requires explicit owner approval and execution enablement before paid execution.",
            requires_api_key=True,
        ),
    ))
