"""AHOS Media Factory worker client — run an authorized existing local backend.

This client connects only via an SSH-forwarded loopback Studio OS API.
It never registers/provisions GPU, downloads model weights or approves media QA.
A backend creates actual artifacts and evidence with the existing dispatcher CLI.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
STAGES={
    "character_model":"character_model",
    "rig":"rig","scene":"scene","animation":"animation","voice":"voice",
    "lipsync":"lipsync","render":"render","qa":"qa",
}
KINDS={
    "character_model":"character_model","rig":"rig","scene":"scene",
    "animation":"animation","voice":"voice","lipsync":"lipsync",
    "render":"film","qa":"quality_report",
}
MAX_FILE=64*1024*1024


class WorkerError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def request_json(server, path, token, data):
    body=json.dumps(data,ensure_ascii=False).encode("utf-8")
    request=Request(server+path,data=body,method="POST",
                    headers={"Content-Type":"application/json",
                             "Authorization":"Bearer "+token})
    try:
        with urlopen(request,timeout=20) as response:
            return json.load(response)
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        raise WorkerError("Studio OS API request failed: "+type(exc).__name__) from exc


def upload_file(server, token, job_id, lease_key, name, data):
    if len(data)>MAX_FILE:
        raise WorkerError("Artifact exceeds 64 MiB. Split into shot segments or add audited object storage.")
    sha=digest(data)
    request=Request(server+"/api/media/artifact",data=data,method="PUT",
                    headers={"Authorization":"Bearer "+token,
                             "Content-Type":"application/octet-stream",
                             "X-AHOS-Job-ID":job_id,"X-AHOS-Lease-Key":lease_key,
                             "X-AHOS-Filename":name,"X-AHOS-SHA256":sha})
    try:
        with urlopen(request,timeout=180) as response:
            ack=json.load(response)
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        raise WorkerError("Media artifact upload failed: "+type(exc).__name__) from exc
    if ack.get("status")!="STORED" or ack.get("sha256")!=sha:
        raise WorkerError("Oracle did not acknowledge exact artifact SHA")
    return {"filename":name,"sha256":sha}


def script_for_capability(capability, root):
    if capability not in STAGES:
        raise WorkerError("No approved local backend for "+str(capability))
    path=root/"studio/pipeline/production-backends.json"
    if not path.is_file():
        raise WorkerError("Backend registry not present")
    registry=json.loads(path.read_text(encoding="utf-8"))
    setup=registry.get("stages",{}).get(capability,{})
    if setup.get("cost_eur")!=0:
        raise WorkerError("Existing backend must prove zero new spending")
    relative=setup.get("script")
    if not isinstance(relative,str) or not re.fullmatch(
            r"tools/studio_backends/[A-Za-z0-9_/-]+\.py",relative):
        raise WorkerError("No reviewed backend script registered")
    script=(root/relative).resolve()
    safe_root=(root/"tools"/"studio_backends").resolve()
    if safe_root not in script.parents or not script.is_file():
        raise WorkerError("Backend script path is missing or unsafe")
    return script


def read_evidence(path, capability, job_dir):
    if not path.is_file():
        raise WorkerError("Backend emitted no evidence.json")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("stage")!=capability or data.get("status")!="PASSED":
        raise WorkerError("Backend did not pass this exact stage")
    if data.get("cost_eur")!=0 or data.get("commercial_license_verified") is not True:
        raise WorkerError("Backend spending or commercial license not proven")
    assets=data.get("artifacts")
    if not isinstance(assets,list) or not assets or len(assets)>30:
        raise WorkerError("Missing real media artifacts")
    results=[]
    for asset in assets:
        if asset.get("kind")!=KINDS[capability]:
            raise WorkerError("Artifact kind mismatch")
        filename=asset.get("path")
        if not isinstance(filename,str):
            raise WorkerError("Artifact has no file path")
        p=Path(filename)
        if p.is_absolute() or ".." in p.parts:
            raise WorkerError("Unsafe artifact path")
        output=(job_dir/p).resolve()
        if job_dir.resolve() not in output.parents or not output.is_file():
            raise WorkerError("Artifact outside the approved job directory")
        if output.stat().st_size>MAX_FILE:
            raise WorkerError("Artifact too large for current Oracle ingest limit")
        raw=output.read_bytes()
        if digest(raw)!=asset.get("sha256"):
            raise WorkerError("Local asset SHA does not match backend evidence")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}",output.name):
            raise WorkerError("Artifact filename not suitable for versioned upload")
        results.append((output.name,raw))
    if len({name for name,_ in results})!=len(results):
        raise WorkerError("Duplicate output names; use unique immutable filenames")
    return results


def execute_one(server, token, job_root, repo_root=ROOT, *, max_seconds=1800):
    if not server.startswith("http://127.0.0.1:") and not server.startswith("http://localhost:"):
        raise WorkerError("Only SSH loopback-forwarded coordinator is permitted")
    assignment=request_json(server,"/api/media/lease",token,{"seconds":120})
    if assignment.get("status")!="LEASED":
        return {"status":assignment.get("status","NO_WORK")}
    jid=assignment["job_id"]
    lease=assignment["lease_key"]
    payload=assignment["payload"]
    try:
        capability=payload["capability"]
        script=script_for_capability(capability,repo_root)
        dirname=Path(job_root)/jid
        dirname.mkdir(parents=True,exist_ok=True)
        plan=dirname/"production-plan.json"
        plan.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        evidence=dirname/"backend-evidence.json"
        argv=[sys.executable,str(script),"--plan",str(plan),
              "--job-dir",str(dirname),"--evidence",str(evidence)]
        # Never use unconsumed PIPE streams: large Blender stdout could deadlock.
        logs=dirname/"backend-run.log"
        with logs.open("wb") as log:
            process=subprocess.Popen(argv,cwd=repo_root,stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+max_seconds
            while process.poll() is None:
                if time.monotonic()>deadline:
                    process.kill()
                    process.wait(timeout=15)
                    raise WorkerError("Production stage time budget exceeded")
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    try:
                        request_json(server,"/api/media/heartbeat",token,
                                     {"job_id":jid,"lease_key":lease,"seconds":120})
                    except WorkerError:
                        process.kill()
                        process.wait(timeout=15)
                        raise
        if process.returncode!=0:
            with logs.open("rb") as fd:
                fd.seek(max(0,logs.stat().st_size-1000))
                tail=fd.read().decode("utf-8",errors="replace")
            raise WorkerError("Backend exit="+str(process.returncode)+", "+tail[-400:])
        outputs=read_evidence(evidence,capability,dirname)
        submitted=[upload_file(server,token,jid,lease,name,raw) for name,raw in outputs]
        manifest={
            "schema":"ahos.media.result.v1",
            "capability":capability,
            "technical_status":"PASSED",
            "new_spend_eur":0,
            "license_status":"COMMERCIAL_REVIEWED",
            "artifacts":submitted,
            "creative_approved":False,"production_ready":False,
        }
        return request_json(server,"/api/media/complete",token,
                            {"job_id":jid,"lease_key":lease,"result":manifest})
    except (WorkerError,KeyError,ValueError,OSError,subprocess.TimeoutExpired) as exc:
        try:
            response=request_json(server,"/api/media/fail",token,
                                  {"job_id":jid,"lease_key":lease,
                                   "reason":(type(exc).__name__+": "+str(exc))[:280]})
        except WorkerError:
            response={"status":"LEASE_OR_API_FAILURE"}
        return {"status":"FAILED","job_id":jid,"reason":str(exc)[:300],
                "queue_response":response,"production_ready":False}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--server",default="http://127.0.0.1:8801")
    p.add_argument("--job-root",type=Path,required=True)
    p.add_argument("--repo-root",type=Path,default=ROOT)
    p.add_argument("--max-seconds",type=int,default=1800)
    args=p.parse_args(argv)
    secret=os.environ.get("AHOS_MEDIA_WORKER_TOKEN")
    if not secret:
        raise SystemExit("Worker token absent. It must be injected privately from the approved worker registry.")
    outcome=execute_one(args.server,secret,args.job_root,args.repo_root,
                        max_seconds=args.max_seconds)
    print(json.dumps(outcome,ensure_ascii=False,indent=2))
    return 0 if outcome["status"] in ("NO_COMPATIBLE_WORK","AWAITING_QA") else 2


if __name__=="__main__":
    raise SystemExit(main())
