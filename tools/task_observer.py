#!/usr/bin/env python3
"""AHOS Task Observer: gözlem kaydı + inceleme (kod değiştirmez, yalnız öneri/ders yazar)."""
import argparse, datetime, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OBS = os.environ.get("AHOS_OBS_DIR") or os.path.join(ROOT, "studio", "observations")
IMP = os.environ.get("AHOS_IMPROVE_DIR") or os.path.join(ROOT, "studio", "improvements")
KINDS = ("friction", "correction", "method")


def _norm(t):
    return re.sub(r"\W+", " ", str(t).lower()).strip()


def _all():
    out = []
    for p in sorted(glob.glob(os.path.join(OBS, "[0-9]*.json"))):
        try:
            r = json.load(open(p, encoding="utf-8")); r["_path"] = p; out.append(r)
        except ValueError:
            pass
    return out


def log(worker, kind, issue, fix=""):
    if kind not in KINDS:
        raise ValueError("kind " + "/".join(KINDS))
    os.makedirs(OBS, exist_ok=True)
    key = _norm(worker + " " + issue)
    for r in _all():
        if r.get("key") == key:
            r["count"] = r.get("count", 1) + 1
            r["last"] = datetime.datetime.now().isoformat(timespec="seconds")
            if fix and not r.get("fix"):
                r["fix"] = fix
            p = r.pop("_path"); json.dump(r, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return p
    n = len(glob.glob(os.path.join(OBS, "[0-9]*.json"))) + 1 + len(glob.glob(os.path.join(OBS, "archive", "*.json")))
    slug = re.sub(r"[^a-z0-9]+", "-", _norm(issue).encode("ascii", "ignore").decode())[:40].strip("-") or "obs"
    p = os.path.join(OBS, "%04d-%s.json" % (n, slug))
    now = datetime.datetime.now().isoformat(timespec="seconds")
    json.dump({"key": key, "worker": worker, "kind": kind, "issue": issue, "fix": fix, "count": 1, "first": now,
               "last": now, "status": "open"}, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


def review(min_count=2):
    """Tekrar edenleri öneriye çevirir. Uygulamaz."""
    os.makedirs(IMP, exist_ok=True)
    made = []
    for r in _all():
        if r.get("status") != "open" or r.get("count", 1) < min_count:
            continue
        pid = os.path.splitext(os.path.basename(r["_path"]))[0]
        pp = os.path.join(IMP, pid + ".proposal.json")
        if os.path.exists(pp):
            continue
        json.dump({"id": pid, "worker": r["worker"], "kind": r["kind"], "problem": r["issue"], "proposed_fix": r.get("fix") or "(henüz yok)",
                   "evidence_count": r["count"], "status": "PROPOSED", "needs_owner_approval": True,
                   "pipeline": ["observe", "identify_gap", "propose_fix", "sandbox", "test", "review", "approved_integration"]},
                  open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        made.append(pp)
        if r.get("fix"):
            try:
                sys.path.insert(0, HERE); import lessons
                lessons.add(r["worker"], r["fix"], source="auto")
            except Exception:  # noqa: BLE001
                pass
    return made


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("log"); a.add_argument("--worker", required=True); a.add_argument("--kind", default="friction", choices=KINDS)
    a.add_argument("--issue", required=True); a.add_argument("--fix", default="")
    sp.add_parser("review"); sp.add_parser("list")
    x = ap.parse_args()
    if x.cmd == "log": print(log(x.worker, x.kind, x.issue, x.fix))
    elif x.cmd == "review": print(json.dumps(review(), ensure_ascii=False, indent=1))
    else:
        for r in _all(): print(r["count"], r["worker"], r["kind"], r["issue"])


if __name__ == "__main__":
    main()
