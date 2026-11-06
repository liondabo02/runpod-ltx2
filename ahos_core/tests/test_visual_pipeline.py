import json
from pathlib import Path

import pytest

from ahos.visual_pipeline import (
    ComfyUIClient,
    ExecutionGateError,
    RenderManifestStore,
    VisualProductionPlanner,
    WorkflowTemplate,
    WorkflowTemplateError,
    deterministic_seed,
)


def graph():
    return {
        "episode_id": "S01E001",
        "style": {"style_id": "family-2d-v1"},
        "shots": [
            {
                "shot_id": "SCENE-01-SHOT-01",
                "duration_seconds": 24,
                "prompt_id": "p1",
                "output_asset_id": "o1",
            },
            {
                "shot_id": "SCENE-01-SHOT-02",
                "duration_seconds": 24,
                "prompt_id": "p2",
                "output_asset_id": "o2",
            },
        ],
        "prompts": [
            {
                "prompt_id": "p1",
                "positive_prompt": "Aden at home",
                "negative_prompt": "drift",
                "reference_asset_ids": ["charref:aden:v1", "envref:home"],
                "continuity_constraints": ["keep identity"],
                "style_id": "family-2d-v1",
            },
            {
                "prompt_id": "p2",
                "positive_prompt": "Kaan at home",
                "negative_prompt": "drift",
                "reference_asset_ids": ["charref:kaan:v1", "envref:home"],
                "continuity_constraints": ["keep identity"],
                "style_id": "family-2d-v1",
            },
        ],
    }


def test_render_jobs_are_deterministic():
    planner = VisualProductionPlanner()
    first = planner.plan(graph())
    second = planner.plan(graph())

    assert [j.job_id for j in first] == [j.job_id for j in second]
    assert [j.seed for j in first] == [j.seed for j in second]
    assert all(j.mode == "video" for j in first)
    assert deterministic_seed("a", "b") == deterministic_seed("a", "b")


def test_comfyui_endpoint_is_localhost_only():
    ComfyUIClient("http://127.0.0.1:8188")
    ComfyUIClient("http://localhost:8188")

    with pytest.raises(ValueError):
        ComfyUIClient("https://example.com:8188")


def test_workflow_template_substitutes_required_values(tmp_path: Path):
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "inputs": {
                        "text": "{{POSITIVE_PROMPT}}",
                        "negative": "{{NEGATIVE_PROMPT}}",
                        "seed": "{{SEED}}",
                        "filename_prefix": "{{OUTPUT_PREFIX}}",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    job = VisualProductionPlanner().plan(graph())[0]
    rendered = WorkflowTemplate.load(path, mode="video").render(job)

    inputs = rendered["1"]["inputs"]
    assert inputs["text"] == job.positive_prompt
    assert inputs["negative"] == job.negative_prompt
    assert inputs["seed"] == job.seed
    assert inputs["filename_prefix"] == job.output_prefix


def test_workflow_template_rejects_unknown_placeholder(tmp_path: Path):
    path = tmp_path / "workflow.json"
    path.write_text(
        json.dumps({"1": {"inputs": {"x": "{{UNKNOWN_VALUE}}"}}}),
        encoding="utf-8",
    )
    job = VisualProductionPlanner().plan(graph())[0]

    with pytest.raises(WorkflowTemplateError):
        WorkflowTemplate.load(path, mode="video").render(job)


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request_json(self, method, url, payload=None, timeout=10.0):
        self.calls.append((method, url, payload))
        if url.endswith("/system_stats"):
            return {"system": "ok"}
        if url.endswith("/object_info"):
            return {"KSampler": {}, "SaveImage": {}}
        if url.endswith("/prompt"):
            return {"prompt_id": "prompt-123"}
        return {}


def test_health_probe_is_read_only_and_counts_nodes():
    transport = FakeTransport()
    health = ComfyUIClient(
        "http://127.0.0.1:8188",
        transport=transport,
    ).health()

    assert health.reachable is True
    assert health.node_count == 2
    assert [call[0] for call in transport.calls] == ["GET", "GET"]


def test_render_submission_requires_both_owner_and_execution_gate(tmp_path: Path):
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {
                    "inputs": {
                        "text": "{{POSITIVE_PROMPT}}",
                        "negative": "{{NEGATIVE_PROMPT}}",
                        "seed": "{{SEED}}",
                        "filename_prefix": "{{OUTPUT_PREFIX}}",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    template = WorkflowTemplate.load(workflow, mode="video")
    job = VisualProductionPlanner().plan(graph())[0]
    client = ComfyUIClient(
        "http://127.0.0.1:8188",
        transport=FakeTransport(),
    )

    with pytest.raises(ExecutionGateError):
        client.submit(
            job=job,
            template=template,
            owner_approved=True,
            execution_enabled=False,
        )

    with pytest.raises(ExecutionGateError):
        client.submit(
            job=job,
            template=template,
            owner_approved=False,
            execution_enabled=True,
        )

    prompt_id = client.submit(
        job=job,
        template=template,
        owner_approved=True,
        execution_enabled=True,
    )
    assert prompt_id == "prompt-123"


def test_render_manifest_store_is_persistent(tmp_path: Path):
    db = tmp_path / "render.db"
    jobs = VisualProductionPlanner().plan(graph())
    store = RenderManifestStore(db)

    for job in jobs:
        store.upsert_planned(job)

    reopened = RenderManifestStore(db)
    assert reopened.count("S01E001") == 2
    assert reopened.list_payloads("S01E001")[0]["episode_id"] == "S01E001"
