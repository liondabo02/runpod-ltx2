import json
from types import SimpleNamespace

from miniverse import openhands_builder as module
from miniverse.config import Settings


def test_builder_passes_configured_step_limit_without_model_call(tmp_path, monkeypatch):
    seen = {}
    finish = module.FinishAction(message=json.dumps(dict(
        change_summary='local fixture', tests_run=['offline check'], changed_files=[],
        rollback='none', remaining_risks=[])))
    class Conversation:
        def __init__(self, **kwargs):
            seen.update(kwargs)
            self.state = SimpleNamespace(events=[SimpleNamespace(action=finish)])
            self.conversation_stats = SimpleNamespace(get_combined_metrics=lambda: SimpleNamespace(accumulated_cost=0))
        def send_message(self, message):
            seen['prompt'] = message
        def run(self):
            pass
    monkeypatch.setattr(module, 'LLM', lambda **kwargs: object())
    monkeypatch.setattr(module, 'Agent', lambda **kwargs: object())
    monkeypatch.setattr(module, 'Conversation', Conversation)
    result = module.OpenHandsBuilder(Settings(openhands_max_iterations=64)).run('safe fixture', tmp_path)
    assert seen['max_iteration_per_run'] == 64
    assert result.estimated_cost_usd == 0
