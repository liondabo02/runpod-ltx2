from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from orchestrator.main import ROOT, build_jobs, make_episode

app = FastAPI(title="Cartoon Factory API", version="0.1.0")


class EpisodeRequest(BaseModel):
    idea: str = Field(min_length=3)
    episode_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "cartoon-factory"}


@app.post("/episodes")
def create_episode(req: EpisodeRequest) -> dict:
    try:
        episode_id = req.episode_id or datetime.utcnow().strftime("episode_%Y%m%d_%H%M%S")
        out = ROOT / "output" / episode_id
        out.mkdir(parents=True, exist_ok=True)
        episode = make_episode(req.idea)
        jobs = build_jobs(episode)
        (out / "episode.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "episode_id": episode_id,
            "scenes": len(episode.get("scenes", [])),
            "episode_manifest": str(out / "episode.json"),
            "jobs_manifest": str(out / "jobs.json"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
