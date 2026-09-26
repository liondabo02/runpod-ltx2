import pytest

from ahos.model_gateway import (
    DataSensitivity, GatewayPolicyError, ModelGateway, ModelRouteRequest,
    ProviderRoutePolicy, default_route_policies,
)


def test_openrouter_free_router_can_be_planned_without_paid_approval():
    plan = ModelGateway().plan(ModelRouteRequest(
        capability="coding", model_id="openrouter/free",
        preferred_provider_id="openrouter", allow_external=True,
    ))
    assert plan.provider_id == "openrouter"
    assert plan.estimated_cost_usd == 0
    assert plan.api_key_env == "OPENROUTER_API_KEY"


def test_unverified_free_model_fails_closed():
    with pytest.raises(GatewayPolicyError, match="verified-free"):
        ModelGateway().plan(ModelRouteRequest(
            capability="coding", model_id="some-paid-model",
            preferred_provider_id="openrouter", allow_external=True,
        ))


def test_external_provider_requires_explicit_permission():
    with pytest.raises(GatewayPolicyError, match="no allowed provider"):
        ModelGateway().plan(ModelRouteRequest(
            capability="coding", model_id="openrouter/free",
            preferred_provider_id="openrouter",
        ))


def test_paid_estimate_requires_owner_approval():
    with pytest.raises(GatewayPolicyError, match="owner approval"):
        ModelGateway().plan(ModelRouteRequest(
            capability="coding", model_id="paid", allow_external=True,
            estimated_cost_usd=0.01,
        ))


def test_confidential_data_is_blocked_for_public_gateway():
    with pytest.raises(GatewayPolicyError, match="sensitivity"):
        ModelGateway().plan(ModelRouteRequest(
            capability="coding", model_id="openrouter/free",
            preferred_provider_id="openrouter", allow_external=True,
            sensitivity=DataSensitivity.CONFIDENTIAL,
        ))


def test_nim_runs_only_after_free_model_is_explicitly_verified():
    policies = dict(default_route_policies())
    policies["nvidia-nim"] = ProviderRoutePolicy(
        provider_id="nvidia-nim", api_key_env="NVIDIA_API_KEY",
        base_url="https://integrate.api.nvidia.com/v1",
        free_model_ids=frozenset({"verified/nim-model"}),
    )
    plan = ModelGateway(policies=policies).plan(ModelRouteRequest(
        capability="vision", model_id="verified/nim-model",
        preferred_provider_id="nvidia-nim", allow_external=True,
    ))
    assert plan.provider_id == "nvidia-nim"


def test_bytez_defaults_to_blocked_until_catalog_is_verified():
    with pytest.raises(GatewayPolicyError, match="verified-free"):
        ModelGateway().plan(ModelRouteRequest(
            capability="segmentation", model_id="unknown/model",
            preferred_provider_id="bytez", allow_external=True,
        ))
