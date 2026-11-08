from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Protocol


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def deterministic_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 2_147_483_647


class VisualPipelineError(RuntimeError):
    pass


class ExecutionGateError(VisualPipelineError):
    pass


class WorkflowTemplateError(VisualPipelineError):
    pass


class ComfyUIConnectionError(VisualPipelineError):
    pass


class RenderJobStatus(str, Enum):
    PLANNED = "planned"
    BLOCKED = "blocked"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ComfyUIHealth:
    reachable: bool
    endpoint: str
    node_count: int
    error: str | None


@dataclass(frozen=True, slots=True)
class RenderJob:
    job_id: str
    episode_id: str
    shot_id: str
    prompt_id: str
    output_asset_id: str
    mode: str
    seed: int
    positive_prompt: str
    negative_prompt: str
    reference_asset_ids: tuple[str, ...]
    continuity_constraints: tuple[str, ...]
    style_id: str
    duration_seconds: int
    output_prefix: str

    def to_payload(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "episode_id": self.episode_id,
            "shot_id": self.shot_id,
            "prompt_id": self.prompt_id,
            "output_asset_id": self.output_asset_id,
            "mode": self.mode,
            "seed": self.seed,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "reference_asset_ids": list(self.reference_asset_ids),
            "continuity_constraints": list(self.continuity_constraints),
            "style_id": self.style_id,
            "duration_seconds": self.duration_seconds,
            "output_prefix": self.output_prefix,
        }


@dataclass(frozen=True, slots=True)
class WorkflowTemplate:
    name: str
    mode: str
    workflow: dict[str, object]

    @classmethod
    def load(cls, path: str | Path, *, mode: str) -> "WorkflowTemplate":
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowTemplateError(
                f"invalid workflow template {source}: {exc}"
            ) from exc

        if not isinstance(payload, dict) or not payload:
            raise WorkflowTemplateError("workflow template must be a non-empty JSON object")

        return cls(name=source.stem, mode=mode, workflow=payload)

    def render(self, job: RenderJob) -> dict[str, object]:
        values = {
            "POSITIVE_PROMPT": job.positive_prompt,
            "NEGATIVE_PROMPT": job.negative_prompt,
            "SEED": str(job.seed),
            "SHOT_ID": job.shot_id,
            "EPISODE_ID": job.episode_id,
            "OUTPUT_PREFIX": job.output_prefix,
            "DURATION_SECONDS": str(job.duration_seconds),
        }

        def substitute(value: object) -> object:
            if isinstance(value, dict):
                return {str(k): substitute(v) for k, v in value.items()}
            if isinstance(value, list):
                return [substitute(v) for v in value]
            if isinstance(value, str):
                out = value
                for key, replacement in values.items():
                    out = out.replace("{{" + key + "}}", replacement)
                if out == value:
                    return value

                # Preserve numeric JSON types for exact placeholders.
                for key in ("SEED", "DURATION_SECONDS"):
                    if value == "{{" + key + "}}":
                        return int(values[key])
                return out
            return value

        rendered = substitute(self.workflow)
        assert isinstance(rendered, dict)
        unresolved = _find_placeholders(rendered)
        if unresolved:
            raise WorkflowTemplateError(
                "unresolved workflow placeholders: " + ", ".join(sorted(unresolved))
            )
        return rendered


def _find_placeholders(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found.update(_find_placeholders(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_find_placeholders(item))
    elif isinstance(value, str):
        start = 0
        while True:
            left = value.find("{{", start)
            if left < 0:
                break
            right = value.find("}}", left + 2)
            if right < 0:
                break
            found.add(value[left + 2:right])
            start = right + 2
    return found


class JsonTransport(Protocol):
    def request_json(
        self,
        method: str,
        url: str,
        payload: Mapping[str, object] | None = None,
        timeout: float = 10.0,
    ) -> object:
        ...


class UrlLibJsonTransport:
    def request_json(
        self,
        method: str,
        url: str,
        payload: Mapping[str, object] | None = None,
        timeout: float = 10.0,
    ) -> object:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError) as exc:
            raise ComfyUIConnectionError(str(exc)) from exc

        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComfyUIConnectionError(
                f"non-JSON response from ComfyUI: {exc}"
            ) from exc


class ComfyUIClient:
    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:8188",
        *,
        transport: JsonTransport | None = None,
    ) -> None:
        endpoint = endpoint.rstrip("/")
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("ComfyUI endpoint must be http/https")
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("ComfyUI endpoint must be localhost only")
        self.endpoint = endpoint
        self.transport = transport or UrlLibJsonTransport()

    def health(self) -> ComfyUIHealth:
        try:
            self.transport.request_json(
                "GET",
                self.endpoint + "/system_stats",
                timeout=3.0,
            )
            object_info = self.transport.request_json(
                "GET",
                self.endpoint + "/object_info",
                timeout=5.0,
            )
            node_count = len(object_info) if isinstance(object_info, dict) else 0
            return ComfyUIHealth(
                reachable=True,
                endpoint=self.endpoint,
                node_count=node_count,
                error=None,
            )
        except Exception as exc:
            return ComfyUIHealth(
                reachable=False,
                endpoint=self.endpoint,
                node_count=0,
                error=f"{type(exc).__name__}: {exc}",
            )

    def submit(
        self,
        *,
        job: RenderJob,
        template: WorkflowTemplate,
        owner_approved: bool,
        execution_enabled: bool,
        client_id: str = "ahos-animation-studio",
    ) -> str:
        if not execution_enabled:
            raise ExecutionGateError("render execution is disabled")
        if not owner_approved:
            raise ExecutionGateError("owner approval is required for render execution")

        rendered = template.render(job)
        response = self.transport.request_json(
            "POST",
            self.endpoint + "/prompt",
            {
                "prompt": rendered,
                "client_id": client_id,
            },
            timeout=10.0,
        )
        if not isinstance(response, dict):
            raise ComfyUIConnectionError("unexpected /prompt response")
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyUIConnectionError("ComfyUI response missing prompt_id")
        return str(prompt_id)

    def history(self, prompt_id: str) -> object:
        return self.transport.request_json(
            "GET",
            self.endpoint + "/history/" + urllib.parse.quote(prompt_id),
            timeout=10.0,
        )


class VisualProductionPlanner:
    """Converts STUDIO-004 graph JSON into deterministic render jobs."""

    def plan(self, graph_payload: Mapping[str, object]) -> tuple[RenderJob, ...]:
        episode_id = str(graph_payload["episode_id"])
        style = graph_payload.get("style", {})
        if not isinstance(style, Mapping):
            raise VisualPipelineError("graph style must be an object")
        style_id = str(style.get("style_id") or "unknown-style")

        prompts_raw = graph_payload.get("prompts", ())
        shots_raw = graph_payload.get("shots", ())
        if not isinstance(prompts_raw, list) or not isinstance(shots_raw, list):
            raise VisualPipelineError("graph prompts/shots must be arrays")

        prompts = {
            str(item["prompt_id"]): item
            for item in prompts_raw
            if isinstance(item, Mapping)
        }

        jobs: list[RenderJob] = []
        for shot in shots_raw:
            if not isinstance(shot, Mapping):
                raise VisualPipelineError("shot entry must be an object")
            prompt_id = str(shot["prompt_id"])
            prompt = prompts.get(prompt_id)
            if prompt is None:
                raise VisualPipelineError(
                    f"shot {shot.get('shot_id')} references missing prompt {prompt_id}"
                )

            shot_id = str(shot["shot_id"])
            duration = int(shot["duration_seconds"])
            mode = "video" if duration > 0 else "image"
            job_id = f"render:{episode_id}:{shot_id}"
            seed = deterministic_seed(episode_id, shot_id, style_id)
            output_prefix = f"{episode_id}/{shot_id}/{seed}"

            jobs.append(
                RenderJob(
                    job_id=job_id,
                    episode_id=episode_id,
                    shot_id=shot_id,
                    prompt_id=prompt_id,
                    output_asset_id=str(shot["output_asset_id"]),
                    mode=mode,
                    seed=seed,
                    positive_prompt=str(prompt["positive_prompt"]),
                    negative_prompt=str(prompt["negative_prompt"]),
                    reference_asset_ids=tuple(
                        str(x) for x in prompt.get("reference_asset_ids", ())
                    ),
                    continuity_constraints=tuple(
                        str(x) for x in prompt.get("continuity_constraints", ())
                    ),
                    style_id=str(prompt.get("style_id") or style_id),
                    duration_seconds=duration,
                    output_prefix=output_prefix,
                )
            )

        if not jobs:
            raise VisualPipelineError("production graph produced no render jobs")

        if len({job.job_id for job in jobs}) != len(jobs):
            raise VisualPipelineError("duplicate render job ids")

        return tuple(jobs)


class RenderManifestStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS render_jobs (
                    job_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    shot_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    prompt_id TEXT,
                    output_hash TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert_planned(self, job: RenderJob) -> None:
        now = _utc_now()
        payload = _stable_json(job.to_payload())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO render_jobs (
                    job_id, episode_id, shot_id, status, seed,
                    payload_json, prompt_id, output_hash, error,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    seed=excluded.seed,
                    updated_at=excluded.updated_at
                """,
                (
                    job.job_id,
                    job.episode_id,
                    job.shot_id,
                    RenderJobStatus.PLANNED.value,
                    job.seed,
                    payload,
                    now,
                    now,
                ),
            )

    def count(self, episode_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM render_jobs WHERE episode_id=?",
                (episode_id,),
            ).fetchone()
        return int(row["c"])

    def list_payloads(self, episode_id: str) -> tuple[dict[str, object], ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM render_jobs
                WHERE episode_id=?
                ORDER BY shot_id
                """,
                (episode_id,),
            ).fetchall()
        return tuple(json.loads(row["payload_json"]) for row in rows)


def write_render_manifest(
    jobs: tuple[RenderJob, ...],
    path: str | Path,
    *,
    comfyui_health: ComfyUIHealth | None = None,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "ahos.visual-render-manifest.v1",
        "generated_at": _utc_now(),
        "execution_enabled": False,
        "owner_approved": False,
        "comfyui": (
            {
                "reachable": comfyui_health.reachable,
                "endpoint": comfyui_health.endpoint,
                "node_count": comfyui_health.node_count,
                "error": comfyui_health.error,
            }
            if comfyui_health is not None
            else None
        ),
        "jobs": [job.to_payload() for job in jobs],
    }
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination


def write_workflow_contract(path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    contract = {
        "schema": "ahos.comfyui-workflow-contract.v1",
        "required_placeholders": [
            "{{POSITIVE_PROMPT}}",
            "{{NEGATIVE_PROMPT}}",
            "{{SEED}}",
            "{{OUTPUT_PREFIX}}",
        ],
        "optional_placeholders": [
            "{{SHOT_ID}}",
            "{{EPISODE_ID}}",
            "{{DURATION_SECONDS}}",
        ],
        "instructions": [
            "Export the chosen ComfyUI workflow in API JSON format.",
            "Replace prompt, seed, output prefix, and optional duration values with AHOS placeholders.",
            "Keep the workflow file private/local if it contains local model paths or other sensitive machine details.",
            "AHOS refuses non-localhost ComfyUI endpoints.",
            "Actual rendering remains disabled until owner approval and execution_enabled are both true.",
        ],
    }
    destination.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination
