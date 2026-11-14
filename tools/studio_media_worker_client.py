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
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from studio_media_multipart import CHUNK_BYTES,MAX_FILE_BYTES

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


def upload_large_file(server, token, job_id, lease_key, name, path):
    """Bounded multipart upload for a real >64MiB artifact, no whole-file RAM load."""
    path=Path(path)
    total=path.stat().st_size
    if not MAX_FILE<total<=MAX_FILE_BYTES:
        raise WorkerError("Not a supported large artifact size")
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(CHUNK_BYTES),b""):
            h.update(chunk)
    expected=h.hexdigest()
    started=request_json(server,"/api/media/uploads/start",token,{
        "job_id":job_id,"lease_key":lease_key,"filename":name,
        "sha256":expected,"size_bytes":total})
    upload_id=started.get("upload_id")
    if not isinstance(upload_id,str) or not re.fullmatch(r"[a-f0-9-]{36}",upload_id):
        raise WorkerError("Oracle did not return a valid upload session")
    received=started.get("received")
    if type(received) is not int or not 0<=received<=total:
        raise WorkerError("Oracle returned an invalid resume offset")
    last_heartbeat=time.monotonic()
    with path.open("rb") as stream:
        stream.seek(received)
        while received<total:
            chunk=stream.read(min(CHUNK_BYTES,total-received))
            req=Request(server+"/api/media/uploads/"+upload_id,
                        data=chunk,method="PUT",
                        headers={"Authorization":"Bearer "+token,
                                 "Content-Type":"application/octet-stream",
                                 "X-AHOS-Lease-Key":lease_key,
                                 "X-AHOS-Offset":str(received)})
            try:
                with urlopen(req,timeout=180) as response:
                    acknowledgement=json.load(response)
            except (HTTPError,URLError,TimeoutError,ValueError) as exc:
                raise WorkerError("Multipart chunk upload failed: "+type(exc).__name__) from exc
            next_offset=acknowledgement.get("received")
            if next_offset!=received+len(chunk):
                raise WorkerError("Oracle acknowledged an unexpected chunk offset")
            received=next_offset
            if time.monotonic()-last_heartbeat>=30:
                request_json(server,"/api/media/heartbeat",token,{
                    "job_id":job_id,"lease_key":lease_key,"seconds":120})
                last_heartbeat=time.monotonic()
    completed=request_json(server,"/api/media/uploads/"+upload_id+"/finish",token,{
        "job_id":job_id,"lease_key":lease_key})
    if completed.get("status")!="STORED" or completed.get("sha256")!=expected or completed.get("bytes")!=total:
        raise WorkerError("Oracle did not confirm whole-file SHA/size")
    return {"filename":name,"sha256":expected}


def download_canon(server, token, payload, job_dir):
    """Fetch the exact owner-approved PNG bytes through a job-scoped SSH API."""
    locks=payload.get("canonical_reference_sha256")
    cast=payload.get("cast")
    if not isinstance(locks,dict) or not isinstance(cast,list) or not cast:
        raise WorkerError("Media job lacks accepted canonical reference locks")
    out_dir=Path(job_dir)/"references"
    out_dir.mkdir(parents=True,exist_ok=True)
    result={}
    for name in cast:
        if not isinstance(name,str) or not re.fullmatch(r"[a-z0-9_-]{1,64}",name):
            raise WorkerError("Unsafe character identifier")
        expected=locks.get(name)
        if not isinstance(expected,str) or not re.fullmatch("[0-9a-f]{64}",expected):
            raise WorkerError("Missing immutable canonical SHA for "+name)
        query=urlencode({"episode_id":payload["episode_id"],"character":name})
        req=Request(server+"/api/media/reference?"+query,
                    headers={"Authorization":"Bearer "+token},method="GET")
        try:
            with urlopen(req,timeout=30) as response:
                remote_hash=response.headers.get("X-Reference-SHA256")
                if remote_hash!=expected:
                    raise WorkerError("Oracle returned changed canon hash")
                data=response.read(20*1024*1024+1)
        except (HTTPError,URLError,TimeoutError) as exc:
            raise WorkerError("Canon reference fetch failed: "+type(exc).__name__) from exc
        if len(data)>20*1024*1024 or len(data)<16 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise WorkerError("Canonical reference is not a valid PNG header or exceeds limit")
        if digest(data)!=expected:
            raise WorkerError("Canonical reference content does not match hash")
        dest=out_dir/(name+".png")
        dest.write_bytes(data)
        result[name]={"path":str(dest),"sha256":expected}
    return result


def download_dependencies(server, token, payload, job_id, job_dir):
    """Download only independently QA-approved inputs for the leased stage."""
    listing=Request(
        server+"/api/media/dependencies?"+urlencode({"job_id":job_id}),
        headers={"Authorization":"Bearer "+token},method="GET")
    try:
        with urlopen(listing,timeout=30) as response:
            manifest=json.load(response)
    except (HTTPError,URLError,TimeoutError,ValueError) as exc:
        raise WorkerError("Cannot resolve approved upstream media") from exc
    if manifest.get("schema")!="ahos.media.dependencies.v1":
        raise WorkerError("Unknown upstream media manifest")
    items=manifest.get("artifacts")
    if not isinstance(items,list) or len(items)>100:
        raise WorkerError("Too many upstream media files")
    total=sum(x.get("bytes",0) for x in items if isinstance(x,dict))
    if not isinstance(total,int) or total>MAX_FILE_BYTES:
        raise WorkerError("Upstream media exceeds safe job budget")
    output=[]
    folder=Path(job_dir)/"dependencies"
    folder.mkdir(parents=True,exist_ok=True)
    for i,item in enumerate(items):
        if not isinstance(item,dict):
            raise WorkerError("Malformed upstream artifact descriptor")
        task_id=item.get("task_id")
        name=item.get("filename")
        expected=item.get("sha256")
        size=item.get("bytes")
        if (not isinstance(task_id,str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,150}",task_id)
            or not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}",name)
            or not isinstance(expected,str) or not re.fullmatch(r"[0-9a-f]{64}",expected)
            or type(size) is not int or size<1 or size>MAX_FILE_BYTES):
            raise WorkerError("Unsafe or invalid upstream artifact metadata")
        kind=item.get("kind")
        character_id=item.get("character_id")
        licence=item.get("license_status")
        source_sha=item.get("source_sha256")
        if kind is not None and not re.fullmatch(r"[a-z_]{1,40}",str(kind)):
            raise WorkerError("Invalid dependency kind")
        if character_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",str(character_id)):
            raise WorkerError("Invalid dependency character id")
        if licence is not None and not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}",str(licence)):
            raise WorkerError("Invalid dependency licence status")
        if source_sha is not None and not re.fullmatch(r"[0-9a-f]{64}",str(source_sha)):
            raise WorkerError("Invalid dependency source sha256")
        uri=server+"/api/media/dependency?"+urlencode(
            {"job_id":job_id,"task_id":task_id,"filename":name})
        req=Request(uri,headers={"Authorization":"Bearer "+token},method="GET")
        sub=folder/(f"{i:03}-"+hashlib.sha256(task_id.encode()).hexdigest()[:12])
        sub.mkdir(parents=True,exist_ok=True)
        path=sub/name
        tmp=sub/(name+".incoming")
        received=0
        hasher=hashlib.sha256()
        try:
            with urlopen(req,timeout=300) as response:
                if response.headers.get("X-Artifact-SHA256")!=expected:
                    raise WorkerError("Upstream server SHA header differs")
                with tmp.open("xb") as stream:
                    while True:
                        data=response.read(min(CHUNK_BYTES,size-received+1))
                        if not data:break
                        received+=len(data)
                        if received>size:
                            raise WorkerError("Upstream media exceeds advertised byte size")
                        stream.write(data)
                        hasher.update(data)
            if received!=size or hasher.hexdigest()!=expected:
                raise WorkerError("Upstream media content or size changed")
            if path.exists():
                raise WorkerError("Previous dependency file exists; never overwrite")
            tmp.replace(path)
        except (HTTPError,URLError,TimeoutError) as exc:
            raise WorkerError("Upstream media transfer failed") from exc
        finally:
            tmp.unlink(missing_ok=True)
        output.append({"source_task_id":task_id,"task_id":task_id,"filename":name,
                       "path":str(path),"sha256":expected,"bytes":size,
                       "kind":kind,"character_id":character_id,
                       "license_status":licence,"source_sha256":source_sha})
    return output


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
        size=output.stat().st_size
        if not 1<=size<=MAX_FILE_BYTES:
            raise WorkerError("Artifact exceeds the configured safe multipart limit")
        if size>MAX_FILE:
            hasher=hashlib.sha256()
            with output.open("rb") as stream:
                for chunk in iter(lambda:stream.read(CHUNK_BYTES),b""):
                    hasher.update(chunk)
            raw=output
            actual_sha=hasher.hexdigest()
        else:
            raw=output.read_bytes()
            actual_sha=digest(raw)
        if actual_sha!=asset.get("sha256"):
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
        # Lock the worker to the actual immutable bytes, not just character names.
        references=download_canon(server,token,payload,dirname)
        dependencies=download_dependencies(server,token,payload,jid,dirname)
        plan=dirname/"production-plan.json"
        plan_payload=dict(payload)
        plan_payload["approved_reference_files"]=references
        plan_payload["dependency_artifacts"]=dependencies
        plan.write_text(json.dumps(plan_payload,ensure_ascii=False,indent=2),encoding="utf-8")
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
        submitted=[
            upload_large_file(server,token,jid,lease,name,raw)
            if isinstance(raw,Path)
            else upload_file(server,token,jid,lease,name,raw)
            for name,raw in outputs
        ]
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
