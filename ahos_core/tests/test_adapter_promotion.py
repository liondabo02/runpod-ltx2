from ahos.adapter_catalog import AdapterSpec, AdapterTrust
from ahos.adapter_promotion import AdapterPromotionEvidence, AdapterPromotionGate


def _spec():
    return AdapterSpec(
        name="candidate",
        capability="coding",
        trust=AdapterTrust.EXPERIMENTAL,
        free_by_default=True,
        sandbox_required=True,
        network_required=True,
        can_modify_repo=True,
        owner_approval_for_external_action=True,
    )


def _evidence(**overrides):
    values = dict(
        license_ok=True,
        security_scan_ok=True,
        sandbox_smoke_ok=True,
        deterministic_smoke_ok=True,
        terms_reviewed=True,
        version_pinned=True,
        maintenance_ok=True,
        network_scope_reviewed=True,
    )
    values.update(overrides)
    return AdapterPromotionEvidence(**values)


def test_adapter_promotion_requires_all_checks():
    decision = AdapterPromotionGate().evaluate(_spec(), _evidence())
    assert decision.promoted is True
    assert decision.target_trust is AdapterTrust.REVIEWED_OPEN_SOURCE


def test_security_failure_blocks_candidate():
    decision = AdapterPromotionGate().evaluate(_spec(), _evidence(security_scan_ok=False))
    assert decision.promoted is False
    assert decision.target_trust is AdapterTrust.BLOCKED
    assert "security_scan_ok" in decision.blockers


def test_missing_license_keeps_candidate_experimental():
    decision = AdapterPromotionGate().evaluate(_spec(), _evidence(license_ok=False))
    assert decision.promoted is False
    assert decision.target_trust is AdapterTrust.EXPERIMENTAL
