"""A1-A4/B1-B3 acceptance: no real credentials, network, or permanent paths."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from ahos.autonomous_company import PersistentMissionQueue, QueueStatus
from ahos.llm_executor import ModelSettings, make_model_executor
from ahos.mission_orchestrator import MissionResult, MissionStatus
from ahos.model_router import pick
from ahos.queue_drain import drain
from ahos.scope import as_document_objective, classify
from ahos.workforce_execution import WorkItem


def _settings(**values):
    options = dict(base_url="https://example.invalid/v1", api_key="fake",
                   model="configured-default", max_usd_per_run=1.0,
                   browser_check=False)
    options.update(values)
    return ModelSettings(**options)


def _project(tmp_path):
    root = tmp_path / "project"
    (root / "www").mkdir(parents=True)
    (root / "www" / "game.js").write_text("const a=1;\n", encoding="utf-8")
    return root


def _item():
    return WorkItem(task_id="task-a:produce", title="www/game.js içindeki değeri değiştir",
                    department="software", required_capabilities=frozenset({"python"}))


def _responses(*payloads):
    replies = iter(payloads)
    calls = []
    def transport(system, prompt, settings):
        calls.append((system, prompt, settings.model))
        return json.dumps(next(replies), ensure_ascii=False)
    return transport, calls


def _gate():
    return [sys.executable, "-c", 'from pathlib import Path; assert Path("www/game.js").read_text().strip() == "const a=2;"']


def test_a1_classifies_deterministic_and_complex(tmp_path):
    assert tmp_path.is_dir()
    assert classify("dosyasının sonuna açıklama ekle") == "deterministic"
    assert classify("Yeni bir video motoru tasarla ve API kur") == "complex"
    assert classify("") == "complex"


def test_a2_complex_goal_transformed_and_qa_blocked(tmp_path):
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    objective = "yeni video motoru tasarla ve API kur"
    queue.enqueue(mission_id="a2", objective=objective, primary_department="creative")
    converted = as_document_objective(objective)
    seen = []
    class Console:
        runtime_dir = tmp_path
        book = SimpleNamespace(get=lambda department: SimpleNamespace(department_id=department))
        def _project_for_department(self, department):
            return None
        def _execute(self, spec, target, mission_id, executor=None):
            seen.append((target, executor))
            return MissionResult(mission_id, target, None, MissionStatus.BLOCKED, (), "QA not verified")
        def _record(self, mission_id, owner, result):
            queue.block(mission_id, owner=owner, result=result)
    console = Console()
    report = drain(console, limit=1)
    assert report["executed"] == ["a2"]
    assert seen and seen[0][0] == converted and callable(seen[0][1])
    assert console._scope_document is False  # no QA mode leak to next mission
    assert queue.get("a2").status is QueueStatus.BLOCKED


def test_a3_empty_patch_gets_one_self_repair(tmp_path):
    root = _project(tmp_path)
    transport, calls = _responses(
        {"summary": "no patch", "edits": [], "risk": "low"},
        {"summary": "repaired", "edits": [
            {"path": "www/game.js", "find": "const a=1;", "replace": "const a=2;"}
        ], "risk": "low"},
    )
    executor = make_model_executor(root, tmp_path / "artifacts", settings=_settings(),
                                   transport=transport, verify_command=_gate())
    result = executor(_item(), "coding-worker")
    assert result.success is True, result.summary
    assert root.joinpath("www", "game.js").read_text(encoding="utf-8") == "const a=2;\n"
    assert len(calls) == 2
    assert "BOŞ" in calls[1][1].upper() or "boş" in calls[1][1]


def test_a3_second_empty_patch_is_blocked(tmp_path):
    root = _project(tmp_path)
    transport, calls = _responses(
        {"summary": "no patch", "edits": [], "risk": "low"},
        {"summary": "still none", "edits": [], "risk": "low"},
    )
    result = make_model_executor(root, tmp_path / "artifacts", settings=_settings(),
                                 transport=transport, verify_command=_gate())(
        _item(), "coding-worker")
    assert not result.success and "blocked" in result.summary
    assert len(calls) == 2
    assert root.joinpath("www", "game.js").read_text(encoding="utf-8") == "const a=1;\n"


def test_b3_router_chooses_credentialed_model_and_executor_uses_it(tmp_path, monkeypatch):
    configuration = tmp_path / "models.json"
    configuration.write_text((Path(__file__).resolve().parents[1] / "config" / "models.json").read_text(encoding="utf-8"), encoding="utf-8")
    settings = _settings(base_url="https://openrouter.ai/api/v1")
    env = {"OPENROUTER_API_KEY": "fake-api-key"}
    assert pick("complex", settings=settings, env=env, config_path=configuration) == "qwen/qwen3-coder:free"
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-api-key")
    root = _project(tmp_path)
    transport, calls = _responses(
        {"summary": "none", "edits": [], "risk": "low"},
        {"summary": "none", "edits": [], "risk": "low"},
    )
    executor = make_model_executor(root, tmp_path / "artifacts", settings=settings,
                                   transport=transport, verify_command=_gate())
    result = executor(WorkItem(task_id="model:produce", title="karmaşık video motoru tasarla",
                               department="software", required_capabilities=frozenset()), "worker")
    assert result.success is False
    assert len(calls) == 2 and {call[2] for call in calls} == {"qwen/qwen3-coder:free"}


def test_b3_missing_key_preserves_fallback(tmp_path):
    configuration = tmp_path / "models.json"
    configuration.write_text((Path(__file__).resolve().parents[1] / "config" / "models.json").read_text(encoding="utf-8"), encoding="utf-8")
    settings = _settings(base_url="https://openrouter.ai/api/v1", model="preconfigured-fallback")
    assert pick("complex", settings=settings, env={}, config_path=configuration) == "preconfigured-fallback"
    assert pick("complex", settings=settings, env={}, config_path=tmp_path / "missing.json") == "preconfigured-fallback"


def test_a2_deterministic_queue_uses_simple_edits_without_model(tmp_path):
    """A queued append must mutate the real project without invoking a model."""
    queue = PersistentMissionQueue(tmp_path / "company-service.db")
    project = _project(tmp_path)
    objective = "www/game.js dosyasının sonuna şu yorumu ekle: // queue-proof"
    assert classify(objective) == "deterministic"
    queue.enqueue(mission_id="a2-simple", objective=objective, primary_department="software")

    class Console:
        runtime_dir = tmp_path
        book = SimpleNamespace(get=lambda department: SimpleNamespace(department_id=department))

        def _project_for_department(self, department):
            return SimpleNamespace(work_path=project, path=project)

        def _execute(self, *args, **kwargs):
            raise AssertionError("deterministic work must not invoke the model")

        def _record(self, mission_id, owner, result):
            if result.status is MissionStatus.COMPLETED:
                queue.complete(mission_id, owner=owner, result=result)
            else:
                queue.block(mission_id, owner=owner, result=result)

    report = drain(Console(), limit=1)
    assert report["executed"] == ["a2-simple"]
    assert queue.get("a2-simple").status is QueueStatus.COMPLETED
    content = (project / "www" / "game.js").read_text(encoding="utf-8")
    assert content.endswith("// queue-proof\n")

    # An idempotent repeat must not manufacture another verified delivery.
    queue.enqueue(mission_id="a2-noop", objective=objective, primary_department="software")
    repeated = drain(Console(), limit=1)
    assert repeated["executed"] == ["a2-noop"]
    assert queue.get("a2-noop").status is QueueStatus.BLOCKED
    assert (project / "www" / "game.js").read_text(encoding="utf-8") == content
