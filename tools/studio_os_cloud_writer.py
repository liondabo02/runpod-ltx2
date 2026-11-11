"""Optional AHOS Studio OS director adapter: use existing Oracle SSH Ollama service.

No account creation, no public model port, no paid endpoint, no keys in Git.
Outputs DRAFT planning text, NEVER a professional/approved screenplay.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RECORD=ROOT/"ops/oracle/last-instance.json"
DEFAULT_MODEL="qwen2.5-coder:3b"


def generate_outline(prompt: str, cast: list[str], scene_count: int,
                     *, record: Path = RECORD, model: str=DEFAULT_MODEL,
                     timeout: int=160) -> dict:
    if scene_count<1 or scene_count>20:
        raise ValueError("scene count 1-20 required")
    if not record.is_file():
        raise RuntimeError("Oracle instance configuration not present")
    cfg=json.loads(record.read_text(encoding="utf-8"))
    host=cfg.get("public_ip")
    user=cfg.get("ssh_user","ubuntu")
    identity=Path(cfg.get("ssh_key","")).expanduser()
    if not host or not identity.is_file():
        raise RuntimeError("Oracle SSH connection/key unavailable")
    instruction=(
        "You are a children's animation series writer. Return ONLY a valid JSON object, "
        "no markdown. Use simple Turkish suitable for ages 2 to 5. Output properties: "
        "'title' (Turkish), 'premise' (one sentence), 'learning_goal' (one sentence), "
        "'scenes' (an array of exactly "+str(scene_count)+" objects). "
        "Each scene has 'number' integer, 'location' text, 'summary' text, "
        "'characters' array, and 'emotional_beat' text. "
        "Do not change character names or family identities. "
        "Scene events should have cause, consequence, character emotion and resolution. "
        "No violence or frightening incidents. "
        "Cast: "+", ".join(cast)+". Story: "+prompt
    )
    request={"model":model,"prompt":instruction,"stream":False,"format":"json",
             "options":{"temperature":0.4,"num_predict":1200}}
    # Bundle JSON into the SSH command without passing any credentials or secrets.
    remote_source=(
        "import urllib.request, json\n"
        "data="+repr(json.dumps(request,ensure_ascii=False).encode("utf-8"))+"\n"
        "req=urllib.request.Request('http://127.0.0.1:11434/api/generate',"
        "data=data,headers={'Content-Type':'application/json'})\n"
        "r=urllib.request.urlopen(req,timeout=130)\n"
        "j=json.load(r)\n"
        "print(json.dumps({'model':j.get('model'), 'response':j.get('response'),"
        "'eval_count':j.get('eval_count')}))\n"
    )
    command=["ssh","-o","BatchMode=yes","-o","ConnectTimeout=8",
             "-o","StrictHostKeyChecking=yes","-i",str(identity),
             f"{user}@{host}","python3 -c "+shlex.quote(remote_source)]
    try:
        run=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Oracle model generation timed out") from exc
    if run.returncode:
        raise RuntimeError("Oracle AI service unavailable; SSH exit code "+str(run.returncode))
    try:
        reply=json.loads(run.stdout)
        script=json.loads(reply["response"])
    except (KeyError,ValueError,TypeError) as exc:
        raise RuntimeError("Director model did not return valid JSON story") from exc
    if not isinstance(script,dict) or not isinstance(script.get("scenes"),list):
        raise RuntimeError("Story structure missing scenes")
    if len(script["scenes"])!=scene_count:
        raise RuntimeError(f"Model returned {len(script['scenes'])} scenes; expected {scene_count}")
    if not all(isinstance(x,dict) and isinstance(x.get("summary"),str) and
               len(x["summary"])>10 for x in script["scenes"]):
        raise RuntimeError("Some scenes lack a usable plot beat")
    guest_characters=[]
    for scene in script["scenes"]:
        members=scene.get("characters",[])
        if not isinstance(members,list):
            raise RuntimeError("Scene cast list invalid")
        for name in members:
            if not isinstance(name,str) or len(name)>80:
                raise RuntimeError("Invalid cast member in draft")
            if name.casefold() not in [c.casefold() for c in cast] and name not in guest_characters:
                guest_characters.append(name)
    return {
        "schema":"ahos.studio-os.outline.v1",
        "source":"existing Oracle VM, Ollama over authenticated SSH",
        "model":reply.get("model",model),
        "new_paid_api_calls":0,
        "status":"DRAFT_UNREVIEWED",
        "original_prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),
        "cast":cast,
        "guest_characters_pending_assets":guest_characters,
        "outline":script,
        "generated_tokens":reply.get("eval_count"),
        "creative_approved":False,
        "identity_approved":False,
        "production_ready":False,
    }


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--prompt",required=True)
    ap.add_argument("--cast",default="aden,kaan")
    ap.add_argument("--scenes",type=int,default=3)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--record",type=Path,default=RECORD)
    args=ap.parse_args(argv)
    result=generate_outline(args.prompt,args.cast.split(","),args.scenes,record=args.record)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":result["status"],"model":result["model"],
                      "scenes":len(result["outline"]["scenes"]),
                      "path":str(args.out)},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
