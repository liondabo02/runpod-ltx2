import pytest

from ahos.provider_registry import (
    ProviderSelectionError,
    default_media_provider_registry,
)


def test_registry_contains_local_and_runpod():
    registry = default_media_provider_registry()
    ids = {p.provider_id for p in registry.list()}
    assert {"local-comfyui", "runpod-ltx2"}.issubset(ids)


def test_free_local_is_selected_without_paid_external_permission():
    registry = default_media_provider_registry()
    selected = registry.select("video_generation")
    assert selected.provider_id == "local-comfyui"


def test_runpod_can_be_selected_only_when_paid_and_external_allowed():
    registry = default_media_provider_registry()
    selected = registry.select(
        "ltx2",
        allow_paid=True,
        allow_external=True,
        preferred_provider_id="runpod-ltx2",
    )
    assert selected.provider_id == "runpod-ltx2"

    with pytest.raises(ProviderSelectionError):
        registry.select("ltx2")
