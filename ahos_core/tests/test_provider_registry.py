import pytest

from ahos.provider_registry import ProviderSelectionError, default_media_provider_registry


def test_registry_contains_local_runpod_and_research_gateways():
    ids = {p.provider_id for p in default_media_provider_registry().list()}
    assert {"local-comfyui", "runpod-ltx2", "openrouter", "nvidia-nim", "bytez"}.issubset(ids)


def test_external_free_provider_is_not_selected_without_permission():
    registry = default_media_provider_registry()
    with pytest.raises(ProviderSelectionError):
        registry.select("coding")
    assert registry.select("coding", allow_external=True).provider_id == "openrouter"


def test_free_local_is_selected_without_paid_external_permission():
    assert default_media_provider_registry().select("video_generation").provider_id == "local-comfyui"


def test_runpod_can_be_selected_only_when_paid_and_external_allowed():
    registry = default_media_provider_registry()
    selected = registry.select("ltx2", allow_paid=True, allow_external=True,
                               preferred_provider_id="runpod-ltx2")
    assert selected.provider_id == "runpod-ltx2"
    with pytest.raises(ProviderSelectionError):
        registry.select("ltx2")
