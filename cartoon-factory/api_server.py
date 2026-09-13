from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orchestrator.main import ROOT, build_jobs, make_episode

app = FastAPI(title="Cartoon Factory API", version="0.3.0")
PY = sys.executable


class EpisodeRequest(BaseModel):
    idea: str = Field(min_length=1)
    episode_id: str | None = None
    languages: str = "all"


def status_path(episode_id: str) -> Path:
    return ROOT / "output" / episode_id / "status.json"


def write_status(episode_id: str, state: str, message: str, extra: dict | None = None) -> None:
    p = status_path(episode_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "episode_id": episode_id,
        "state": state,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def episode_id_now() -> str:
    return datetime.now().strftime("episode_%Y%m%d_%H%M%S")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "cartoon-factory", "version": app.version}


@app.post("/episodes/plan")
def plan_episode(req: EpisodeRequest) -> dict:
    try:
        episode_id = req.episode_id or episode_id_now()
        out = ROOT / "output" / episode_id
        out.mkdir(parents=True, exist_ok=True)
        episode = make_episode(req.idea)
        jobs = build_jobs(episode)
        (out / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
        write_status(episode_id, "planned", "Episode plan created", {"idea": req.idea})
        return {
            "ok": True,
            "episode_id": episode_id,
            "scenes": len(episode.get("scenes", [])),
            "episode_manifest": str(out / "episode.json"),
            "jobs_manifest": str(out / "jobs.json"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/episodes/run")
def run_episode(req: EpisodeRequest) -> dict:
    try:
        episode_id = req.episode_id or episode_id_now()
        out = ROOT / "output" / episode_id
        out.mkdir(parents=True, exist_ok=True)
        log_path = out / "pipeline.log"
        write_status(episode_id, "queued", "Production queued", {"idea": req.idea, "languages": req.languages})
        log = log_path.open("ab")
        proc = subprocess.Popen(
            [PY, str(ROOT / "run_pipeline.py"), req.idea, "--episode-id", episode_id, "--languages", req.languages],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        write_status(episode_id, "running", "Production started", {"pid": proc.pid, "idea": req.idea, "languages": req.languages})
        return {
            "ok": True,
            "episode_id": episode_id,
            "state": "running",
            "pid": proc.pid,
            "status_url": f"/episodes/{episode_id}/status",
            "log": str(log_path),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/episodes/{episode_id}/status")
def get_episode_status(episode_id: str) -> dict:
    p = status_path(episode_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Episode status not found")
    data = json.loads(p.read_text(encoding="utf-8"))
    delivery = ROOT / "output" / episode_id / "delivery_manifest.json"
    if delivery.exists():
        data["delivery"] = json.loads(delivery.read_text(encoding="utf-8"))
        if data.get("state") not in {"failed"}:
            data["state"] = "completed"
            data["message"] = "Production completed"
    return data


# Backward-compatible endpoint: plan only.
@app.post("/episodes")
def create_episode(req: EpisodeRequest) -> dict:
    return plan_episode(req)
