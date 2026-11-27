"""Tek yetkili dağıtıcı: dosya kaydı süreçler arasında atomik; medya kuyruğu aynı içerikli işi iki kez ürettirmez.
GLB baytları sentetiktir: yalnız taşıma/dağıtım mantığını sınar, film kalitesini DEĞİL."""
import hashlib, json, multiprocessing as mp, os, shutil, sys, threading
from pathlib import Path
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import cloud_evidence as CE, job_ledger as L
from test_studio_media_queue import system, worker, sample_glb, qmod_floors

PROMPT = "Aden helps a baby bird learn to share."


# ---------------------------------------------------------------- dosya kaydı
def _racer(root, name, barrier, results):
    barrier.wait()
    try:
        results.put(L.claim(root, "j", name, "H")["ok"])
    except Exception as exc:                       # taban sürümde: FileNotFoundError / JSONDecodeError
        results.put(type(exc).__name__)


def test_concurrent_processes_get_exactly_one_claim(tmp_path):
    ctx = mp.get_context("spawn")                  # Windows ile aynı başlatma yöntemi
    for round_ in range(3):
        root = str(tmp_path / str(round_)); barrier = ctx.Barrier(6); results = ctx.Queue()
        procs = [ctx.Process(target=_racer, args=(root, f"m{i % 2}", barrier, results)) for i in range(6)]
        [p.start() for p in procs]
        got = [results.get(timeout=60) for _ in procs]
        [p.join(timeout=30) for p in procs]
        assert sorted(map(str, got)) == ["False"] * 5 + ["True"], got


def test_second_process_on_same_machine_is_rejected_and_stale_owner_is_fenced(tmp_path):
    r = str(tmp_path); res = tmp_path / "o.bin"; res.write_bytes(b"x")
    first = L.claim(r, "j", "pc", "H", now=1)
    assert L.claim(r, "j", "pc", "H", now=2)["action"] == "REJECT"
    second = L.claim(r, "j", "pc", "H", now=2 + L.TTL)                  # aynı makinede yeniden başlatma: nabız bayatladıktan sonra
    assert second["action"] == "RESUME" and second["token"] != first["token"]
    t = first["token"]
    assert not L.heartbeat(r, "j", "pc", token=t) and not L.complete(r, "j", "pc", str(res), token=t) and not L.fail(r, "j", "pc", "eski", token=t)
    assert L.complete(r, "j", "pc", str(res), token=second["token"])
    assert not L.fail(r, "j", "pc", "tamamlanmış iş bozulamaz", token=second["token"])
    assert L.claim(r, "j", "pc", "H")["action"] == "DONE"


def test_job_ids_with_slash_and_underscore_do_not_collide(tmp_path):
    r = str(tmp_path)
    assert L.claim(r, "a/b", "m1", "H")["ok"] and L.claim(r, "a_b", "m2", "H")["action"] == "RUN"


def _evidence_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(CE, "ROOT", str(tmp_path))
    monkeypatch.setattr(CE.dev_cmd, "src_hash", lambda root: "H")


def test_repeat_run_keeps_verified_evidence_and_does_not_rerun(tmp_path, monkeypatch):
    _evidence_repo(tmp_path, monkeypatch)
    out = tmp_path / "ev.json"; counter = tmp_path / "count"
    cmd = [sys.executable, "-c", f"open({str(counter)!r},'a').write('x')"]
    argv = ["m", "job", str(out), "--"] + cmd
    assert CE.main(argv) == 0
    proof = out.read_bytes()
    for _ in range(3):
        assert CE.main(argv) == 0
    assert out.read_bytes() == proof and counter.read_text() == "x"
    assert "token" not in json.loads(proof)["claim"]


def test_long_command_heartbeats_and_blocks_second_runner(tmp_path, monkeypatch):
    _evidence_repo(tmp_path, monkeypatch); monkeypatch.setattr(L, "TTL", 1.2)
    out = tmp_path / "ev.json"; done = []
    th = threading.Thread(target=lambda: done.append(CE.main(["m1", "job", str(out), "--", sys.executable, "-c", "import time; time.sleep(3.5)"])))
    th.start()
    import time; time.sleep(2.5)                                     # TTL'den uzun süredir çalışıyor
    assert L.claim(str(tmp_path), "job", "m2", "H")["action"] == "REJECT"
    th.join(timeout=30)
    assert done == [0]


def test_runner_that_loses_ownership_stops_and_writes_no_evidence(tmp_path, monkeypatch):
    _evidence_repo(tmp_path, monkeypatch); monkeypatch.setattr(L, "TTL", 1.2)
    monkeypatch.setattr(L, "heartbeat", lambda *a, **k: False)
    out = tmp_path / "ev.json"
    assert CE.main(["m1", "job", str(out), "--", sys.executable, "-c", "import time; time.sleep(30)"]) == 5
    assert not out.exists()


def test_unstartable_command_is_recorded_failed_not_left_running(tmp_path, monkeypatch):
    _evidence_repo(tmp_path, monkeypatch)
    with pytest.raises(OSError):
        CE.main(["m1", "job", str(tmp_path / "e.json"), "--", str(tmp_path / "yok-boyle-komut")])
    assert L.claim(str(tmp_path), "job", "m1", "H")["action"] == "RUN"


# ---------------------------------------------------------------- medya kuyruğu
def second_episode(os_, first_id, tmp_path, prompt=PROMPT):
    """Aynı isteğin ikinci kez gönderilmesi (ör. çift tıklama): ayrı bölüm kimliği, aynı onaylı yönetmen verisi."""
    eid = os_.submit(prompt, minutes=1)["episode_id"]
    folder = tmp_path / "cloud/episode-artifacts" / eid; folder.mkdir(parents=True)
    plan = folder / "shot-plan.json"
    shutil.copy(tmp_path / "cloud/episode-artifacts" / first_id / "shot-plan.json", plan)
    with os_.connect() as db:
        for tid in ("intake", "canon", "story", "storyboard", "asset_inventory"):
            row = db.execute("SELECT state,result_json FROM tasks WHERE episode_id=? AND task_id=?", (first_id, tid)).fetchone()
            result = row["result_json"]
            if tid == "storyboard":
                result = json.dumps({"draft_path": str(plan), "sha256": hashlib.sha256(plan.read_bytes()).hexdigest()})
            db.execute("UPDATE tasks SET state=?,result_json=? WHERE episode_id=? AND task_id=?", (row["state"], result, eid, tid))
    return eid


def jobs_of(q, task="model:aden"):
    with q.connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM media_jobs WHERE task_id=? ORDER BY created,rowid", (task,))]


def drain(q, who):
    """Bu yetenek için dağıtılabilen her şeyi al (her biri ayrı işçiyle)."""
    out = []
    for i in range(8):
        w, _ = worker(q, f"{who}-{i}")
        r = q.lease(w)
        out.append(r)
        if r["status"] != "LEASED":
            return out
    raise AssertionError("kuyruk bitmedi")


def produce(q, maker, job):
    data = sample_glb(); sha = hashlib.sha256(data).hexdigest()
    q.upload(maker, job["job_id"], "model.glb", sha, data, job["lease_key"])
    q.complete(maker, job["job_id"], job["lease_key"], {"schema": "ahos.media.result.v1", "capability": "character_model", "technical_status": "PASSED",
               "new_spend_eur": 0, "license_status": "COMMERCIAL_REVIEWED", "artifacts": [{"filename": "model.glb", "sha256": sha}]})


def review(q, reviewer, score=1.0):
    claim = q.review_claim(reviewer); assert claim["status"] == "REVIEWING", claim
    proof = json.dumps({"check": claim["job_id"]}).encode(); sha = hashlib.sha256(proof).hexdigest()
    name = f"proof-{claim['job_id'][:8]}-{score}.json"
    q.upload(reviewer, claim["job_id"], name, sha, proof)
    res = q.review(reviewer, claim["job_id"], {"schema": "ahos.media.review.v1", "method": "human_frame_audio_review",
                   "proof": {"filename": name, "sha256": sha}, "scores": {k: score for k in qmod_floors()}})
    return claim, res


def two_identical(tmp_path):
    q, os_, e1 = system(tmp_path); e2 = second_episode(os_, e1, tmp_path)
    q.sync_ready()
    assert len(jobs_of(q)) == 2
    return q, os_, e1, e2


def model_leases(results):
    return [r for r in results if r["status"] == "LEASED" and r["payload"]["task_id"] == "model:aden"]


def test_identical_in_flight_work_is_dispatched_once(tmp_path):
    q, _, _, _ = two_identical(tmp_path)
    got = drain(q, "actor")
    assert len(model_leases(got)) == 1
    assert got[-1]["status"] == "NO_COMPATIBLE_WORK" and got[-1]["held_duplicates"] >= 1


def test_simultaneous_lease_requests_never_double_dispatch(tmp_path):
    q, _, _, _ = two_identical(tmp_path)
    people = [worker(q, f"par-{i}")[0] for i in range(6)]
    barrier = threading.Barrier(len(people)); got = []
    def go(w):
        barrier.wait(); got.append(q.lease(w))
    ts = [threading.Thread(target=go, args=(w,)) for w in people]
    [t.start() for t in ts]; [t.join(timeout=60) for t in ts]
    assert len(got) == 6 and len(model_leases(got)) == 1, got


def test_different_story_is_not_treated_as_duplicate(tmp_path):
    q, os_, e1 = system(tmp_path)
    second_episode(os_, e1, tmp_path, prompt="Aden builds a small paper boat and learns patience.")
    assert len(model_leases(drain(q, "actor"))) == 2


def test_passed_work_is_reused_without_production_but_still_needs_independent_qa(tmp_path):
    q, os_, e1, e2 = two_identical(tmp_path)
    maker, _ = worker(q, "maker"); rev, _ = worker(q, "reviewer", role="reviewer")
    job = q.lease(maker); produce(q, maker, job)
    assert not model_leases(drain(q, "while-waiting"))                 # QA beklerken de ikinci üretim yok
    review(q, rev)
    got = drain(q, "after-pass")
    assert not model_leases(got)
    first, second = jobs_of(q)
    assert second["state"] == "AWAITING_QA" and second["attempts"] == 0 and second["worker_id"] == "maker"
    assert [x for r in got for x in r.get("reused_without_production", [])] == [second["job_id"]]
    assert {t["task_id"]: t["state"] for t in os_.episode(e2)["tasks"]}["model:aden"] == "AWAITING_QA"     # otomatik onay YOK
    claim, res = review(q, rev)
    assert claim["job_id"] == second["job_id"] and res["status"] == "QA_PASS"
    assert claim["artifacts"][0]["sha256"] == hashlib.sha256(sample_glb()).hexdigest()


def test_rejected_reuse_leads_to_real_production_once_no_loop(tmp_path):
    q, _, _, _ = two_identical(tmp_path)
    maker, _ = worker(q, "maker"); rev, _ = worker(q, "reviewer", role="reviewer")
    job = q.lease(maker); produce(q, maker, job); review(q, rev)
    drain(q, "a"); _, res = review(q, rev, score=0.1)
    assert res["status"] == "QUEUED"
    again = drain(q, "b")
    assert [r["attempt"] for r in model_leases(again)] == [1] and not any(r.get("reused_without_production") for r in again)


def test_tampered_source_artifact_is_never_reused(tmp_path):
    q, _, _, _ = two_identical(tmp_path)
    maker, _ = worker(q, "maker"); rev, _ = worker(q, "reviewer", role="reviewer")
    job = q.lease(maker); produce(q, maker, job); review(q, rev)
    with q.connect() as db:
        path = db.execute("SELECT local_path FROM media_artifacts WHERE job_id=? AND role='worker'", (job["job_id"],)).fetchone()[0]
    Path(path).write_bytes(b"glTF" + b"\x01" * 256)
    assert len(model_leases(drain(q, "a"))) == 1                       # yeniden üretilir
    with q.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM media_events WHERE event='REUSE_REJECTED'").fetchone()[0] == 1


def test_duplicate_of_blocked_work_does_not_get_new_attempt_budget(tmp_path):
    q, _, _, _ = two_identical(tmp_path)
    maker, _ = worker(q, "maker"); leased = 0
    for _ in range(10):
        r = q.lease(maker)
        if r["status"] != "LEASED" or r["payload"]["task_id"] != "model:aden":
            break
        leased += 1; q.fail(maker, r["job_id"], r["lease_key"], "backend failed deliberately")
    assert leased == 3 and [j["state"] for j in jobs_of(q)] == ["BLOCKED", "QUEUED"]


def test_failed_or_expired_first_job_releases_the_hold(tmp_path):
    q, _, _, _ = two_identical(tmp_path)
    a, _ = worker(q, "actor-a"); job = q.lease(a)
    with q.connect() as db:
        db.execute("UPDATE media_jobs SET lease_until=0 WHERE job_id=?", (job["job_id"],))
    assert len(model_leases(drain(q, "b"))) == 1                       # süresi dolan iş bir kez yeniden dağıtılır


def test_work_key_ignores_transient_ids_but_not_content_or_inputs():
    base = {"episode_id": "1", "shotplan_sha256": "a", "creative_status": "x", "task_id": "t", "scene_plan": {"n": 1}}
    k = L.work_key("render", base, [("up", "f", "s1")])
    assert k == L.work_key("render", dict(base, episode_id="2", shotplan_sha256="b"), [("up", "f", "s1")])
    assert k != L.work_key("render", dict(base, scene_plan={"n": 2}), [("up", "f", "s1")])
    assert k != L.work_key("render", base, [("up", "f", "s2")])
    assert k != L.work_key("voice", base, [("up", "f", "s1")])
