from ahos_quality99.architecture_invariants import run_architecture_invariants


def test_existing_ahos_architecture_boundaries_hold():
    report = run_architecture_invariants()
    assert report.passed is True
    assert report.owner_boundary is True
    assert report.localhost_boundary is True
    assert report.zero_cost_boundary is True
    assert report.durable_queue is True
    assert report.recovery_boundary is True
