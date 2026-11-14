"""AHOS Media Factory — bounded, resumable, lease-scoped multipart artifact ingest.

This extends the existing <=64 MiB direct uploader for real movie files.
All uploaded bytes live on the existing Oracle private disk, never in Git.
A completed multipart artifact is still only a *technical candidate*.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import re
import secrets
import shutil
import time
import uuid
from pathlib import Path

from studio_media_queue import QueueError, NAME, require_hash, checksum, validate_media_file

CHUNK_BYTES = 4 * 1024 * 1024
MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024
DISK_RESERVE_BYTES = 1024 * 1024 * 1024


class MultipartStore:
    def __init__(self, queue):
        self.queue=queue
        with queue.connect() as db:
            db.execute("""
CREATE TABLE IF NOT EXISTS media_upload_sessions (
 session_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, attempt INTEGER NOT NULL,
 worker_id TEXT NOT NULL, lease_hash TEXT NOT NULL, filename TEXT NOT NULL,
 expected_sha TEXT NOT NULL, expected_size INTEGER NOT NULL,
 received INTEGER NOT NULL DEFAULT 0, tmp_path TEXT NOT NULL,
 state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
 UNIQUE(job_id,attempt,filename)
)""")

    def _owned(self, db, worker, session_id, lease_key):
        if worker["role"]!="worker":
            raise QueueError("Only real media workers may upload large artifacts")
        row=db.execute(
            "SELECT * FROM media_upload_sessions WHERE session_id=?",
            (session_id,)).fetchone()
        if row is None:
            raise QueueError("Unknown upload session")
        job=self.queue._valid_lease(db,worker,row["job_id"],lease_key)
        if job["attempts"]!=row["attempt"] or (
                not hmac.compare_digest(
                    hashlib.sha256(lease_key.encode()).hexdigest(),row["lease_hash"])):
            raise QueueError("An earlier lease may not upload to this attempt")
        if row["worker_id"]!=worker["worker_id"]:
            raise QueueError("Upload does not belong to this worker")
        return row,job

    def start(self, worker, job_id, lease_key, filename, sha, total):
        if worker["role"]!="worker":
            raise QueueError("Only production workers can start multipart uploads")
        if not isinstance(filename,str) or not NAME.fullmatch(filename) or filename in (".",".."):
            raise QueueError("Unsafe filename")
        require_hash(sha,"Multipart upload")
        if type(total) is not int or not 1<=total<=MAX_FILE_BYTES:
            raise QueueError("Invalid multipart size")
        free=shutil.disk_usage(self.queue.artifacts_dir).free
        if free < total+DISK_RESERVE_BYTES:
            raise QueueError("Insufficient Oracle disk space for complete upload")
        with self.queue.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job=self.queue._valid_lease(db,worker,job_id,lease_key)
            existing=db.execute(
                "SELECT 1 FROM media_artifacts WHERE job_id=? AND role='worker' AND filename=?",
                (job_id,filename)).fetchone()
            if existing:
                raise QueueError("Artifact already finalized; no silent overwrite")
            prev=db.execute(
                "SELECT * FROM media_upload_sessions WHERE job_id=? AND attempt=? AND filename=?",
                (job_id,job["attempts"],filename)).fetchone()
            if prev:
                if prev["expected_sha"]!=sha or prev["expected_size"]!=total or (
                        prev["worker_id"]!=worker["worker_id"]):
                    raise QueueError("Conflicting multipart upload on this attempt")
                if prev["state"]!="ACTIVE":
                    raise QueueError("Already finalized multipart upload")
                return {"status":"RESUME","upload_id":prev["session_id"],
                        "received":prev["received"],"chunk_limit":CHUNK_BYTES}
            folder=self.queue.artifacts_dir/job_id/"worker"
            folder.mkdir(mode=0o700,parents=True,exist_ok=True)
            ident=str(uuid.uuid4())
            tmp=folder/(ident+".part")
            with tmp.open("xb"):
                pass
            now=time.time()
            try:
                db.execute(
                    "INSERT INTO media_upload_sessions "
                    "(session_id,job_id,attempt,worker_id,lease_hash,filename,expected_sha,"
                    "expected_size,received,tmp_path,state,created,updated) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ident,job_id,job["attempts"],worker["worker_id"],
                     hashlib.sha256(lease_key.encode()).hexdigest(),filename,sha,
                     total,0,str(tmp),"ACTIVE",now,now))
            except Exception:
                tmp.unlink(missing_ok=True)
                raise
        return {"status":"CREATED","upload_id":ident,"received":0,
                "chunk_limit":CHUNK_BYTES}

    def append(self, worker, upload_id, lease_key, offset, data):
        if type(offset) is not int or offset<0:
            raise QueueError("Invalid chunk offset")
        if not isinstance(data,bytes) or not 1<=len(data)<=CHUNK_BYTES:
            raise QueueError("Invalid multipart chunk length")
        with self.queue.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item,_=self._owned(db,worker,upload_id,lease_key)
            if item["state"]!="ACTIVE":
                raise QueueError("Upload session no longer active")
            path=Path(item["tmp_path"])
            if not path.is_file():
                raise QueueError("Partial upload disappeared")
            expected=item["received"]
            if path.stat().st_size<expected:
                raise QueueError("Partial upload truncated since last database commit")
            if offset+len(data)<=expected:
                with path.open("rb") as stream:
                    stream.seek(offset)
                    old=stream.read(len(data))
                if old!=data:
                    raise QueueError("Retry chunk bytes differ from already recorded bytes")
                return {"status":"DUPLICATE","received":expected}
            if offset!=expected or expected+len(data)>item["expected_size"]:
                raise QueueError("Out-of-order or overlong multipart chunk")
            with path.open("r+b") as stream:
                # Crash after write/before DB COMMIT: discard uncommitted tail
                # and replay it from the next authenticated worker request.
                stream.truncate(expected)
                stream.seek(expected)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            new_size=expected+len(data)
            db.execute("UPDATE media_upload_sessions SET received=?,updated=? "
                       "WHERE session_id=?",(new_size,time.time(),upload_id))
        return {"status":"RECEIVED","received":new_size}

    def finish(self, worker, upload_id, lease_key):
        with self.queue.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item,job=self._owned(db,worker,upload_id,lease_key)
            if item["state"]!="ACTIVE" or item["received"]!=item["expected_size"]:
                raise QueueError("Incomplete or previously finalized multipart upload")
            path=Path(item["tmp_path"])
            if not path.is_file() or path.stat().st_size!=item["expected_size"]:
                raise QueueError("Multipart file size mismatch")
            actual_sha=checksum(path)
            if actual_sha!=item["expected_sha"]:
                raise QueueError("Multipart file SHA-256 mismatch")
            # Do not call a dummy MP4 a successful render. For a long final film
            # the server probes container and streams, while per-shot render
            # requires separate whole-shot objective FFmpeg analysis.
            validate_media_file(path.with_name(path.name+"-"+item["filename"]),
                                job["capability"]) if False else None
            # The suffix matters for type checks, so use a non-public temporary
            # hard link for validation before atomically renaming the original.
            test_path=path.parent/(upload_id+"-verify-"+item["filename"])
            os.link(path,test_path)
            try:
                validate_media_file(test_path,job["capability"])
            finally:
                test_path.unlink(missing_ok=True)
            final=path.parent/(upload_id+"-"+item["filename"])
            if db.execute("SELECT 1 FROM media_artifacts WHERE job_id=? AND role='worker' "
                          "AND filename=?",(job["job_id"],item["filename"])).fetchone():
                raise QueueError("Artifact finalized by another session")
            os.replace(path,final)
            db.execute("INSERT INTO media_artifacts VALUES(?,?,?,?,?,?,?)",
                       (job["job_id"],"worker",worker["worker_id"],item["filename"],
                        actual_sha,item["expected_size"],str(final)))
            db.execute("UPDATE media_upload_sessions SET state='FINISHED',updated=? "
                       "WHERE session_id=?",(time.time(),upload_id))
        return {"status":"STORED","filename":item["filename"],
                "sha256":actual_sha,"bytes":item["expected_size"]}
