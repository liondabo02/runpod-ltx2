from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ahos import (
    ActionRequest,
    AuthorityLevel,
    InertMediaCapabilityAdapter,
    MediaAuthorizationStatus,
    MediaCapabilityAdapter,
    MediaExecutionStatus,
    MediaRequest,
)


def _request(
    *, authority: AuthorityLevel = AuthorityLevel.B, external_side_effect: bool = False
) -> MediaRequest:
    return MediaRequest(
        request_id="media-1",
        capability="media.create_draft",
        action=ActionRequest(
            name="create local media draft",
            authority=authority,
            external_side_effect=external_side_effect,
        ),
        parameters={"prompt": "a quiet sunrise"},
    )


def test_media_request_is_immutable_and_parameters_are_local() -> None:
    parameters = {"prompt": "a quiet sunrise"}
    request = MediaRequest(
        "media-1",
        "media.create_draft",
        ActionRequest("create draft", AuthorityLevel.B),
        parameters,
    )
    parameters["prompt"] = "changed"

    assert request.parameters["prompt"] == "a quiet sunrise"
    with pytest.raises(TypeError):
        request.parameters["new"] = "value"
    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"


def test_authority_a_and_b_are_authorized_without_owner_approval() -> None:
    adapter = InertMediaCapabilityAdapter()

    for authority in (AuthorityLevel.A, AuthorityLevel.B):
        authorization = adapter.authorize(_request(authority=authority))

        assert authorization.status is MediaAuthorizationStatus.AUTHORIZED
        assert authorization.allowed is True
        assert authorization.governance_reasons == ()


def test_external_or_c_authority_remains_owner_approval_gated() -> None:
    adapter = InertMediaCapabilityAdapter()

    for request in (
        _request(external_side_effect=True),
        _request(authority=AuthorityLevel.C),
    ):
        result = adapter.execute(request)

        assert result.status is MediaExecutionStatus.REJECTED
        assert result.authorization.status is MediaAuthorizationStatus.OWNER_APPROVAL_REQUIRED
        assert result.authorization.allowed is False
        assert result.authorization.governance_reasons


def test_inert_adapter_never_executes_authorized_request() -> None:
    adapter = InertMediaCapabilityAdapter()
    result = adapter.execute(_request())

    assert isinstance(adapter, MediaCapabilityAdapter)
    assert result.request_id == "media-1"
    assert result.status is MediaExecutionStatus.NOT_EXECUTED
    assert result.authorization.status is MediaAuthorizationStatus.AUTHORIZED
    assert result.output_ref is None
    assert "does not execute" in result.message
