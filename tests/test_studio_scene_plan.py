"""Media scene jobs must use verified scene-specific director beats."""
import json
from pathlib import Path
import pytest
from test_studio_media_queue import system
from studio_media_queue import QueueError


def test_scene_job_receives_correct_director_beat(tmp_path):
    q,os,eid=system(tmp_path)
    assert q.sync_ready()>=1
    with q.connect() as db:
        row=db.execute(
            "SELECT payload FROM media_jobs WHERE episode_id=? AND task_id='scene01:set'",
            (eid,)).fetchone()
    data=json.loads(row["payload"])
    assert data["scene_plan"]["scene_id"]=="scene01"
    assert data["scene_plan"]["plot_beat"]["location"]=="garden"
    assert data["scene_plan"]["planned_seconds"]==60
    assert data["creative_status"]=="DRAFT_UNREVIEWED"
    assert len(data["shotplan_sha256"])==64
    assert data["production_ready"] is False


def test_tampered_director_plan_blocks_all_new_work(tmp_path):
    q,os,eid=system(tmp_path)
    plan=tmp_path/"cloud/episode-artifacts"/eid/"shot-plan.json"
    plan.write_text('{"schema":"ahos.studio-os.shotplan.v1","scenes":[]}',encoding="utf-8")
    with pytest.raises(QueueError,match="Shot-plan path or hash"):
        q.sync_ready()
    # SQLite BEGIN IMMEDIATE + rollback: no partial enqueue accepted.
    assert q.status()["jobs"]=={}
