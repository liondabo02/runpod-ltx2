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


def generate_outline_local(prompt: str, cast: list[str], scene_count: int,
                           *, model: str = DEFAULT_MODEL, timeout: int = 150) -> dict:
    """Use existing Oracle Ollama through *loopback*, without local SSH/private keys.

    Draft only. 1-20 scenes split into small batches so a low-resource ARM
    model can work reliably and stay within bounded output limits.
    """
    import urllib.request
    import urllib.error
    if not 1 <= scene_count <= 20:
        raise ValueError("Scene count must be 1..20")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        raise ValueError("Invalid story premise")
    if not isinstance(cast, list) or not all(isinstance(c, str) for c in cast):
        raise ValueError("Invalid series cast")
    scenes = []
    for offset in range(0, scene_count, 3):
        count = min(3, scene_count - offset)
        prefix = ("Previously planned scenes: " +
                  " | ".join(s["summary"][:160] for s in scenes[-2:]))
        instruction = (
            "You are an animated series scriptwriter for children ages 2 to 5. "
            "Only output valid JSON, without Markdown. Write Turkish. "
            "Do not change the identities of recurring series characters. "
            "Return an object with property scenes, containing exactly " +
            str(count) + " objects. Each object MUST contain: location (string), "
            "summary (at least 25 characters, beginning-middle-end progression), "
            "emotional_beat (string), characters (array of first names). "
            "Write safe, gentle, coherent dramatic events with cause and effect; "
            "keep visual continuity and specific physical actions for animation. "
            "Cast: " + ", ".join(cast) + ". "
            "Story idea: " + prompt + ". "
            "Total episode scenes: " + str(scene_count) + ". "
            "Current batch begins at global scene " + str(offset + 1) + ". "
            + prefix
        )
        payload = {"model": model, "stream": False, "format": "json",
                   "prompt": instruction,
                   "options": {"temperature": 0.3, "num_predict": 950}}
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                outer = json.load(response)
            partial = json.loads(outer["response"])
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            raise RuntimeError("Oracle local Ollama returned invalid scene draft") from exc
        batch = partial.get("scenes")
        if not isinstance(batch, list) or len(batch) != count:
            raise RuntimeError("Director returned incorrect scene count")
        for item in batch:
            if not isinstance(item, dict) or not isinstance(item.get("summary"), str):
                raise RuntimeError("Director returned incomplete scene")
            if len(item["summary"].strip()) < 25:
                raise RuntimeError("Director scene summary too short")
            members = item.get("characters", [])
            if not isinstance(members, list) or not all(isinstance(x, str) for x in members):
                raise RuntimeError("Director character list invalid")
            scenes.append({
                "number": len(scenes) + 1,
                "location": str(item.get("location", "belirlenmedi"))[:100],
                "summary": item["summary"][:900],
                "emotional_beat": str(item.get("emotional_beat", ""))[:250],
                "characters": members[:12],
            })
    new_guests = sorted({
        c for s in scenes for c in s["characters"]
        if c.casefold() not in {x.casefold() for x in cast}
    })
    return {
        "schema": "ahos.studio-os.outline.v1",
        "source": "Oracle localhost Ollama (no external API)",
        "model": model,
        "new_paid_api_calls": 0,
        "status": "DRAFT_UNREVIEWED",
        "original_prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "cast": cast,
        "guest_characters_pending_assets": new_guests,
        "outline": {
            "title": prompt[:100], "premise": prompt,
            "learning_goal": "Çocuk dostu, yaşa uygun hikâye",
            "scenes": scenes,
        },
        "generated_tokens": None,
        "creative_approved": False,
        "identity_approved": False,
        "production_ready": False,
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
