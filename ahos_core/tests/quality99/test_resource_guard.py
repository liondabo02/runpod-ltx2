from ahos_quality99.resource_guard import ResourceGuard


def test_resource_guard_blocks_critical_memory():
    decision = ResourceGuard().evaluate(total_memory_kb=16_000_000, free_memory_kb=500_000)
    assert decision.allow_heavy_work is False
    assert decision.state == "critical"


def test_resource_guard_allows_healthy_memory():
    decision = ResourceGuard().evaluate(total_memory_kb=16_000_000, free_memory_kb=4_000_000)
    assert decision.allow_heavy_work is True
