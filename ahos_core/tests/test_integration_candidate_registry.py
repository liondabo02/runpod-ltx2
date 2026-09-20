from ahos.integration_candidate_registry import IntegrationStatus, default_integration_candidate_registry


def test_only_isolated_zero_software_cost_candidates_enter_sandbox_queue():
    eligible = {item.candidate_id for item in default_integration_candidate_registry().sandbox_eligible()}
    assert eligible == {"agent-reach-public", "deer-flow-2", "remotion-local"}


def test_agent_reach_profile_forbids_credentials_cookies_and_production():
    candidate = default_integration_candidate_registry().get("agent-reach-public")
    assert candidate is not None
    assert candidate.credentials_allowed is False
    assert candidate.browser_cookies_allowed is False
    assert candidate.production_allowed is False


def test_paid_or_compute_bound_models_fail_closed():
    registry = default_integration_candidate_registry()
    assert registry.get("lyria-3.5").status is IntegrationStatus.BLOCKED_PAID
    for candidate_id in ("deepseek-v4", "longcat-video", "longcat-video-avatar-1.5", "ltx-2.5"):
        candidate = registry.get(candidate_id)
        assert candidate.status is IntegrationStatus.BLOCKED_COMPUTE
        assert candidate.production_allowed is False


def test_unverified_longcat_language_model_is_not_sandbox_eligible():
    registry = default_integration_candidate_registry()
    assert registry.get("longcat-2").status is IntegrationStatus.NEEDS_VERIFICATION
    assert "longcat-2" not in {item.candidate_id for item in registry.sandbox_eligible()}


def test_remotion_is_local_compositor_not_hosted_free_generation():
    candidate = default_integration_candidate_registry().get("remotion-local")
    assert candidate is not None
    assert candidate.kind == "video_compositor"
    assert candidate.local_compute_required is True
    assert candidate.hosted_api_free is False
    assert candidate.production_allowed is False
    assert "episode_assembly" in candidate.capabilities
