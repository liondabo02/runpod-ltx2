#!/usr/bin/env python3
"""Motor yetenek ve skill eksik envanteri (Yazılım Şirketi / yetenek keşifçisinin aracı).

Kaynak: studio/engine_capabilities.json. Her yeteneğin durumu ELLE YAZILMAZ, kanıttan hesaplanır:
  - kanıt yoksa                                 -> YOK
  - kanıttaki modül/sembol/desen bulunamazsa     -> KANIT_BOZUK (harita yalan söylüyor; önce bu düzeltilir)
  - kod var ama modülü anan test dosyası yoksa   -> TESTSIZ
  - kod + test var, açık görev bağlıysa          -> KISMI
  - kod + test var, açık görev yoksa             -> VAR
"insan_onayi" bayrağı ayrıca gösterilir: teknik VAR, profesyonel kalite demek DEĞİLDİR.

Skill denetimi: her yeteneğin sahibi skill dosyası var mı, skill dosyası kullandığı motor araçlarını anıyor mu.

Kullanım:
  python tools/engine_gaps.py                      # özet
  python tools/engine_gaps.py --json r.json --md r.md
  python tools/engine_gaps.py --write-skills       # var olan SKILL.md dosyalarına motor bloğunu yazar/günceller
Yalnız standart kütüphane; ağ yok, kurulum yok, harcama yok.
"""
import argparse, ast, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join("studio", "engine_capabilities.json")
ORDER = ("KANIT_BOZUK", "YOK", "TESTSIZ", "KISMI", "VAR")
BLOCK_START = "<!-- MOTORLAR:BASLA (tools/engine_gaps.py --write-skills yazar; elle düzenleme) -->"
BLOCK_END = "<!-- MOTORLAR:BITIS -->"
_ast_cache = {}


def load(root=ROOT, path=None):
    with open(path or os.path.join(root, REGISTRY), encoding="utf-8") as f:
        return json.load(f)


def _names(root, rel):
    if rel not in _ast_cache:
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            _ast_cache[rel] = {n.name for n in tree.body
                               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        except (OSError, SyntaxError, UnicodeDecodeError):
            _ast_cache[rel] = None
    return _ast_cache[rel]


def _read(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def evidence_problems(root, cap):
    """Kanıttaki her satırı doğrular; sorun listesi döner (boş = kanıt sağlam)."""
    out = []
    for e in cap.get("kanit", []):
        mod = e.get("modul", "")
        if "sembol" in e:
            names = _names(root, mod)
            if names is None:
                out.append("%s okunamadı" % mod)
            elif e["sembol"] not in names:
                out.append("%s içinde %s yok" % (mod, e["sembol"]))
        elif "desen" in e:
            text = _read(root, mod)
            if text is None:
                out.append("%s okunamadı" % mod)
            elif not re.search(e["desen"], text):
                out.append("%s içinde '%s' deseni yok" % (mod, e["desen"]))
        else:
            out.append("kanıt satırında sembol/desen yok: %s" % mod)
    return out


def test_problems(root, cap):
    """Test dosyası var mı ve kanıttaki modüllerden en az birini anıyor mu."""
    tests = cap.get("test", [])
    if not tests:
        return ["test dosyası belirtilmemiş"]
    stems = {os.path.splitext(os.path.basename(e["modul"]))[0] for e in cap.get("kanit", [])}
    out = []
    for t in tests:
        text = _read(root, t)
        if text is None:
            out.append("%s yok" % t)
        elif stems and not any(re.search(r"\b%s\b" % re.escape(s), text) for s in stems):
            out.append("%s kanıt modülünü (%s) anmıyor" % (t, ", ".join(sorted(stems))))
    return out


def status_of(root, cap):
    if not cap.get("kanit"):
        return "YOK", []
    ev = evidence_problems(root, cap)
    if ev:
        return "KANIT_BOZUK", ev
    tp = test_problems(root, cap)
    if tp:
        return "TESTSIZ", tp
    if cap.get("acik_gorev"):
        return "KISMI", ["açık görev: " + ", ".join(cap["acik_gorev"])]
    return "VAR", []


def skill_path(root, skill):
    return os.path.join(root, "skills", skill, "SKILL.md")


def check(root=ROOT, registry=None):
    """Tam rapor: yetenek satırları, motor özetleri, skill sorunları, öncelikli eksik listesi."""
    _ast_cache.clear()
    reg = registry if registry is not None else load(root)
    rows = []
    for cap in reg["yetenekler"]:
        st, why = status_of(root, cap)
        rows.append({"id": cap["id"], "motor": cap["motor"], "isci": cap["isci"], "skill": cap["skill"],
                     "yetenek": cap["yetenek"], "durum": st, "neden": why,
                     "insan_onayi": bool(cap.get("insan_onayi")), "acik_gorev": cap.get("acik_gorev", []),
                     "not": cap.get("not", ""), "moduller": sorted({e["modul"] for e in cap.get("kanit", [])})})
    engines = {}
    for r in rows:
        e = engines.setdefault(r["motor"], {k: 0 for k in ORDER})
        e[r["durum"]] += 1
    skills = {}
    for r in rows:
        s = skills.setdefault(r["skill"], {"skill": r["skill"], "moduller": set(), "yetenekler": []})
        s["moduller"].update(r["moduller"]); s["yetenekler"].append(r["id"])
    skill_rows = []
    for name, s in sorted(skills.items()):
        p = skill_path(root, name)
        text = _read(root, os.path.relpath(p, root))
        probs = []
        if text is None:
            probs.append("SKILL.md yok (bu çalışma kopyasında)")
        else:
            missing = sorted(m for m in s["moduller"] if m not in text)
            if missing:
                probs.append("kullandığı motor araçlarını anmıyor: " + ", ".join(missing))
            if BLOCK_START not in text:
                probs.append("motor bloğu yok (--write-skills)")
        skill_rows.append({"skill": name, "var": text is not None, "sorunlar": probs,
                           "yetenek_sayisi": len(s["yetenekler"]), "moduller": sorted(s["moduller"])})
    gaps = sorted((r for r in rows if r["durum"] != "VAR"), key=lambda r: (ORDER.index(r["durum"]), r["id"]))
    total = {k: sum(1 for r in rows if r["durum"] == k) for k in ORDER}
    return {"toplam": total, "yetenek_sayisi": len(rows), "motorlar": engines, "yetenekler": rows,
            "eksikler": [r["id"] for r in gaps], "skilller": skill_rows,
            "insan_onayi_bekleyen": [r["id"] for r in rows if r["insan_onayi"]]}


def render_md(rep):
    L = ["# Motor yetenek ve skill envanteri", "",
         "Durum kanıttan hesaplanır (tools/engine_gaps.py). VAR = kod + onu sınayan test var; profesyonel kalite DEĞİLDİR.",
         "Toplam %d yetenek: " % rep["yetenek_sayisi"] + ", ".join("%s %d" % (k, rep["toplam"][k]) for k in ORDER), "",
         "## Motor özeti", "", "| Motor | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
    for m, c in sorted(rep["motorlar"].items()):
        L.append("| %s | " % m + " | ".join(str(c[k]) for k in ORDER) + " |")
    L += ["", "## Eksikler (öncelik sırasıyla)", "", "| Kod | Durum | Yetenek | İşçi | Neden / not |", "|---|---|---|---|---|"]
    by = {r["id"]: r for r in rep["yetenekler"]}
    for i in rep["eksikler"]:
        r = by[i]
        why = "; ".join(r["neden"] + ([r["not"]] if r["not"] else []))
        L.append("| %s | %s | %s | %s | %s |" % (i, r["durum"], r["yetenek"], r["isci"], why.replace("|", "/")))
    L += ["", "## İnsan onayı bekleyen (teknik VAR olsa da zevk/kulak kararı sahipte)", "",
          ", ".join(rep["insan_onayi_bekleyen"]) or "-", "", "## Skill dosyaları", ""]
    for s in rep["skilller"]:
        L.append("- %s (%d yetenek): %s" % (s["skill"], s["yetenek_sayisi"], "; ".join(s["sorunlar"]) or "tamam"))
    return "\n".join(L) + "\n"


def skill_block(rep, skill):
    rows = [r for r in rep["yetenekler"] if r["skill"] == skill]
    L = [BLOCK_START, "## Motorlar ve yetenekler (gerçek araçlar)", "",
         "Bu işçinin kullandığı motorlar ve her yeteneğin kanıttan hesaplanan durumu.",
         "Eksik yetenek için önce açık görevi Yazılım Şirketi'ne bildir; olmayan aracı varmış gibi kullanma.", ""]
    for r in rows:
        tag = r["durum"] + (", insan onayı" if r["insan_onayi"] else "")
        tools = ", ".join("`%s`" % m for m in r["moduller"]) or "araç yok"
        extra = (" — açık: " + ", ".join(r["acik_gorev"])) if r["acik_gorev"] else ""
        L.append("- %s %s [%s]: %s%s" % (r["id"], r["yetenek"], tag, tools, extra))
    L.append(BLOCK_END)
    return "\n".join(L)


def write_skills(rep, root=ROOT):
    """Var olan SKILL.md dosyalarında motor bloğunu ekler/günceller. Dosya oluşturmaz. Değişen yolları döner."""
    changed = []
    for s in rep["skilller"]:
        if not s["var"]:
            continue
        p = skill_path(root, s["skill"])
        with open(p, encoding="utf-8", newline="") as f:
            text = f.read()
        nl = "\r\n" if "\r\n" in text else "\n"
        block = skill_block(rep, s["skill"]).replace("\n", nl)
        if BLOCK_START in text and BLOCK_END in text:
            a = text.index(BLOCK_START); b = text.index(BLOCK_END) + len(BLOCK_END)
            new = text[:a] + block + text[b:]
        else:
            new = text.rstrip("\r\n") + nl + nl + block + nl
        if new != text:
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            changed.append(os.path.relpath(p, root))
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--json"); ap.add_argument("--md")
    ap.add_argument("--write-skills", action="store_true")
    a = ap.parse_args(argv)
    rep = check(a.root)
    if a.write_skills:
        for p in write_skills(rep, a.root):
            print("skill güncellendi:", p)
        rep = check(a.root)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(render_md(rep))
    t = rep["toplam"]
    print("yetenek %d | " % rep["yetenek_sayisi"] + " ".join("%s=%d" % (k, t[k]) for k in ORDER))
    print("skill sorunlu: %d/%d" % (sum(1 for s in rep["skilller"] if s["sorunlar"]), len(rep["skilller"])))
    print("ilk eksikler:", ", ".join(rep["eksikler"][:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
