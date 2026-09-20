from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .provider_registry import MediaProviderRegistry, ProviderSelectionError, default_media_provider_registry


class GatewayPolicyError(RuntimeError):
    pass


class DataSensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True, slots=True)
class ProviderRoutePolicy:
    provider_id: str
    api_key_env: str
    base_url: str
    free_model_ids: frozenset[str] = frozenset()
    free_model_suffixes: tuple[str, ...] = ()
    maximum_sensitivity: DataSensitivity = DataSensitivity.INTERNAL

    def is_verified_free(self, model_id: str) -> bool:
        return model_id in self.free_model_ids or any(model_id.endswith(s) for s in self.free_model_suffixes)


@dataclass(frozen=True, slots=True)
class ModelRouteRequest:
    capability: str
    model_id: str
    sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    preferred_provider_id: str | None = None
    allow_external: bool = False
    owner_approved_paid: bool = False
    estimated_cost_usd: float = 0.0


@dataclass(frozen=True, slots=True)
class ModelRoutePlan:
    provider_id: str
    model_id: str
    base_url: str
    api_key_env: str
    estimated_cost_usd: float
    external: bool


_SENSITIVITY_RANK = {
    DataSensitivity.PUBLIC: 0,
    DataSensitivity.INTERNAL: 1,
    DataSensitivity.CONFIDENTIAL: 2,
    DataSensitivity.RESTRICTED: 3,
}


def default_route_policies() -> Mapping[str, ProviderRoutePolicy]:
    return MappingProxyType({
        "openrouter": ProviderRoutePolicy(
            provider_id="openrouter", api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
            free_model_ids=frozenset({"openrouter/free"}), free_model_suffixes=(":free",),
        ),
        "nvidia-nim": ProviderRoutePolicy(
            provider_id="nvidia-nim", api_key_env="NVIDIA_API_KEY",
            base_url="https://integrate.api.nvidia.com/v1",
        ),
        "bytez": ProviderRoutePolicy(
            provider_id="bytez", api_key_env="BYTEZ_API_KEY",
            base_url="https://api.bytez.com",
        ),
    })


@dataclass(slots=True)
class ModelGateway:
    registry: MediaProviderRegistry = field(default_factory=default_media_provider_registry)
    policies: Mapping[str, ProviderRoutePolicy] = field(default_factory=default_route_policies)

    def plan(self, request: ModelRouteRequest) -> ModelRoutePlan:
        if request.estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd must be >= 0")
        if request.estimated_cost_usd > 0 and not request.owner_approved_paid:
            raise GatewayPolicyError("paid route requires explicit owner approval")

        try:
            provider = self.registry.select(
                request.capability,
                allow_paid=request.owner_approved_paid,
                allow_external=request.allow_external,
                preferred_provider_id=request.preferred_provider_id,
            )
        except ProviderSelectionError as exc:
            raise GatewayPolicyError(str(exc)) from exc

        policy = self.policies.get(provider.provider_id)
        if policy is None:
            raise GatewayPolicyError(f"provider {provider.provider_id!r} has no route policy")
        if _SENSITIVITY_RANK[request.sensitivity] > _SENSITIVITY_RANK[policy.maximum_sensitivity]:
            raise GatewayPolicyError("data sensitivity exceeds provider policy")
        if request.estimated_cost_usd == 0 and not policy.is_verified_free(request.model_id):
            raise GatewayPolicyError("model is not on the verified-free allowlist")

        return ModelRoutePlan(
            provider_id=provider.provider_id, model_id=request.model_id,
            base_url=policy.base_url, api_key_env=policy.api_key_env,
            estimated_cost_usd=request.estimated_cost_usd, external=provider.external,
        )
