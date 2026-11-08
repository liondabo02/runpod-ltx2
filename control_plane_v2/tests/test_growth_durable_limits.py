from concurrent.futures import ThreadPoolExecutor
from ahos.growth_budget import GrowthBudget
from ahos.growth_loop import GrowthLoop
from ahos.owner_console import build_default_console


def test_restart_does_not_reset_limit(tmp_path):
    path = tmp_path / 'budget.db'
    for index in range(8):
        assert GrowthBudget(path).reserve('software', str(index), now=100000)[0]
    assert GrowthBudget(path).reserve('software', 'ninth', now=100001)[0] is None
    assert GrowthBudget(path).reserve('software', 'later', now=200000)[0]


def test_same_goal_concurrent_claim_once(tmp_path):
    path = tmp_path / 'budget.db'
    GrowthBudget(path)
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: GrowthBudget(path).reserve('software', 'same goal', now=100000)[0], range(12)))
    assert sum(ident is not None for ident in results) == 1


def test_failed_or_crashed_attempt_still_consumes_reservation(tmp_path):
    budget = GrowthBudget(tmp_path / 'budget.db')
    ident, _ = budget.reserve('software', 'goal', now=100000)
    budget.finish(ident, 'failed')
    assert budget.reserve('software', 'goal', now=100001)[0] is None
    assert budget.reserve('software', 'goal', now=103601)[0]


def test_growth_loop_budget_survives_new_instance(tmp_path):
    console = build_default_console(tmp_path / 'holding')
    for index in range(8):
        GrowthBudget(console.runtime_dir / 'growth-budget.sqlite3').reserve('test', str(index))
    before = len(console.queue.list())
    loop = GrowthLoop(console)
    assert loop.run_once() == []
    assert len(console.queue.list()) == before
    assert loop.status()['automatic_task_limit_24h'] == 8
    assert loop.status()['last_throttle']


def test_stop_marker_prevents_direct_tick(tmp_path):
    console = build_default_console(tmp_path / 'holding')
    marker = tmp_path / 'stop'
    marker.write_text('stop')
    assert GrowthLoop(console, stop_file=marker).run_once() == []
    assert not console.queue.list()
