"""AHOS kabul görev kaydı: görev başına kabul ölçütleri ve doğrulanma sayısı (yüzde yok).
Kullanım: python tools/acceptance_board.py show [--area A] | set <ID> status <durum> | verify <ID> <n> <kanıt-dosyası>
Kendi dosyasına yazar (studio/standards/acceptance_tasks.json); başka ajanların görev panolarına dokunmaz."""
import json, sys, os, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "..", "studio", "standards", "acceptance_tasks.json")
STATES = ("bekliyor", "çalışılıyor", "doğrulandı", "engelli")

def load(p=PATH):
    with open(p, encoding="utf-8") as f: return json.load(f)

def save(d, p=PATH):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)

def counts(t):
    c = t["criteria"]; return sum(1 for x in c if x.get("verified")), len(c)

def validate(d):
    errs = []
    ids = {t["id"] for t in d["tasks"]}
    for t in d["tasks"]:
        for k in ("id", "area", "priority", "state", "current", "change", "deps", "criteria", "evidence"):
            if k not in t: errs.append(f"{t.get('id')}: eksik alan {k}")
        if t["state"] not in STATES: errs.append(f"{t['id']}: geçersiz durum")
        if t["state"] == "engelli" and not (t.get("blocker") and t.get("alternative")): errs.append(f"{t['id']}: engelli ama engel/alternatif yok")
        v, n = counts(t)
        if t["state"] == "doğrulandı" and v != n: errs.append(f"{t['id']}: doğrulandı ama {v}/{n}")
        for c in t["criteria"]:
            if c.get("verified") and not c.get("evidence"): errs.append(f"{t['id']}: kanıtsız doğrulanmış ölçüt")
        for dep in t["deps"]:
            if dep not in ids: errs.append(f"{t['id']}: bilinmeyen bağımlılık {dep}")
    return errs

def show(d, area=None):
    for t in d["tasks"]:
        if area and t["area"] != area: continue
        v, n = counts(t)
        print(f"{t['id']:5} [{t['state']:11}] {v}/{n} ölçüt  {t['title']}" + (f"  ENGEL: {t['blocker']}" if t["state"] == "engelli" else ""))
    V = sum(counts(t)[0] for t in d["tasks"]); N = sum(counts(t)[1] for t in d["tasks"])
    print(f"TOPLAM doğrulanan ölçüt: {V}/{N}")

if __name__ == "__main__":
    d = load(); a = sys.argv[1:]
    if not a or a[0] == "show": show(d, a[2] if len(a) > 2 and a[1] == "--area" else None)
    elif a[0] == "set": 
        t = next(x for x in d["tasks"] if x["id"] == a[1]); t[a[2]] = " ".join(a[3:]); save(d)
    elif a[0] == "verify":
        t = next(x for x in d["tasks"] if x["id"] == a[1]); c = t["criteria"][int(a[2])]; c["verified"] = True; c["evidence"] = a[3]; save(d)
    errs = validate(load())
    if errs: print("HATA:", *errs, sep="\n  "); sys.exit(1)
