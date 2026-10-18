import pytest

from ahos.adapter_catalog import AdapterCatalog, AdapterSpec, AdapterTrust, default_catalog


def test_default_catalog_keeps_experimental_tools_out_of_execution():
    catalog = default_catalog()
    assert catalog.execution_eligible("codex") is True
    assert catalog.execution_eligible("openhands") is True
    assert catalog.execution_eligible("antigravity") is False
    assert catalog.execution_eligible("deepseek-harness") is False


def test_catalog_does_not_grant_execution_by_registration():
    catalog = AdapterCatalog()
    catalog.register(AdapterSpec(
        name="new-tool",
        capability="coding",
        trust=AdapterTrust.EXPERIMENTAL,
        free_by_default=True,
        sandbox_required=True,
        network_required=True,
        can_modify_repo=True,
        owner_approval_for_external_action=True,
    ))
    assert catalog.execution_eligible("new-tool") is False


def test_blocked_adapter_cannot_receive_repo_authority():
    catalog = AdapterCatalog()
    with pytest.raises(ValueError):
        catalog.register(AdapterSpec(
            name="blocked",
            capability="coding",
            trust=AdapterTrust.BLOCKED,
            free_by_default=True,
            sandbox_required=True,
            network_required=False,
            can_modify_repo=True,
            owner_approval_for_external_action=True,
        ))
