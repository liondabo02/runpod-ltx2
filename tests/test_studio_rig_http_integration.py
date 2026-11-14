"""Rig Media Factory HTTP integration, isolated from all live Oracle state.

The model QA approval below is a TEST FIXTURE: it verifies transport and
queue gates only. It does NOT represent independent creative QA or production
approval. The optional Blender test executes the real rig backend through the
actual localhost HTTP coordinator, and intentionally stops at AWAITING_QA.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from studio_oracle_service import Coordinator, handler_factory  # noqa: E402
from studio_media_queue import FLOORS  # noqa: E402
import studio_media_worker_client as client  # noqa: E402
from studio_backends.rig import resolve_model, find_blender  # noqa: E402
from test_studio_media_http import make_root, json_call  # noqa: E402


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def http_oracle(coordinator):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(coordinator))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
        coordinator.pool.shutdown(wait=True)


def seed_director(coordinator):
    """Only deterministic task prerequisites; never claim a completed film."""
    engine = coordinator.engine
    episode_id = engine.submit(
        "Aden finds a kite and helps her little brother.",
        minutes=1, languages=("tr",),
    )["episode_id"]
    reference = (
        engine.root / "studio/reference/owner_accepted_roster_v1/"
        "characters/01_aden.png"
    ).read_bytes()
    with engine.connect() as db:
        for task in ("intake", "canon", "story", "storyboard", "asset_inventory"):
            db.execute(
                "UPDATE tasks SET state='DONE_VERIFIED' "
                "WHERE episode_id=? AND task_id=?",
                (episode_id, task),
            )
        db.execute(
            "UPDATE tasks SET result_json=? "
            "WHERE episode_id=? AND task_id='canon'",
            (json.dumps({
                "locked_characters": {"aden": sha(reference)},
                "identity_source": "owner_accepted_roster_v1",
            }), episode_id),
        )
    return episode_id


def register(base, admin, name, *, capability=None, role="worker"):
    _, result = json_call(
        base, "/api/media/register", {
            "worker_id": name,
            "role": role,
            "capabilities": [capability] if capability else [],
            "runtime_proof_sha256": sha(b"TEST-ONLY-runtime-fixture"),
            "runtime_status": "VERIFIED_RUNTIME",
            "license_status": "COMMERCIAL_REVIEWED",
            "new_spend_eur": 0,
            "region": "EU",
        }, token=admin,
    )
    return result["worker_token"]


def upload(base, token, job_id, filename, raw, *, lease_key=None):
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/octet-stream",
        "X-AHOS-Job-ID": job_id,
        "X-AHOS-Filename": filename,
        "X-AHOS-SHA256": sha(raw),
    }
    if lease_key:
        headers["X-AHOS-Lease-Key"] = lease_key
    req = Request(
        base + "/api/media/artifact", data=raw, method="PUT", headers=headers,
    )
    with urlopen(req, timeout=60) as response:
        result = json.load(response)
    assert result["sha256"] == sha(raw)
    return {"filename": filename, "sha256": sha(raw)}


def seed_qa_reviewed_model_fixture(base, admin, model_bytes):
    """Use real HTTP endpoints; MODEL QA is explicitly synthetic TEST DATA."""
    maker = register(base, admin, "fixture-model-worker", capability="character_model")
    reviewer = register(base, admin, "fixture-qa-reviewer", role="reviewer")
    _, lease = json_call(base, "/api/media/lease", {"seconds": 120}, token=maker)
    assert lease["status"] == "LEASED"
    assert lease["payload"]["capability"] == "character_model"
    artifact = upload(
        base, maker, lease["job_id"], "aden-character-v1.blend",
        model_bytes, lease_key=lease["lease_key"],
    )
    _, complete = json_call(base, "/api/media/complete", {
        "job_id": lease["job_id"], "lease_key": lease["lease_key"],
        "result": {
            "schema": "ahos.media.result.v1",
            "capability": "character_model",
            "technical_status": "PASSED",
            "new_spend_eur": 0,
            "license_status": "COMMERCIAL_REVIEWED",
            "artifacts": [artifact],
            "creative_approved": False,
            "production_ready": False,
        },
    }, token=maker)
    assert complete["status"] == "AWAITING_QA"
    _, claim = json_call(base, "/api/media/review-claim", {}, token=reviewer)
    assert claim["job_id"] == lease["job_id"]
    proof = json.dumps({
        "TEST_FIXTURE_ONLY": True,
        "not_independent_creative_qa": True,
        "purpose": "unlock the model dependency for isolated rig HTTP test",
    }).encode()
    proof_file = upload(
        base, reviewer, lease["job_id"], "fixture-review.json", proof,
    )
    _, reviewed = json_call(base, "/api/media/review", {
        "job_id": lease["job_id"],
        "result": {
            "schema": "ahos.media.review.v1",
            "method": "independent_multimodal",
            "proof": proof_file,
            "scores": {category: 1.0 for category in FLOORS},
        },
    }, token=reviewer)
    assert reviewed["status"] == "QA_PASS"
    return lease["job_id"]


def test_actual_http_dependency_handoff_to_rig(tmp_path):
    """No Blender needed: real HTTP, SQLite, file transfer, SHA and metadata."""
    root = make_root(tmp_path)
    coordinator = Coordinator(tmp_path / "isolated-oracle", root=root)
    coordinator.enqueue = lambda _episode_id: None
    seed_director(coordinator)
    with http_oracle(coordinator) as base:
        admin = coordinator.media_queue.admin_key.read_text(encoding="ascii").strip()
        # Synthetic BLENDER signature is a protocol fixture, never a real rig.
        seed_qa_reviewed_model_fixture(
            base, admin, b"BLENDER" + b"\0" * 512,
        )
        rig_token = register(base, admin, "rig-worker", capability="rig")
        _, rig_job = json_call(
            base, "/api/media/lease", {"seconds": 120}, token=rig_token,
        )
        assert rig_job["status"] == "LEASED"
        assert rig_job["payload"]["capability"] == "rig"
        dependencies = client.download_dependencies(
            base, rig_token, rig_job["payload"],
            rig_job["job_id"], tmp_path / "worker-job",
        )
        assert len(dependencies) == 1
        item = dependencies[0]
        assert item["kind"] == "character_model"
        assert item["character_id"] == "aden"
        assert item["license_status"] == "verified"
        assert item["source_sha256"] == rig_job["payload"][
            "canonical_reference_sha256"
        ]["aden"]
        assert item["sha256"] == sha(Path(item["path"]).read_bytes())
        model, source, error = resolve_model("aden", {
            "cast": ["aden"], "dependency_artifacts": dependencies,
            "_job_dir": str(tmp_path / "worker-job"),
        })
        assert source == "dependency" and error is None
        assert model == Path(item["path"])
        # Fail closed when the supposedly reviewed source bytes change.
        model.write_bytes(b"tampered")
        _, _, error = resolve_model("aden", {
            "cast": ["aden"], "dependency_artifacts": dependencies,
        })
        assert error == "SHA_MISMATCH"
        assert coordinator.media_queue.status()["production_ready"] is False


@pytest.mark.skipif(
    not find_blender(), reason="Real Blender runtime not installed",
)
def test_real_blender_rig_over_http_stops_at_awaiting_qa(tmp_path):
    """Real Blender + real localhost lease/upload/complete; no creative QA claim."""
    real_model = ROOT / "studio/assets/character-library/aden/v1/aden-character-v1.blend"
    approved_ref = (
        ROOT / "studio/reference/owner_accepted_roster_v1/characters/01_aden.png"
    )
    if not real_model.is_file() or not approved_ref.is_file():
        pytest.skip("Actual Aden model/canonical reference missing")
    model_bytes = real_model.read_bytes()
    assert model_bytes.startswith(b"BLENDER")

    coordinator = Coordinator(tmp_path / "isolated-oracle", root=ROOT)
    coordinator.enqueue = lambda _episode_id: None
    seed_director(coordinator)
    with http_oracle(coordinator) as base:
        admin = coordinator.media_queue.admin_key.read_text(encoding="ascii").strip()
        seed_qa_reviewed_model_fixture(base, admin, model_bytes)
        rig_token = register(base, admin, "actual-blender-rig", capability="rig")
        outcome = client.execute_one(
            base, rig_token, tmp_path / "worker-jobs",
            repo_root=ROOT, max_seconds=1200,
        )
        assert outcome["status"] == "AWAITING_QA", outcome
        with coordinator.media_queue.connect() as db:
            row = db.execute(
                "SELECT job_id,state FROM media_jobs WHERE capability='rig'"
            ).fetchone()
            assert row["state"] == "AWAITING_QA"
            files = db.execute(
                "SELECT filename,sha256,local_path FROM media_artifacts "
                "WHERE job_id=? AND role='worker'", (row["job_id"],),
            ).fetchall()
        assert {x["filename"] for x in files} == {
            "aden-rigged.blend", "aden-rigged.glb", "aden-rig-contract.json",
        }
        for item in files:
            assert sha(Path(item["local_path"]).read_bytes()) == item["sha256"]
        assert coordinator.media_queue.status()["production_ready"] is False
        print("REAL_BLENDER_RIG_HTTP_AWAITING_QA: true")
        print("CREATIVE_QA_APPROVED: false")


def test_rig_requires_explicit_identity_and_editable_blend(tmp_path):
    """A GLB first in the upstream manifest must not be rigged as a BLEND."""
    model = tmp_path / "aden-model.blend"
    glb = tmp_path / "aden-model.glb"
    model.write_bytes(b"BLENDER" + b"x" * 300)
    glb.write_bytes(b"glTF" + b"x" * 300)
    files = [
        {"kind": "character_model", "character_id": "aden",
         "path": str(glb), "sha256": sha(glb.read_bytes()),
         "license_status": "verified"},
        {"kind": "character_model", "character_id": "aden",
         "path": str(model), "sha256": sha(model.read_bytes()),
         "license_status": "verified"},
    ]
    chosen, source, error = resolve_model(
        "aden", {"dependency_artifacts": files},
    )
    assert (chosen, source, error) == (model, "dependency", None)
    no_identity = [{k: v for k, v in d.items() if k != "character_id"}
                   for d in files]
    chosen, _, error = resolve_model(
        "aden", {"dependency_artifacts": no_identity},
    )
    assert chosen is None and error == "DEPENDENCY_UNMATCHED"
    no_license = [dict(files[-1], license_status=None)]
    chosen, _, error = resolve_model(
        "aden", {"dependency_artifacts": no_license},
    )
    assert chosen is None and error == "LICENSE_UNVERIFIED"
