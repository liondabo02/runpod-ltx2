"""AHOS Studio OS: durable episode-wide production director, not a character script.

Creates an entire multi-language episode DAG from one owner prompt.
All external work is capability-gated, cost-gated, and quality-gated.
SQLite records survive restarts. No fake film outputs or unapproved releases.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "runtime" / "studio_os.sqlite3"
ROSTER = ROOT / "studio" / "reference" / "owner_accepted_roster_v1" / "characters"
CANON = ("aden","kaan","esra","ahmet","esma","harun","veysel","oznur",
         "salih","medine","davut","fatos","emos","berzan","aras","ramin")
ALIASES = {"öznur":"oznur","fatoş":"fatos","emoş":"emos"}
LANGS = ("tr","de","en","ar","fr","es","ku")
MAX_PENDING = 300
# Qualified stages must have production-grade rights + creative review, not just a .blend or MP4.
TASK_REQUIREMENTS = {
    "story": "screenplay",
    "storyboard": "storyboard",
    "model": "character_model",
    "rig": "rig",
    "set": "scene",
    "animation": "animation",
    "voice": "voice",
    "lipsync": "lipsync",
    "render": "render",
    "scene_qa": "qa",
    "edit": "editing",
    "episode_qa": "qa",
    "owner_review": "owner_review",
    "deliver": "delivery",
}
BUILTIN = ("intake", "canon", "asset_inventory")


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def cast_from_prompt(prompt: str) -> list[str]:
    t = prompt.casefold()
    found = []
    for cid in CANON:
        names = (cid,) + tuple(alias for alias, canonical in ALIASES.items() if canonical == cid)
        if any(re.search(r"(?<!\w)"+re.escape(n)+r"(?!\w)",t) for n in names):
            found.append(cid)
    # Canonical series defaults when owner refers to children without names.
    return found or ["aden","kaan"]


def compile_episode(prompt: str, *, minutes: int = 8, languages=("tr",),
                    series_id: str = "AHOS-FAMILY") -> dict:
    if not isinstance(prompt,str) or not (1 <= len(prompt.strip()) <= 4000):
        raise ValueError("Story prompt must contain 1-4000 characters.")
    if not isinstance(minutes,int) or not (1 <= minutes <= 20):
        raise ValueError("Episode duration must be 1-20 minutes.")
    languages=tuple(dict.fromkeys(languages))
    if not languages or any(x not in LANGS for x in languages):
        raise ValueError("Languages must be tr/de/en/ar/fr/es/ku.")
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{2,39}",series_id):
        raise ValueError("Invalid series ID.")
    cast=cast_from_prompt(prompt)
    scene_count=max(1,(minutes*60+59)//60)
    tasks=[]

    def add(tid,kind,deps=(),*,lang=None,scene=None,character=None):
        tasks.append({"id":tid,"kind":kind,"capability":TASK_REQUIREMENTS.get(kind,kind),
                      "deps":list(deps),"language":lang,"scene":scene,
                      "character":character,"state":"PENDING"})
    add("intake","intake")
    add("canon","canon",["intake"])
    add("story","story",["canon"])
    add("storyboard","storyboard",["story"])
    add("asset_inventory","asset_inventory",["storyboard"])
    for name in cast:
        add("model:"+name,"model",["asset_inventory"],character=name)
        add("rig:"+name,"rig",["model:"+name],character=name)
    for s in range(1,scene_count+1):
        scene_id=f"scene{s:02}"
        add(scene_id+":set","set",["storyboard","asset_inventory"],scene=s)
        add(scene_id+":animation","animation",[scene_id+":set"]+["rig:"+c for c in cast],scene=s)
        for lang in languages:
            code=scene_id+":"+lang
            add(code+":voice","voice",["story"],scene=s,lang=lang)
            add(code+":lipsync","lipsync",[scene_id+":animation",code+":voice"],scene=s,lang=lang)
            add(code+":render","render",[code+":lipsync",scene_id+":set"],scene=s,lang=lang)
            add(code+":qa","scene_qa",[code+":render"],scene=s,lang=lang)
    for lang in languages:
        all_scenes=[f"scene{s:02}:{lang}:qa" for s in range(1,scene_count+1)]
        add("episode:"+lang+":edit","edit",all_scenes,lang=lang)
        add("episode:"+lang+":qa","episode_qa",["episode:"+lang+":edit"],lang=lang)
    add("owner_review","owner_review",["episode:"+lang+":qa" for lang in languages])
    add("delivery","deliver",["owner_review"])
    if len(tasks)>MAX_PENDING:
        raise ValueError("Production graph exceeds 300 pending tasks; use lazy episode batching.")
    return {"schema":"ahos.studio-os.episode.v1","owner_prompt":prompt.strip(),
            "series_id":series_id,"minutes":minutes,"languages":list(languages),
            "cast":cast,"scene_count":scene_count,"tasks":tasks,
            "production_ready":False,"creative_target":"feature-film-quality CGI",
            "cost_policy":{"new_spending_allowed_eur":0,
                           "existing_prepaid_requires_verified_balance_and_owner_permission":True},
            "canon_policy":"reuse locked approved assets; review new identity once, never regenerate per shot",
            "owner_policy":"only final creative review, paid spending and irreversible actions require approval"}


class StudioOS:
    def __init__(self, db_path: Path, *, root: Path = ROOT):
        self.db_path = Path(db_path)
        self.root = Path(root)
        self.db_path.parent.mkdir(parents=True,exist_ok=True)
        self._create()

    def connect(self):
        db=sqlite3.connect(str(self.db_path),timeout=20)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _create(self):
        with self.connect() as db:
            db.executescript("""
CREATE TABLE IF NOT EXISTS episodes(
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
 plan_json TEXT NOT NULL, production_ready INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks(
 episode_id TEXT NOT NULL, task_id TEXT NOT NULL, kind TEXT NOT NULL,
 capability TEXT NOT NULL, depends_json TEXT NOT NULL, state TEXT NOT NULL,
 result_json TEXT NOT NULL DEFAULT '{}', attempts INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(episode_id,task_id),
 FOREIGN KEY(episode_id) REFERENCES episodes(id)
);
CREATE INDEX IF NOT EXISTS tasks_queue ON tasks(state,capability);
CREATE TABLE IF NOT EXISTS events(
 episode_id TEXT NOT NULL, task_id TEXT NOT NULL, time TEXT NOT NULL,
 event TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
);
""")

    def submit(self,prompt,*,minutes=8,languages=("tr",),series_id="AHOS-FAMILY") -> dict:
        plan=compile_episode(prompt,minutes=minutes,languages=languages,series_id=series_id)
        episode_id=str(uuid.uuid4())
        now=timestamp()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pending=db.execute(
                "SELECT COUNT(*) FROM tasks WHERE state IN ('PENDING','READY','RUNNING','WAITING_PROVIDER')"
            ).fetchone()[0]
            if pending+len(plan["tasks"])>MAX_PENDING:
                raise RuntimeError(f"Pending cap {MAX_PENDING} would be exceeded; complete existing jobs first.")
            db.execute("INSERT INTO episodes(id,created_at,status,plan_json) VALUES(?,?,?,?)",
                       (episode_id,now,"PLANNED",json.dumps(plan,ensure_ascii=False)))
            db.executemany(
                "INSERT INTO tasks(episode_id,task_id,kind,capability,depends_json,state,updated_at)"
                " VALUES(?,?,?,?,?,?,?)",
                [(episode_id,x["id"],x["kind"],x["capability"],
                  json.dumps(x["deps"]),x["state"],now) for x in plan["tasks"]]
            )
            db.execute("INSERT INTO events VALUES(?,?,?,?,?)",
                       (episode_id,"intake",now,"SUBMITTED","prompt received"))
        return {"episode_id":episode_id,"status":"PLANNED","task_count":len(plan["tasks"]),
                "scene_count":plan["scene_count"],"cast":plan["cast"],
                "languages":plan["languages"],"production_ready":False}

    def episode(self,episode_id: str):
        with self.connect() as db:
            episode=db.execute("SELECT * FROM episodes WHERE id=?",(episode_id,)).fetchone()
            if episode is None:
                raise KeyError("Unknown episode")
            tasks=db.execute("SELECT task_id,kind,capability,depends_json,state,result_json,attempts"
                             " FROM tasks WHERE episode_id=? ORDER BY rowid",(episode_id,)).fetchall()
        data=json.loads(episode["plan_json"])
        data.update({"episode_id":episode_id,"status":episode["status"],
                     "production_ready":bool(episode["production_ready"]),
                     "tasks":[dict(x) for x in tasks]})
        for t in data["tasks"]:
            t["deps"]=json.loads(t.pop("depends_json"))
            t["result"]=json.loads(t.pop("result_json"))
        return data

    def _update(self,db,eid,tid,state,details=None,*,event=None):
        now=timestamp()
        db.execute("UPDATE tasks SET state=?,result_json=?,updated_at=?"
                   " WHERE episode_id=? AND task_id=?",
                   (state,json.dumps(details or {},ensure_ascii=False),now,eid,tid))
        db.execute("INSERT INTO events VALUES(?,?,?,?,?)",
                   (eid,tid,now,event or state,str((details or {}).get("reason",""))[:300]))

    def tick(self,episode_id: str, *, max_steps=25, use_existing_oracle=False):
        """Run safe local discovery, create routed work orders for missing real capabilities.

        This does not claim to render a cartoon. Registered backends must be
        separately verified and connected by a reviewed production executor.
        """
        if not 1<=max_steps<=50:
            raise ValueError("max_steps out of bounds")
        episode=self.episode(episode_id)
        done={t["task_id"] for t in episode["tasks"] if t["state"] in ("DONE_VERIFIED","DONE_DRAFT")}
        progressed=[]
        blockers={}
        registry_path=self.root/"studio/pipeline/production-backends.json"
        try:
            registry=json.loads(registry_path.read_text(encoding="utf-8"))
            registered=registry.get("stages",{})
        except (OSError,ValueError):
            registered={}
        for task in episode["tasks"]:
            if len(progressed)>=max_steps:
                break
            if task["state"]!="PENDING" or not all(d in done for d in task["deps"]):
                continue
            tid=task["task_id"]
            kind=task["kind"]
            if kind=="intake":
                result={"prompt_sha256":hashlib.sha256(episode["owner_prompt"].encode()).hexdigest(),
                        "owner_constraints":"no new unapproved spending; no automatic publication"}
                state="DONE_VERIFIED"
            elif kind=="canon":
                missing=[c for c in episode["cast"] if not (self.root/"studio/reference/owner_accepted_roster_v1/characters"/
                            (f"{CANON.index(c)+1:02}_{c}.png")).is_file()]
                if missing:
                    result={"reason":"missing owner-approved reference","missing":missing}
                    state="WAITING_PROVIDER"
                else:
                    result={"locked_characters":{c:sha(self.root/"studio/reference/owner_accepted_roster_v1/characters"/
                               (f"{CANON.index(c)+1:02}_{c}.png")) for c in episode["cast"]},
                            "identity_source":"owner_accepted_roster_v1"}
                    state="DONE_VERIFIED"
            elif kind=="story" and use_existing_oracle:
                # Real AI planning on existing Oracle VM, never calls paid hosted APIs.
                try:
                    from studio_os_cloud_writer import generate_outline
                    data=generate_outline(episode["owner_prompt"],episode["cast"],episode["scene_count"],
                                          record=self.root/"ops/oracle/last-instance.json")
                    path=self.db_path.parent/"episode-artifacts"/episode_id/"story-outline.json"
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
                    guest_work_orders=self.register_guest_assets(episode_id,data)
                    result={"draft_path":str(path),"sha256":sha(path),
                            "guest_work_orders":guest_work_orders,
                            "status":"DRAFT_UNREVIEWED","model":data["model"],
                            "creative_approved":False}
                    state="DONE_DRAFT"
                except (RuntimeError,ValueError,TimeoutError,OSError) as exc:
                    state="WAITING_PROVIDER"
                    result={"reason":"Oracle story model unavailable or invalid output",
                            "error_type":type(exc).__name__,"capability":"screenplay"}
                    blockers["screenplay"]=result
            elif kind=="storyboard":
                # Textual shot plan only. Visual storyboard and creative approval are still required.
                story_task=next(x for x in self.episode(episode_id)["tasks"] if x["task_id"]=="story")
                path_str=story_task["result"].get("draft_path")
                if not path_str or not Path(path_str).is_file():
                    result={"reason":"screenplay draft file missing"}
                    state="WAITING_PROVIDER"
                else:
                    story=json.loads(Path(path_str).read_text(encoding="utf-8"))
                    beat_list=story["outline"]["scenes"]
                    shotplan={"schema":"ahos.studio-os.shotplan.v1","status":"DRAFT_UNREVIEWED",
                              "creative_approved":False,
                              "scenes":[{"scene_id":f"scene{i:02}","plot_beat":s,
                                         "planned_seconds":int(episode["minutes"]*60/len(beat_list))}
                                        for i,s in enumerate(beat_list,1)]}
                    path=self.db_path.parent/"episode-artifacts"/episode_id/"shot-plan.json"
                    path.write_text(json.dumps(shotplan,ensure_ascii=False,indent=2),encoding="utf-8")
                    result={"draft_path":str(path),"sha256":sha(path),
                            "status":"DRAFT_SHOT_PLAN_NOT_VISUAL_STORYBOARD"}
                    state="DONE_DRAFT"
            elif kind=="asset_inventory":
                # Auditing assets is possible without having every asset already created.
                registry=self.root/"studio/production/asset-registry.json"
                data=json.loads(registry.read_text(encoding="utf-8")) if registry.is_file() else {"assets":[]}
                found=len(data.get("assets",[]))
                result={"scanned_asset_records":found,
                        "owner_cast":episode["cast"],
                        "note":"Inventory audited; production suitability NOT certified"}
                state="DONE_VERIFIED"
            else:
                # Existence of a Python script only certifies an available *technical* adapter.
                # No untrusted plugin may auto-promote an episode to creative/identity approval.
                conf=registered.get(task["capability"],{})
                is_file=isinstance(conf,dict) and isinstance(conf.get("script"),str)
                script=(self.root/conf["script"]).resolve() if is_file else None
                safe=(script is not None and self.root.resolve() in script.parents
                      and script.is_file() and conf.get("cost_eur")==0)
                state="WAITING_PROVIDER"
                result={"reason":"production-qualified provider not yet verified",
                        "capability":task["capability"],
                        "technical_adapter_present":bool(safe),
                        "next_action":"verify provider capabilities, rights, creative QA, then run"}
                blockers[task["capability"]]=result
            with self.connect() as db:
                self._update(db,episode_id,tid,state,result)
            progressed.append({"task":tid,"state":state})
            if state in ("DONE_VERIFIED","DONE_DRAFT"):
                done.add(tid)
        # A later no-op tick must not erase existing provider blockers.
        all_task_states=[x["state"] for x in self.episode(episode_id)["tasks"]]
        status="WAITING_CAPABILITIES" if "WAITING_PROVIDER" in all_task_states else "IN_PROGRESS"
        with self.connect() as db:
            db.execute("UPDATE episodes SET status=? WHERE id=?",(status,episode_id))
        return {"episode_id":episode_id,"status":status,"steps":progressed,
                "capability_gaps":blockers,"production_ready":False}

    def register_guest_assets(self, episode_id: str, draft: dict):
        """Create missing character/rig jobs for any new story guest, without manual authoring.

        Guest identity is a deterministic ID. These remain pending until
        source, model and creative-quality requirements are verified.
        """
        guest_names=draft.get("guest_characters_pending_assets",[])
        if not guest_names:
            return []
        scenes=draft["outline"]["scenes"]
        created=[]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current=db.execute("SELECT COUNT(*) FROM tasks WHERE state IN ('PENDING','READY','RUNNING','WAITING_PROVIDER')").fetchone()[0]
            if current+2*len(guest_names)>MAX_PENDING:
                raise RuntimeError("Guest assets exceed pending cap")
            for guest in guest_names:
                key="guest-"+hashlib.sha256(guest.casefold().encode()).hexdigest()[:12]
                for prefix,cap,dep in (("model","character_model","asset_inventory"),
                                       ("rig","rig","model:"+key)):
                    tid=prefix+":"+key
                    db.execute("INSERT OR IGNORE INTO tasks(episode_id,task_id,kind,capability,depends_json,state,result_json,updated_at)"
                               " VALUES(?,?,?,?,?,?,?,?)",
                               (episode_id,tid,prefix,cap,json.dumps([dep]),"PENDING",
                                json.dumps({"guest_name":guest,"identity_status":"NEW_ASSET_REQUIRES_QA"}),timestamp()))
                    created.append({"id":tid,"guest_name":guest})
                for i,scene in enumerate(scenes,1):
                    if not any(guest.casefold()==str(x).casefold() for x in scene.get("characters",[])):
                        continue
                    tid=f"scene{i:02}:animation"
                    row=db.execute("SELECT depends_json,state FROM tasks WHERE episode_id=? AND task_id=?",
                                   (episode_id,tid)).fetchone()
                    if row is None or row["state"] not in ("PENDING","WAITING_PROVIDER"):
                        continue
                    deps=json.loads(row["depends_json"])
                    if "rig:"+key not in deps:
                        deps.append("rig:"+key)
                        db.execute("UPDATE tasks SET depends_json=? WHERE episode_id=? AND task_id=?",
                                   (json.dumps(deps),episode_id,tid))
            db.execute("INSERT INTO events VALUES(?,?,?,?,?)",
                       (episode_id,"asset_inventory",timestamp(),"GUEST_ASSET_ORDERS",str(len(created))))
        return created

    def get_events(self,episode_id):
        with self.connect() as db:
            return [dict(x) for x in db.execute("SELECT * FROM events WHERE episode_id=? ORDER BY rowid",
                                                (episode_id,)).fetchall()]


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",type=Path,default=DEFAULT_DB)
    sub=ap.add_subparsers(dest="action",required=True)
    new=sub.add_parser("submit")
    new.add_argument("--prompt",required=True)
    new.add_argument("--minutes",type=int,default=8)
    new.add_argument("--languages",default="tr")
    new.add_argument("--series-id",default="AHOS-FAMILY")
    for name in ("tick","status","events"):
        p=sub.add_parser(name)
        p.add_argument("--episode-id",required=True)
        if name=="tick":p.add_argument("--use-existing-oracle",action="store_true")
    args=ap.parse_args(argv)
    os=StudioOS(args.db)
    if args.action=="submit":
        result=os.submit(args.prompt,minutes=args.minutes,
                         languages=tuple(x.strip() for x in args.languages.split(",")),
                         series_id=args.series_id)
    elif args.action=="tick": result=os.tick(args.episode_id,use_existing_oracle=args.use_existing_oracle)
    elif args.action=="status": result=os.episode(args.episode_id)
    else:result=os.get_events(args.episode_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
