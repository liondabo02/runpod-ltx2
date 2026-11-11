"""AHOS Studio OS: tests of episode-wide orchestration rather than single character generation."""
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ahos_studio_os",ROOT/"tools"/"ahos_studio_os.py")
so=importlib.util.module_from_spec(spec)
spec.loader.exec_module(so)


def fake_repo(tmp_path):
    root=tmp_path/"repo"
    chars=root/"studio/reference/owner_accepted_roster_v1/characters"
    chars.mkdir(parents=True)
    (chars/"01_aden.png").write_bytes(b"ADEN CANON SOURCE")
    (chars/"02_kaan.png").write_bytes(b"KAAN CANON SOURCE")
    (root/"studio/pipeline").mkdir(parents=True)
    (root/"studio/pipeline/production-backends.json").write_text(
        json.dumps({"schema":"ahos.production.adapters.v1","stages":{}}))
    return root


def test_one_prompt_builds_full_episode_multilingual_dag():
    plan=so.compile_episode(
        "Aden ve Kaan ormanda tavşana yardım etsin, paylaşmayı öğrensin.",
        minutes=8,languages=("tr","de"))
    assert plan["scene_count"]==8
    assert plan["cast"]==["aden","kaan"]
    assert plan["production_ready"] is False
    ids={x["id"] for x in plan["tasks"]}
    assert "story" in ids and "storyboard" in ids
    assert "model:aden" in ids and "rig:kaan" in ids
    assert "scene08:tr:render" in ids
    assert "scene01:de:voice" in ids
    assert "episode:tr:edit" in ids and "episode:de:qa" in ids
    assert all(set(x["deps"]).issubset(ids) for x in plan["tasks"])
    assert len(plan["tasks"])<=300


def test_prompt_changes_cast_and_plan():
    p=so.compile_episode("Veysel ve Öznur parkta.",minutes=2)
    assert p["cast"]==["veysel","oznur"]
    assert "model:veysel" in {t["id"] for t in p["tasks"]}
    assert "model:aden" not in {t["id"] for t in p["tasks"]}


def test_request_validation_and_caps():
    for args in [
        {"prompt":""},
        {"prompt":"ok","minutes":21},
        {"prompt":"ok","languages":("not_a_language",)},
        {"prompt":"ok","series_id":"../evil"},
    ]:
        with pytest.raises(ValueError):
            so.compile_episode(**args)
    with pytest.raises(ValueError,match="300"):
        so.compile_episode("Aden",minutes=20,languages=("tr","de","en","ar","fr","es","ku"))


def test_durable_episode_intake_and_canon_check(tmp_path):
    root=fake_repo(tmp_path)
    engine=so.StudioOS(tmp_path/"state.sqlite",root=root)
    info=engine.submit("Aden ve Kaan bahçede oyun oynasın.",minutes=2)
    result=engine.tick(info["episode_id"])
    assert [x["task"] for x in result["steps"][:2]]==["intake","canon"]
    episode=engine.episode(info["episode_id"])
    task={x["task_id"]:x for x in episode["tasks"]}
    assert task["intake"]["state"]=="DONE_VERIFIED"
    assert task["canon"]["state"]=="DONE_VERIFIED"
    assert task["canon"]["result"]["locked_characters"]["aden"]==so.sha(root/"studio/reference/owner_accepted_roster_v1/characters/01_aden.png")
    assert task["story"]["state"]=="WAITING_PROVIDER"
    assert not episode["production_ready"]
    second=so.StudioOS(tmp_path/"state.sqlite",root=root).episode(info["episode_id"])
    assert second["tasks"][0]["state"]=="DONE_VERIFIED"
    assert len(engine.get_events(info["episode_id"]))>=4


def test_does_not_fake_technical_backend_as_final(tmp_path):
    root=fake_repo(tmp_path)
    scripts=root/"tools/studio_backends"
    scripts.mkdir(parents=True)
    (scripts/"character_model_backend.py").write_text("print('placeholder')\n")
    (root/"studio/pipeline/production-backends.json").write_text(json.dumps({
        "schema":"ahos.production.adapters.v1",
        "stages":{"character_model":{"script":"tools/studio_backends/character_model_backend.py","cost_eur":0}}}))
    engine=so.StudioOS(tmp_path/"db.sqlite",root=root)
    info=engine.submit("Aden yürüyor.",minutes=1)
    state=engine.tick(info["episode_id"])
    assert state["status"]=="WAITING_CAPABILITIES"
    assert engine.episode(info["episode_id"])["production_ready"] is False
    assert engine.episode(info["episode_id"])["tasks"][-1]["state"]=="PENDING"


def test_missing_owner_canon_stops_without_substituting(tmp_path):
    root=fake_repo(tmp_path)
    (root/"studio/reference/owner_accepted_roster_v1/characters/02_kaan.png").unlink()
    os=so.StudioOS(tmp_path/"db.sqlite",root=root)
    eid=os.submit("Aden ile Kaan.",minutes=1)["episode_id"]
    os.tick(eid)
    t={t["task_id"]:t for t in os.episode(eid)["tasks"]}
    assert t["canon"]["state"]=="WAITING_PROVIDER"
    assert "kaan" in t["canon"]["result"]["missing"]


def test_global_queue_cap_blocks_new_episodes(tmp_path):
    root=fake_repo(tmp_path)
    eng=so.StudioOS(tmp_path/"db.sqlite",root=root)
    for _ in range(3):
        eng.submit("Aden ve Kaan bir hikâye.",minutes=8,languages=("tr","de"))
    with pytest.raises(RuntimeError,match="Pending cap"):
        eng.submit("Aden ve Kaan bir hikâye daha.",minutes=8,languages=("tr","de"))


def test_cloud_draft_advances_story_and_adds_guest_jobs(tmp_path,monkeypatch):
    import sys
    root=fake_repo(tmp_path)
    os=so.StudioOS(tmp_path/"db.sqlite",root=root)
    created=os.submit("Aden ve Kaan bir yavru tavşan buluyor",minutes=2,languages=("tr",))
    sys.path.insert(0,str(ROOT/"tools"))
    import studio_os_cloud_writer
    def fake_writer(prompt,cast,scenes,**kwargs):
        return {"schema":"ahos.studio-os.outline.v1","model":"test-local-model",
                "status":"DRAFT_UNREVIEWED","cast":cast,
                "guest_characters_pending_assets":["Tavşan"],
                "outline":{"title":"Yardımlaşma","scenes":[
                    {"number":i+1,"summary":"Aden ve Kaan tavşanı koruyarak birlikte yardım ediyor.",
                     "characters":["Aden","Kaan","Tavşan"]} for i in range(scenes)]}}
    monkeypatch.setattr(studio_os_cloud_writer,"generate_outline",fake_writer)
    outcome=os.tick(created["episode_id"],use_existing_oracle=True)
    assert outcome["status"]=="WAITING_CAPABILITIES"
    state=os.episode(created["episode_id"])
    tasks={t["task_id"]:t for t in state["tasks"]}
    assert tasks["story"]["state"]=="DONE_DRAFT"
    assert tasks["storyboard"]["state"]=="DONE_DRAFT"
    assert tasks["asset_inventory"]["state"]=="DONE_VERIFIED"
    guest=[k for k in tasks if k.startswith("rig:guest-")]
    assert len(guest)==1
    assert guest[0] in tasks["scene01:animation"]["deps"]
    assert Path(tasks["story"]["result"]["draft_path"]).exists()
    assert state["production_ready"] is False


def test_blocked_state_survives_subsequent_idle_tick(tmp_path):
    root=fake_repo(tmp_path)
    engine=so.StudioOS(tmp_path/"db.sqlite",root=root)
    eid=engine.submit("Aden ve Kaan ormanda",minutes=2)["episode_id"]
    initial=engine.tick(eid)
    again=engine.tick(eid)
    assert initial["status"]=="WAITING_CAPABILITIES"
    assert again["status"]=="WAITING_CAPABILITIES"
    assert again["steps"]==[]
