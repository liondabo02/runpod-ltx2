from ahos_quality99.model_routing import ModelEndpoint, ZeroCostSeparationRouter


def test_zero_cost_router_separates_builder_and_reviewer():
    decision = ZeroCostSeparationRouter().select((
        ModelEndpoint("local-builder", "builder", 0.0),
        ModelEndpoint("free-reviewer", "reviewer", 0.0),
        ModelEndpoint("paid-provider", "both", 0.1),
    ))
    assert decision.allowed is True
    assert decision.builder != decision.reviewer
    assert "paid-provider" not in {decision.builder, decision.reviewer}


def test_router_fails_when_only_one_zero_cost_model_exists():
    decision = ZeroCostSeparationRouter().select((
        ModelEndpoint("only", "both", 0.0),
    ))
    assert decision.allowed is False
    assert "builder_reviewer_not_separated" in decision.blockers or "zero_cost_reviewer_unavailable" in decision.blockers
