"""AHOS Media Factory — crash-safe job leasing and evidence-gated media work.

A single Oracle-hosted StudioOS owns this SQLite WAL database.
GPU/media workers connect through authorized SSH local forwarding; not a public API.
This is transport/scheduling infrastructure, NOT a verified film production engine.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import secrets
import sqlite3
import time
import uuid
from pathlib import Path

MEDIA_KINDS = frozenset(("model", "rig", "set", "animation", "voice",
                         "lipsync", "render", "scene_qa", "edit", "episode_qa"))
MEDIA_CAPS = frozenset(("character_model", "rig", "scene", "animation", "voice",
                        "lipsync", "render", "qa", "editing"))
DONE_DEPS = frozenset(("DONE_VERIFIED", "DONE_DRAFT"))
MAX_UPLOAD = 64 * 1024 * 1024
MAX_ATTEMPTS = 3
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
FLOORS = {"identity": .95, "acting": .85, "motion": .88,
          "continuity": .93, "cinematography": .88, "story_adherence": .90,
          "audio": .90, "child_safety": 1., "rights": 1.}


class QueueError(ValueError):
    pass


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def require_hash(value, what):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise QueueError(what + ": valid lowercase SHA-256 required")


ARTIFACT_SUFFIXES = {
    "character_model": (".blend", ".glb"),
    "rig": (".blend", ".glb"),
    "scene": (".blend", ".glb"),
    "animation": (".blend", ".glb", ".fbx", ".mp4"),
    "voice": (".wav",),
    "lipsync": (".json",),
    "render": (".mp4",),
    "qa": (".json",),
    "editing": (".mp4",),
}


def validate_media_file(path, capability):
    """Validate actual media type and duration where codecs allow it."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in ARTIFACT_SUFFIXES.get(capability, ()):
        raise QueueError("Wrong media artifact extension for capability")
    if path.stat().st_size < (100000 if ext == ".mp4" else 100 if ext not in (".json",) else 15):
        raise QueueError("Media file trivially small")
    with path.open("rb") as f:
        head = f.read(12)
    if ext == ".blend" and not head.startswith(b"BLENDER"):
        raise QueueError("Not an authentic Blender container")
    if ext == ".glb" and not head.startswith(b"glTF"):
        raise QueueError("Not a valid GLB container")
    if ext == ".png" and not head.startswith(b"\x89PNG\r\n\x1a\n"):
        raise QueueError("Not a PNG file")
    if ext == ".wav" and not (head.startswith(b"RIFF") and head[8:12] == b"WAVE"):
        raise QueueError("Not a WAV file")
    if ext == ".mp4":
        if head[4:8] != b"ftyp":
            raise QueueError("Not an MP4 container")
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise QueueError("ffprobe must verify real audio/video before technical completion")
        try:
            output = subprocess.run(
                [ffprobe,"-v","error","-show_entries",
                 "format=duration:stream=codec_type,width,height,r_frame_rate",
                 "-of","json",str(path)],
                capture_output=True,text=True,timeout=30,check=True)
            meta = json.loads(output.stdout)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError) as exc:
            raise QueueError("MP4 codec integrity check failed") from exc
        video = [x for x in meta.get("streams",[]) if x.get("codec_type")=="video"]
        audio = [x for x in meta.get("streams",[]) if x.get("codec_type")=="audio"]
        if not video or not audio or float(meta.get("format",{}).get("duration",0)) < 1:
            raise QueueError("Real video + audio duration required")
        if video[0].get("width",0) < 1280 or video[0].get("height",0) < 720:
            raise QueueError("Video falls below initial review resolution")
    if ext == ".json":
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError) as exc:
            raise QueueError("Malformed JSON evidence") from exc
        if not isinstance(obj,(dict,list)):
            raise QueueError("JSON evidence must have meaningful structure")


class MediaQueue:
    def __init__(self, studio_os, state_dir):
        self.os = studio_os
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir = self.state_dir / "media-artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.admin_key = self.state_dir / "media-queue-admin.key"
        if not self.admin_key.exists():
            try:
                fd = os.open(str(self.admin_key), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w", encoding="ascii") as handle:
                    handle.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
        self.init_schema()

    def connect(self):
        return self.os.connect()

    def admin_authorized(self, token):
        if not isinstance(token, str) or len(token) < 32:
            return False
        return hmac.compare_digest(token, self.admin_key.read_text(encoding="ascii").strip())

    def init_schema(self):
        with self.connect() as db:
            db.executescript("""
CREATE TABLE IF NOT EXISTS media_workers (
  worker_id TEXT PRIMARY KEY, role TEXT NOT NULL, token_sha TEXT NOT NULL UNIQUE,
  capabilities TEXT NOT NULL, runtime_sha TEXT NOT NULL, region TEXT NOT NULL,
  state TEXT NOT NULL, last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS media_jobs (
  job_id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, task_id TEXT NOT NULL,
  capability TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, worker_id TEXT, lease_key TEXT,
  lease_until REAL, reviewer_id TEXT, review_until REAL,
  result TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL, updated REAL NOT NULL,
  UNIQUE (episode_id, task_id)
);
CREATE INDEX IF NOT EXISTS media_jobs_state ON media_jobs(state, capability, created);
CREATE TABLE IF NOT EXISTS media_artifacts (
  job_id TEXT NOT NULL, role TEXT NOT NULL, uploader_id TEXT NOT NULL,
  filename TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL,
  local_path TEXT NOT NULL, PRIMARY KEY(job_id,role,filename)
);
CREATE TABLE IF NOT EXISTS media_events (
  at REAL NOT NULL, job_id TEXT NOT NULL, event TEXT NOT NULL,
  actor TEXT NOT NULL, details TEXT NOT NULL
);
""")

    def register(self, info):
        worker_id = info.get("worker_id")
        role = info.get("role", "worker")
        caps = info.get("capabilities", [])
        if not isinstance(worker_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{3,60}", worker_id):
            raise QueueError("Invalid worker_id")
        if role not in ("worker", "reviewer"):
            raise QueueError("Invalid role")
        if not isinstance(caps, list) or any(c not in MEDIA_CAPS for c in caps):
            raise QueueError("Invalid media capabilities")
        if role == "worker" and not caps:
            raise QueueError("Worker needs at least one real media capability")
        require_hash(info.get("runtime_proof_sha256"), "Runtime")
        if info.get("license_status") != "COMMERCIAL_REVIEWED":
            raise QueueError("Commercial license review not verified")
        if info.get("runtime_status") != "VERIFIED_RUNTIME":
            raise QueueError("Real execution proof is mandatory")
        if info.get("region") != "EU" or info.get("new_spend_eur") != 0:
            raise QueueError("EU permission and zero new spending required")
        token = secrets.token_urlsafe(48)
        with self.connect() as db:
            try:
                db.execute(
                    "INSERT INTO media_workers VALUES(?,?,?,?,?,?,?,?)",
                    (worker_id, role, hashlib.sha256(token.encode()).hexdigest(),
                     json.dumps(caps), info["runtime_proof_sha256"], "EU", "ACTIVE", time.time()))
            except sqlite3.IntegrityError as exc:
                raise QueueError("Worker already registered; no silent replacement") from exc
        return {"worker_id": worker_id, "role": role, "worker_token": token}

    def auth(self, token, role=None):
        if not isinstance(token, str) or len(token) < 32:
            raise QueueError("Worker token missing")
        with self.connect() as db:
            row = db.execute("SELECT * FROM media_workers WHERE token_sha=? AND state='ACTIVE'",
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:
            raise QueueError("Invalid worker token")
        result = dict(row)
        if role and result["role"] != role:
            raise QueueError("Wrong worker role")
        result["capabilities"] = json.loads(result.pop("capabilities"))
        result.pop("token_sha")
        return result

    def sync_ready(self):
        """Create only dependency-ready media jobs. No extra StudioOS tasks added."""
        count = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT t.*,e.plan_json FROM tasks t JOIN episodes e ON t.episode_id=e.id "
                "WHERE t.state IN ('PENDING','WAITING_PROVIDER','READY')"
            ).fetchall()
            for t in rows:
                if t["kind"] not in MEDIA_KINDS:
                    continue
                if db.execute("SELECT 1 FROM media_jobs WHERE episode_id=? AND task_id=?",
                              (t["episode_id"], t["task_id"])).fetchone():
                    continue
                deps = json.loads(t["depends_json"])
                if deps:
                    placeholders = ",".join("?" * len(deps))
                    found = db.execute(
                        f"SELECT task_id,state FROM tasks WHERE episode_id=? AND task_id IN ({placeholders})",
                        (t["episode_id"], *deps)).fetchall()
                    if len(found) != len(deps) or any(x["state"] not in DONE_DEPS for x in found):
                        continue
                p = json.loads(t["plan_json"])
                job = {"schema": "ahos.media.job.v1", "episode_id": t["episode_id"],
                       "task_id": t["task_id"], "capability": t["capability"],
                       "kind": t["kind"], "series_id": p["series_id"],
                       "cast": p["cast"], "languages": p["languages"],
                       "story_direction": p["owner_prompt"],
                       "dependencies": deps, "cost_policy": p["cost_policy"],
                       "production_ready": False}
                now = time.time()
                db.execute(
                    "INSERT INTO media_jobs(job_id,episode_id,task_id,capability,payload,state,created,updated)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (str(uuid.uuid4()),t["episode_id"],t["task_id"],t["capability"],
                     json.dumps(job,ensure_ascii=False),"QUEUED",now,now))
                db.execute("UPDATE tasks SET state='READY' WHERE episode_id=? AND task_id=?",
                           (t["episode_id"],t["task_id"]))
                count += 1
        return count

    def _recover(self, db, now):
        expired = db.execute(
            "SELECT * FROM media_jobs WHERE (state='LEASED' AND lease_until<?) "
            "OR (state='REVIEWING' AND review_until<?)",(now,now)).fetchall()
        for job in expired:
            if job["state"] == "REVIEWING":
                db.execute("UPDATE media_jobs SET state='AWAITING_QA',reviewer_id=NULL,"
                           "review_until=NULL WHERE job_id=?", (job["job_id"],))
                continue
            state = "BLOCKED" if job["attempts"] >= MAX_ATTEMPTS else "QUEUED"
            db.execute("UPDATE media_jobs SET state=?,worker_id=NULL,lease_key=NULL,"
                       "lease_until=NULL,updated=? WHERE job_id=?", (state,now,job["job_id"]))
            db.execute("UPDATE tasks SET state=? WHERE episode_id=? AND task_id=?",
                       ("BLOCKED" if state=="BLOCKED" else "READY",
                        job["episode_id"],job["task_id"]))
            db.execute("INSERT INTO media_events VALUES(?,?,?,?,?)",
                       (now,job["job_id"],"LEASE_EXPIRED",job["worker_id"] or "",state))

    def lease(self, worker, seconds=120):
        if worker["role"] != "worker":
            raise QueueError("Reviewers do not run media jobs")
        if type(seconds) is not int or not 30 <= seconds <= 900:
            raise QueueError("Lease must be 30-900 seconds")
        self.sync_ready()
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._recover(db,now)
            active = db.execute(
                "SELECT job_id FROM media_jobs WHERE state='LEASED' AND worker_id=?",
                (worker["worker_id"],)).fetchone()
            if active:
                return {"status":"WORKER_BUSY","job_id":active["job_id"]}
            caps = worker["capabilities"]
            if not caps:
                return {"status":"NO_COMPATIBLE_WORK"}
            args = ",".join("?" * len(caps))
            job = db.execute(
                f"SELECT * FROM media_jobs WHERE state='QUEUED' AND attempts<? "
                f"AND capability IN ({args}) ORDER BY created LIMIT 1",
                (MAX_ATTEMPTS,*caps)).fetchone()
            if job is None:
                return {"status":"NO_COMPATIBLE_WORK"}
            lease_key = secrets.token_urlsafe(32)
            db.execute("UPDATE media_jobs SET state='LEASED',worker_id=?,lease_key=?,"
                       "lease_until=?,attempts=attempts+1,updated=? WHERE job_id=?",
                       (worker["worker_id"],lease_key,now+seconds,now,job["job_id"]))
            db.execute("UPDATE tasks SET state='RUNNING' WHERE episode_id=? AND task_id=?",
                       (job["episode_id"],job["task_id"]))
        return {"status":"LEASED","job_id":job["job_id"],"lease_key":lease_key,
                "attempt":job["attempts"]+1,"lease_seconds":seconds,
                "payload":json.loads(job["payload"])}

    def _valid_lease(self, db, worker, job_id, lease_key):
        job = db.execute("SELECT * FROM media_jobs WHERE job_id=?",(job_id,)).fetchone()
        if not job or job["state"]!="LEASED" or job["worker_id"]!=worker["worker_id"]:
            raise QueueError("Job not leased to this worker")
        if not isinstance(lease_key,str) or not hmac.compare_digest(job["lease_key"] or "",lease_key):
            raise QueueError("Invalid lease key")
        if job["lease_until"] < time.time():
            raise QueueError("Lease expired")
        return job

    def heartbeat(self, worker, job_id, lease_key, seconds=120):
        if type(seconds) is not int or not 30 <= seconds <= 900:
            raise QueueError("Invalid heartbeat duration")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._valid_lease(db,worker,job_id,lease_key)
            expiry = time.time()+seconds
            db.execute("UPDATE media_jobs SET lease_until=?,updated=? WHERE job_id=?",
                       (expiry,time.time(),job_id))
        return {"status":"LEASED","lease_until":expiry}

    def review_claim(self, reviewer):
        if reviewer["role"]!="reviewer":
            raise QueueError("Review role required")
        now = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._recover(db,now)
            job = db.execute("SELECT * FROM media_jobs WHERE state='AWAITING_QA' "
                             "AND worker_id!=? ORDER BY created LIMIT 1",
                             (reviewer["worker_id"],)).fetchone()
            if job is None:
                return {"status":"NO_REVIEW_WORK"}
            db.execute("UPDATE media_jobs SET state='REVIEWING',reviewer_id=?,"
                       "review_until=? WHERE job_id=?",
                       (reviewer["worker_id"],now+900,job["job_id"]))
            items = db.execute("SELECT filename,sha256,bytes FROM media_artifacts "
                               "WHERE job_id=? AND role='worker'",(job["job_id"],)).fetchall()
        return {"status":"REVIEWING","job_id":job["job_id"],
                "payload":json.loads(job["payload"]),
                "result":json.loads(job["result"]),
                "artifacts":[dict(x) for x in items]}

    def upload(self, worker, job_id, filename, declared_sha, data, lease_key=None):
        """Store real bytes in Oracle private artifact cache, max 64 MiB per call."""
        if not isinstance(filename,str) or not NAME.fullmatch(filename) or filename in (".",".."):
            raise QueueError("Unsafe artifact filename")
        require_hash(declared_sha,"Upload")
        if not isinstance(data,bytes) or not 1 <= len(data) <= MAX_UPLOAD:
            raise QueueError("Artifact size invalid")
        if hashlib.sha256(data).hexdigest()!=declared_sha:
            raise QueueError("Artifact bytes/hash mismatch")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT * FROM media_jobs WHERE job_id=?",(job_id,)).fetchone()
            if not job:
                raise QueueError("Unknown job")
            if worker["role"]=="worker":
                self._valid_lease(db,worker,job_id,lease_key)
            elif not (job["state"]=="REVIEWING" and
                      job["reviewer_id"]==worker["worker_id"] and
                      job["review_until"]>time.time()):
                raise QueueError("Reviewer must claim review first")
            role=worker["role"]
            if db.execute("SELECT 1 FROM media_artifacts WHERE job_id=? AND role=? AND filename=?",
                          (job_id,role,filename)).fetchone():
                raise QueueError("Artifact name already used; choose next version")
            folder = self.artifacts_dir / job_id / role
            folder.mkdir(parents=True,exist_ok=True)
            path = folder / (uuid.uuid4().hex+"-"+filename)
            with path.open("xb") as fd:
                fd.write(data)
            db.execute("INSERT INTO media_artifacts VALUES(?,?,?,?,?,?,?)",
                       (job_id,role,worker["worker_id"],filename,declared_sha,
                        len(data),str(path)))
        return {"status":"STORED","filename":filename,"sha256":declared_sha,
                "bytes":len(data)}

    def complete(self, worker, job_id, lease_key, result):
        if not isinstance(result,dict) or result.get("schema")!="ahos.media.result.v1":
            raise QueueError("Result schema invalid")
        if result.get("technical_status")!="PASSED":
            raise QueueError("Failed stage must use explicit failure")
        if result.get("new_spend_eur")!=0 or result.get("license_status")!="COMMERCIAL_REVIEWED":
            raise QueueError("New spending or unverified rights blocked")
        files=result.get("artifacts")
        if not isinstance(files,list) or not 1<=len(files)<=30:
            raise QueueError("At least one real artifact required")
        now=time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job=self._valid_lease(db,worker,job_id,lease_key)
            if result.get("capability")!=job["capability"]:
                raise QueueError("Media result capability does not match leased task")
            for item in files:
                if not isinstance(item,dict):
                    raise QueueError("Invalid artifact")
                digest=item.get("sha256")
                require_hash(digest,"Artifact")
                match=db.execute(
                    "SELECT * FROM media_artifacts WHERE job_id=? AND role='worker' "
                    "AND uploader_id=? AND filename=?",
                    (job_id,worker["worker_id"],item.get("filename"))).fetchone()
                if not match or match["sha256"]!=digest:
                    raise QueueError("Artifact was not uploaded by this worker")
                path=Path(match["local_path"])
                if not path.is_file() or path.stat().st_size!=match["bytes"] or checksum(path)!=digest:
                    raise QueueError("Artifact is missing or modified")
                validate_media_file(path,job["capability"])
            db.execute("UPDATE media_jobs SET state='AWAITING_QA',lease_key=NULL,"
                       "lease_until=NULL,result=?,updated=? WHERE job_id=?",
                       (json.dumps(result,ensure_ascii=False),now,job_id))
            db.execute("UPDATE tasks SET state='AWAITING_QA' WHERE episode_id=? AND task_id=?",
                       (job["episode_id"],job["task_id"]))
        return {"status":"AWAITING_QA","production_ready":False}

    def review(self, reviewer, job_id, result):
        if reviewer["role"]!="reviewer" or not isinstance(result,dict):
            raise QueueError("Independent reviewer required")
        if result.get("schema")!="ahos.media.review.v1" or result.get("method") not in (
                "human_frame_audio_review","independent_multimodal"):
            raise QueueError("Independent creative QA proof required")
        scores=result.get("scores")
        if not isinstance(scores,dict) or set(scores)!=set(FLOORS):
            raise QueueError("Nine QA categories required")
        if any(type(value) not in (int,float) or not 0<=value<=1 for value in scores.values()):
            raise QueueError("Invalid QA score")
        proof=result.get("proof",{})
        if not isinstance(proof,dict):
            raise QueueError("Reviewer proof missing")
        require_hash(proof.get("sha256"),"Review proof")
        failures={key:{"score":scores[key],"floor":min_score}
                  for key,min_score in FLOORS.items() if scores[key]<min_score}
        now=time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job=db.execute("SELECT * FROM media_jobs WHERE job_id=?",(job_id,)).fetchone()
            if not job or job["state"]!="REVIEWING" or job["reviewer_id"]!=reviewer["worker_id"]:
                raise QueueError("Review not claimed")
            if job["review_until"]<now or job["worker_id"]==reviewer["worker_id"]:
                raise QueueError("Reviewer lease expired or self-review")
            file=db.execute("SELECT * FROM media_artifacts WHERE job_id=? AND role='reviewer' "
                            "AND uploader_id=? AND filename=?",
                            (job_id,reviewer["worker_id"],proof.get("filename"))).fetchone()
            if not file or file["sha256"]!=proof["sha256"] or (
                not Path(file["local_path"]).is_file()) or (
                checksum(file["local_path"])!=proof["sha256"]):
                raise QueueError("Independent reviewer artifact missing")
            if failures:
                state="BLOCKED" if job["attempts"]>=MAX_ATTEMPTS else "QUEUED"
                task_state="BLOCKED" if state=="BLOCKED" else "READY"
            else:
                state,task_state="QA_PASS","DONE_VERIFIED"
            db.execute("UPDATE media_jobs SET state=?,worker_id=NULL,lease_key=NULL,"
                       "lease_until=NULL,reviewer_id=NULL,review_until=NULL,result=?,updated=? "
                       "WHERE job_id=?",
                       (state,json.dumps({"production":json.loads(job["result"]),
                        "review":result,"failures":failures},ensure_ascii=False),now,job_id))
            db.execute("UPDATE tasks SET state=? WHERE episode_id=? AND task_id=?",
                       (task_state,job["episode_id"],job["task_id"]))
            db.execute("INSERT INTO media_events VALUES(?,?,?,?,?)",
                       (now,job_id,"QA_FAILED" if failures else "QA_PASS",
                        reviewer["worker_id"],json.dumps(failures)))
        return {"status":state,"failures":failures,"production_ready":False}

    def fail(self, worker, job_id, lease_key, reason):
        if not isinstance(reason,str) or not 5<=len(reason)<=300:
            raise QueueError("Explicit failure reason required")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job=self._valid_lease(db,worker,job_id,lease_key)
            state="BLOCKED" if job["attempts"]>=MAX_ATTEMPTS else "QUEUED"
            db.execute("UPDATE media_jobs SET state=?,worker_id=NULL,lease_key=NULL,"
                       "lease_until=NULL WHERE job_id=?",(state,job_id))
            db.execute("UPDATE tasks SET state=? WHERE episode_id=? AND task_id=?",
                       ("BLOCKED" if state=="BLOCKED" else "READY",
                        job["episode_id"],job["task_id"]))
            db.execute("INSERT INTO media_events VALUES(?,?,?,?,?)",
                       (time.time(),job_id,"FAILED",worker["worker_id"],reason))
        return {"status":state,"production_ready":False}

    def artifact_for_review(self, reviewer, job_id, filename):
        if reviewer["role"] != "reviewer":
            raise QueueError("Reviewer role required")
        with self.connect() as db:
            job = db.execute("SELECT * FROM media_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not job or job["state"] != "REVIEWING" or job["reviewer_id"] != reviewer["worker_id"]:
                raise QueueError("Review claim required to read media artifact")
            if job["review_until"] <= time.time():
                raise QueueError("Review lease expired")
            item = db.execute("SELECT * FROM media_artifacts WHERE job_id=? AND role='worker' "
                              "AND filename=?", (job_id, filename)).fetchone()
            if not item:
                raise QueueError("Artifact not found")
            path = Path(item["local_path"])
            if not path.is_file() or path.stat().st_size != item["bytes"] or checksum(path) != item["sha256"]:
                raise QueueError("Stored artifact changed or disappeared")
            return path, item["sha256"], item["bytes"]

    def status(self):
        with self.connect() as db:
            jobs=db.execute("SELECT state,COUNT(*) n FROM media_jobs GROUP BY state").fetchall()
            workers=db.execute("SELECT worker_id,role,capabilities,state FROM media_workers").fetchall()
        return {"schema":"ahos.media.queue-status.v1",
                "jobs":{row["state"]:row["n"] for row in jobs},
                "workers":[{"worker_id":w["worker_id"],"role":w["role"],
                            "capabilities":json.loads(w["capabilities"]),
                            "state":w["state"]} for w in workers],
                "production_ready":False}
