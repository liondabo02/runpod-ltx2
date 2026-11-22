#!/usr/bin/env python3
"""AHOS Karakter Tasarımcısı işçisi (diziden bağımsız).

Dizi bible'ındaki her karakterin yaş/rol/görünüm tarifinden mesh_factory spec'i üretir
(LLM önerir, kod doğrular/sınırlar; LLM çökerse yaşa göre güvenli varsayılan kullanılır),
sonra character_model_generic.py ile Blender'da .blend/.glb üretir.
Kimlik onayı yalnız sahibindedir: sonuç 'TECHNICAL_ONLY / owner_approval PENDING' kalır.

Not: mevcut mesh_factory insansı gövde üretir. İnsansı olmayan karakterler (hayvan, nesne)
"humanoid_approximation" olarak işaretlenir; gerçek form için yeni yetenek gerekir.
"""
import argparse, json, os, re, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import writers_room as wr  # noqa: E402

PALETTE_KEYS = ["skin", "skin_shadow", "shirt", "shorts", "shoe", "sole", "hair",
                "eye_white", "iris", "pupil", "mouth", "tongue", "star", "accent"]
CLASS_RANGE = {"infant": (0.45, 0.85), "toddler": (0.75, 1.05), "child": (1.0, 1.55), "adult": (1.5, 1.95)}
NONHUMAN = re.compile(r"kirpi|kedi|köpek|kuş|hayvan|robot|bulut|ağaç|hedgehog|cat|dog|bird|animal|cloud", re.I)

SYS = ("Sen bir çizgi film Karakter Tasarımcısısın. Verilen karakter için SADECE JSON döndür: "
       '{"class":"infant|toddler|child|adult","height_m":sayı,"eye_scale":0.8-1.4,'
       '"palette":{"skin":[r,g,b,1],"shirt":[...],"shorts":[...],"shoe":[...],"hair":[...],"accent":[...]},'
       '"design_note":"tek cümle, özgün ve akılda kalıcı bir tasarım fikri"} '
       "Renkler 0-1 arası. Çocuk dostu, canlı, birbirinden ayırt edilebilir renkler seç.")


def age_class(age):
    try:
        a = float(age)
    except (TypeError, ValueError):
        return "adult"
    return "infant" if a < 2 else "toddler" if a < 5 else "child" if a < 13 else "adult"


def _color(v):
    if not isinstance(v, (list, tuple)) or len(v) < 3:
        return None
    try:
        c = [min(1.0, max(0.0, float(x))) for x in v[:3]]
    except (TypeError, ValueError):
        return None
    return c + [1.0]


def sanitize(raw, ch):
    """LLM çıktısını güvenli spec'e çevirir; her alan sınırlanır."""
    raw = raw if isinstance(raw, dict) else {}
    cls = raw.get("class") if raw.get("class") in CLASS_RANGE else age_class(ch.get("age"))
    lo, hi = CLASS_RANGE[cls]
    try:
        h = float(raw.get("height_m"))
    except (TypeError, ValueError):
        h = (lo + hi) / 2
    h = round(min(hi, max(lo, h)), 2)
    try:
        eye = min(1.4, max(0.8, float(raw.get("eye_scale", 1.0))))
    except (TypeError, ValueError):
        eye = 1.0
    pal = {}
    for k, v in (raw.get("palette") or {}).items():
        c = _color(v)
        if k in PALETTE_KEYS and c:
            pal[k] = c
    look = " ".join(str(ch.get(k, "")) for k in ("name", "role", "look"))
    return {"character_id": ch["id"], "class": cls, "height_m": h, "eye_scale": round(eye, 2),
            "palette": pal, "license_status": "own",
            "hair_style": raw.get("hair_style") if raw.get("hair_style") in ("short", "bob", "ponytail", "spiky", "bun", "bald") else None,
            "species": raw.get("species") if raw.get("species") in ("human", "hedgehog") else None,
            "accessory": raw.get("accessory") if raw.get("accessory") in ("none", "glasses", "hat", "bow") else None,
            "humanoid_approximation": bool(NONHUMAN.search(look)),
            "design_note": str(raw.get("design_note", ""))[:200],
            "notes": f"{ch.get('name', ch['id'])} teknik spec - TECHNICAL_ONLY, kimlik onayı yok"}


def default_palette(cid):
    """LLM çökse bile karakterler birbirinden farklı görünsün: kimlikten kararlı renk üret."""
    import colorsys, hashlib
    h = int(hashlib.sha256(cid.encode()).hexdigest(), 16)
    hue = (h % 360) / 360.0
    shirt = list(colorsys.hsv_to_rgb(hue, 0.75, 0.95))
    shorts = list(colorsys.hsv_to_rgb((hue + 0.5) % 1.0, 0.6, 0.45))
    hair = [[0.10, 0.06, 0.03], [0.45, 0.28, 0.10], [0.80, 0.62, 0.25], [0.55, 0.55, 0.58]][(h >> 9) % 4]
    skin = [[0.86, 0.62, 0.47], [0.95, 0.76, 0.62], [0.62, 0.42, 0.30]][(h >> 13) % 3]
    return {"shirt": shirt + [1.0], "shorts": shorts + [1.0], "shoe": shorts + [1.0], "hair": hair + [1.0],
            "skin": skin + [1.0], "accent": list(colorsys.hsv_to_rgb((hue + 0.15) % 1.0, 0.9, 1.0)) + [1.0]}


def design(ch, llm=None):
    llm = llm or wr.llm_json
    user = "Karakter: " + json.dumps({k: ch.get(k) for k in ("id", "name", "age", "role", "look", "personality")},
                                     ensure_ascii=False)
    try:
        raw = llm(SYS, user, temperature=0.9, need=["class", "height_m"])
        src = "llm"
    except Exception as e:
        raw, src, err = {}, "default", f"{type(e).__name__}: {str(e)[:150]}"
    else:
        err = ""
    spec = sanitize(raw, ch)
    if not spec["palette"]:
        spec["palette"] = default_palette(ch["id"])
    spec["design_source"] = src
    if err:
        spec["llm_error"] = err
    return spec


def run_backend(plan_path, job_dir, evidence_path):
    cmd = [sys.executable, os.path.join(HERE, "studio_backends", "character_model_generic.py"),
           "--plan", plan_path, "--job-dir", job_dir, "--evidence", evidence_path]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, cwd=ROOT)
    ev = {}
    if os.path.exists(evidence_path):
        ev = json.load(open(evidence_path, encoding="utf-8"))
    return ev if ev else {"status": "BLOCKED", "blocked": [{"code": "NO_EVIDENCE", "remediation": (p.stdout + p.stderr)[-300:]}]}


def run(series_dir, bible, llm=None, backend=run_backend):
    assets = os.path.join(series_dir, "assets")
    os.makedirs(assets, exist_ok=True)
    specs = {}
    for ch in bible["characters"]:
        sp_path = os.path.join(assets, f"{ch['id']}.spec.json")
        if os.path.exists(sp_path):               # süreklilik: tasarım bir kez kilitlenir
            specs[ch["id"]] = json.load(open(sp_path, encoding="utf-8"))
            continue
        specs[ch["id"]] = design(ch, llm)
        json.dump(specs[ch["id"]], open(sp_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    plan = {"cast": list(specs), "characters": specs}
    plan_path = os.path.join(assets, "character_plan.json")
    json.dump(plan, open(plan_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ev = backend(plan_path, assets, os.path.join(assets, "character_evidence.json"))
    status = ev.get("status", "BLOCKED")
    arts = {}
    for a in ev.get("artifacts", []):
        arts.setdefault(a["cast"], []).append({"path": a["path"], "sha256": a["sha256"]})
    for ch in bible["characters"]:               # kimlik kilidi: karma, onay PENDING
        if ch["id"] in arts:
            ch.setdefault("identity_lock", {})["model_sha256"] = {x["path"]: x["sha256"] for x in arts[ch["id"]]}
    return {"status": "PASSED" if status == "PASSED" else "BLOCKED", "characters": list(specs),
            "approximations": [c for c, s in specs.items() if s.get("humanoid_approximation")],
            "blocked": ev.get("blocked", []), "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, help="series-bible.json yolu")
    a = ap.parse_args()
    bible = json.load(open(a.series, encoding="utf-8"))
    r = run(os.path.dirname(os.path.abspath(a.series)), bible)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    json.dump(bible, open(a.series, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
