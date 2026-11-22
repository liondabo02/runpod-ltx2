#!/usr/bin/env python3
"""AHOS Showrunner (yönetici işçi): sahibin düz Türkçe komutunu ekibe dağıtır.

Sahip komutu yazar; yönetici işi parçalara böler, işçilere verir, sonuçları denetler, raporlar.
Yönetici hiçbir yaratıcı içerik ÜRETMEZ: dizi bible'ını Director işçisi, senaryoyu Yazarlar Odası üretir.
Henüz bağlı olmayan işçi aşamaları dürüstçe NOT_CONNECTED yazılır, sahte başarı yok.

Kullanım:
  python tools/showrunner.py --command "Şu karakterlerle şöyle bir dizi, ilk bölümde ..." [--series-id id] [--seconds 480]
  (series/<id>/ varsa komut, o dizinin YENİ BÖLÜM fikri sayılır; karakterler ve süreklilik korunur)
Ortam: AHOS_LLM_BASE / AHOS_LLM_KEY / AHOS_LLM_MODEL (writers_room ile aynı).
"""
import argparse, datetime, hashlib, json, os, re, sys, time, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import writers_room as wr  # noqa: E402
from validate_beat_sheet import validate  # noqa: E402
import voice_worker as vw  # noqa: E402
import animatic_worker as aw  # noqa: E402
import character_worker as cw  # noqa: E402
import render_worker as rw  # noqa: E402
import video_qa as vqa  # noqa: E402
import series_memory as sm  # noqa: E402
import script_fidelity as sf  # noqa: E402

ROOT = os.path.dirname(HERE)

# Yönetici -> işçi -> skill -> aşama. 'connected' = bu seri için çalıştırılabilir bağ var mı.
PIPELINE = [
    ("director",       "studio-screenwriting",          "dizi bible'ı + bölüm fikri",      True),
    ("research",       "studio-capability-scout",        "eksik yetenek önerisi",            False),
    ("character_model","studio-character-design",       "karakter modeli (Blender, insansı yaklaşım)", True),
    ("rig",            "studio-character-rig",           "iskelet/rig",                      False),
    ("scene",          "studio-scene-camera",            "mekân, ışık, kamera",              False),
    ("animation",      "studio-animation-acting",        "oyunculuk animasyonu",             False),
    ("voice",          "studio-voice-lipsync",           "diyalog sesleri",                  True),
    ("lipsync",        "studio-voice-lipsync",           "dudak senkronu",                   True),
    ("render",         "studio-render",                  "2D çizgi film render (yerel, Blender)", True),
    ("edit",           "studio-editing-sound",           "kurgu (animatik); müzik/efekt render aşamasında karışır", True),
    ("security",       "studio-rights-licence",          "telif/lisans geçidi",              False),
    ("finance",        "studio-budget-control",          "maliyet denetimi",                 False),
    ("qa",             "studio-independent-qa",          "bağımsız kalite denetimi",         True),
    ("distribution",   "studio-localisation-delivery",   "dil sürümleri ve teslim",          False),
]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def slug(text):
    t = unicodedata.normalize("NFKD", text.lower().replace("ı", "i")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "dizi"


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Ledger:
    """İş defteri: her işçi eylemi tek satır, silinmez (append-only)."""
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def add(self, worker, status, detail="", artifact=None):
        row = {"at": now(), "worker": worker, "status": status, "detail": detail, "cost_eur": 0}
        if artifact and os.path.exists(artifact):
            row["artifact"] = os.path.relpath(artifact, ROOT)
            row["sha256"] = sha_file(artifact)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


DIRECTOR_SYS = ("Sen bir çocuk dizisi yaratıcı direktörüsün. SADECE geçerli JSON döndür. "
                "Sahibin komutundan dizinin bible'ını çıkar. Karakter ve mekânları kendin tasarla; "
                "orijinal olsun, bilinen bir karakteri/eseri kopyalama. Sade, doğru Türkçe. Yaş bandına uygun, güvenli.")


_TR = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u"})


def _slug_id(v, taken, fallback):
    t = unicodedata.normalize("NFKD", str(v or "").lower().translate(_TR)).encode("ascii", "ignore").decode()
    t = re.sub(r"_?id$", "", re.sub(r"[^a-z0-9]+", "_", t)).strip("_")[:26] or fallback
    base, k = t, 2
    while t in taken:
        t = f"{base}_{k}"; k += 1
    taken.add(t)
    return t


def normalize_bible(raw):
    """Ücretsiz LLM'ler id'leri bozuk yazabiliyor (Türkçe harf, _id eki): düzelt, atıf yapan alanları da eşle."""
    raw = dict(raw)
    cmap, taken = {}, set()
    for n, c in enumerate(raw.get("characters", []) or []):
        old = c.get("id")
        c["id"] = _slug_id(old or c.get("name"), taken, f"karakter{n+1}")
        cmap[str(old)] = c["id"]
    for c in raw.get("characters", []) or []:
        rel = c.get("relationships")
        if isinstance(rel, dict):
            c["relationships"] = {cmap.get(str(k), _slug_id(k, set(), "x")): v for k, v in rel.items()}
    taken = set()
    for n, l in enumerate(raw.get("locations", []) or []):
        l["id"] = _slug_id(l.get("id") or l.get("name"), taken, f"mekan{n+1}")
    return raw


def director_make_bible(command, series_id=None):
    user = (f"Sahibin komutu: {command}\n"
            "EN AZ 2 karakter (biri çocuk), EN AZ 2 mekân yaz. id'ler yalnız küçük ASCII harf/rakam/alt çizgi (ör. pelin, kaan, bahce); Türkçe harf KULLANMA.\n"
            'JSON: {"title":"","tone":"","age_band":"3-6","visual_style":{"look":"","palette":["#hex"]},'
            '"characters":[{"id":"kucuk_harf_id","name":"","age":5,"role":"","personality":"",'
            '"look":"siluet, oran, renk, ayırt edici özellik","relationships":{},"voice_hint":"yaş/cinsiyet/ton",'
            '"safety_notes":[]}],'
            '"locations":[{"id":"kucuk_harf_id","name":"","light_by_time":{"sabah":"","aksam":""}}]}')
    last = None
    for _ in range(3):
        raw = normalize_bible(wr.llm_json(DIRECTOR_SYS, user, need=["title", "characters", "locations"]))
        last = raw
        if len(raw.get("characters", [])) >= 2 and len(raw.get("locations", [])) >= 1:
            return raw
        user += "\nÖNCEKİ DENEME YETERSİZDİ: en az 2 karakter ve 2 mekân yaz."
    return last


def check_bible(b):
    errs = []
    ids = [c.get("id") for c in b.get("characters", [])]
    if not ids: errs.append("karakter yok")
    if len(set(ids)) != len(ids): errs.append("karakter id'leri tekrar ediyor")
    for i in ids:
        if not re.fullmatch(r"[a-z0-9_]{1,30}", str(i)): errs.append(f"geçersiz karakter id: {i}")
    lids = [l.get("id") for l in b.get("locations", [])]
    if not lids: errs.append("mekân yok")
    for i in lids:
        if not re.fullmatch(r"[a-z0-9_]{1,30}", str(i)): errs.append(f"geçersiz mekân id: {i}")
    return errs


def finish_bible(raw, series_id):
    """Yönetici yalnız teknik alanları doldurur (hash kilitleri, onay durumu); yaratıcı alanlara dokunmaz."""
    b = {"schema": "ahos.series_bible.v1", "series_id": series_id, "title": raw.get("title", ""),
         "language_default": "tr", "age_band": raw.get("age_band", "3-6"), "tone": raw.get("tone", ""),
         "visual_style": {**raw.get("visual_style", {}), "frame_rate": 24, "render_style": "2d_flat_puppet_12fps"},
         "characters": [], "locations": raw.get("locations", []),
         "continuity": {"episodes": [], "running_facts": []},
         "episode_defaults": {"min_seconds": 480, "max_cost_eur": 1.0},
         "owner_approval": {"identity": "PENDING", "episode_final": "PENDING"}}
    for c in raw.get("characters", []):
        c = dict(c)
        c["identity_lock"] = {"reference_png": "", "sha256": "", "model_hash": "", "rig_hash": ""}
        c["voice"] = {"profile_id": "", "hint": c.pop("voice_hint", ""), "engine": "edge-tts", "licence_status": "review_required"}
        c.setdefault("safety_notes", [])
        b["characters"].append(c)
    return b


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class StepLog(list):
    """Adımlar eklendikçe studio/queue/progress.json'a yazar (sanal ofis hangi işçinin bittiğini böyle gösterir)."""
    def append(self, item):
        super().append(item)
        try:
            q = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studio", "queue")
            os.makedirs(q, exist_ok=True)
            json.dump({"done": [x.get("worker") for x in self if x.get("status") not in ("FAILED", "BLOCKED")],
                       "failed": [x.get("worker") for x in self if x.get("status") in ("FAILED", "BLOCKED")],
                       "at": time.time()}, open(os.path.join(q, "progress.json"), "w", encoding="utf-8"))
        except Exception:
            pass





def run(command, series_id=None, seconds=480, base=None, render_seconds=12, script_text=None):
    base = base or os.path.join(ROOT, "series")
    report = {"command": command, "steps": StepLog(), "series_id": None, "episode": None}
    # 1) Dizi var mı?
    sid = series_id
    bible_path = os.path.join(base, sid, "series-bible.json") if sid else None
    new_series = not (bible_path and os.path.exists(bible_path))
    if new_series:
        raw = director_make_bible(command, series_id)
        sid = series_id or slug(raw.get("title", "dizi"))
        bible_path = os.path.join(base, sid, "series-bible.json")
        errs = check_bible(raw)
        led = Ledger(os.path.join(base, sid, "ledger.jsonl"))
        if errs:
            led.add("director", "FAILED", "bible geçersiz: " + "; ".join(errs))
            report["steps"].append({"worker": "director", "status": "FAILED", "errors": errs})
            return report
        bible = finish_bible(raw, sid)
        write_json(bible_path, bible)
        led.add("director", "DONE_DRAFT", f"yeni dizi bible'ı: {len(bible['characters'])} karakter, {len(bible['locations'])} mekân", bible_path)
        report["steps"].append({"worker": "director", "status": "DONE_DRAFT", "what": "dizi bible'ı üretti (kimlik onayı: PENDING)"})
    else:
        bible = json.load(open(bible_path, encoding="utf-8"))
        led = Ledger(os.path.join(base, sid, "ledger.jsonl"))
        led.add("director", "REUSED", "mevcut dizi bible'ı kullanıldı (süreklilik)", bible_path)
        report["steps"].append({"worker": "director", "status": "REUSED", "what": "mevcut dizi, karakterler korunuyor"})
    report["series_id"] = sid

    # 2) Bölüm klasörü
    n = len(bible["continuity"]["episodes"]) + 1
    eid = f"e{n:03d}"
    out = os.path.join(base, sid, "episodes", eid)
    report["episode"] = eid
    idea = command
    if bible["continuity"]["running_facts"]:
        idea += "\nÖnceki bölümlerden süreklilik: " + " | ".join(bible["continuity"]["running_facts"][-5:])

    sdir = os.path.join(base, sid)
    ctx = sm.context_block(sdir)                      # dizi hafızası: önceki bölümlerin olguları
    if ctx:
        idea += "\n" + ctx
    wr.set_source(script_text)                        # sahibin senaryosu varsa yazarlar metne sadık kalır
    if script_text:
        os.makedirs(out, exist_ok=True); open(os.path.join(out, "source_script.txt"), "w", encoding="utf-8").write(script_text)
    # 3) Yazarlar Odası
    try:
        sheet, hist = wr.run(bible, idea, seconds, out)
        last = hist[-1]
        status = "DONE_DRAFT" if not last["validator_errors"] else "NEEDS_REVISION"
        led.add("writers_room", status, f"{eid}: skor {last['score']}, doğrulayıcı hata {len(last['validator_errors'])}",
                os.path.join(out, "beat_sheet.json"))
        report["steps"].append({"worker": "writers_room", "status": status, "score": last["score"],
                                "validator_errors": len(last["validator_errors"])})
        bible["continuity"]["episodes"].append({"id": eid, "title": sheet.get("title"), "logline": sheet.get("logline"), "status": status})
        if sheet.get("logline"):
            bible["continuity"]["running_facts"].append(f"{eid}: {sheet['logline']}")
        write_json(bible_path, bible)
    except RuntimeError as e:
        led.add("writers_room", "FAILED", str(e)[:300])
        report["steps"].append({"worker": "writers_room", "status": "FAILED", "error": str(e)[:300]})
        status = "FAILED"
        sheet = None

    # 4) Bağımsız doğrulama (kodla, üretici değil)
    if sheet:
        try:
            rec = sm.record_episode(sdir, eid, sheet)
            drift = sm.lock_canon(sdir, bible)
            led.add("memory", "DONE_DRAFT" if not drift else "NEEDS_REVISION",
                    f"{eid} kaydedildi; kilit kayması: {len(drift)}", os.path.join(sdir, "memory.json"))
            report["steps"].append({"worker": "series_memory", "status": "DONE_DRAFT" if not drift else "NEEDS_REVISION", "drift": drift})
        except Exception as e:  # noqa: BLE001
            led.add("memory", "BLOCKED", f"{type(e).__name__}: {str(e)[:200]}")
        if script_text:
            fid = sf.check(script_text, sheet["beats"])
            write_json(os.path.join(out, "script_fidelity.json"), fid)
            led.add("fidelity", fid["status"], f"replik kapsamı {fid['coverage']}", os.path.join(out, "script_fidelity.json"))
            report["steps"].append({"worker": "script_fidelity", "status": fid["status"], "coverage": fid["coverage"]})
        errs, warns = validate(sheet, bible, seconds)
        qa = {"verdict": "PASS" if not errs else "NEEDS_REVISION", "errors": errs, "warnings": warns,
              "creative": "NOT_EVALUATED", "cost_eur": 0, "generated_at": now()}
        write_json(os.path.join(out, "quality_report.json"), qa)
        led.add("qa", qa["verdict"], f"{len(errs)} hata, {len(warns)} uyarı", os.path.join(out, "quality_report.json"))
        report["steps"].append({"worker": "qa", "status": qa["verdict"], "errors": len(errs)})

    # 5) Ses + dudak senkronu işçisi (bağlı)
    voiced = False
    if sheet:
        try:
            man = vw.run(out, bible)
            vstatus = "DONE_DRAFT" if man["status"] == "PASSED" else "NEEDS_REVISION"
            led.add("voice", vstatus, f"{man['lines']} satır, {len(man['problems'])} sorun", os.path.join(out, "voice_manifest.json"))
            led.add("lipsync", vstatus, "viseme zamanları voice_manifest içinde")
            report["steps"].append({"worker": "voice+lipsync", "status": vstatus, "lines": man["lines"],
                                    "problems": len(man["problems"])})
            voiced = True
        except Exception as e:                         # motor yoksa çökme, dürüstçe BLOCKED yaz
            led.add("voice", "BLOCKED", f"{type(e).__name__}: {str(e)[:200]}")
            report["steps"].append({"worker": "voice+lipsync", "status": "BLOCKED", "error": str(e)[:200]})

    # 5b) Animatik (kurgu aşamasının ilk hâli)
    if sheet:
        try:
            am = aw.run(out)
            astatus = "DONE_DRAFT" if am["status"] == "PASSED" else "NEEDS_REVISION"
            led.add("edit", astatus, f"animatik {am['duration_s']} sn, {am['voiced_lines']} sesli satır", os.path.join(out, "animatic.mp4"))
            report["steps"].append({"worker": "edit(animatic)", "status": astatus, "seconds": am["duration_s"]})
        except Exception as e:
            led.add("edit", "BLOCKED", f"{type(e).__name__}: {str(e)[:200]}")
            report["steps"].append({"worker": "edit(animatic)", "status": "BLOCKED", "error": str(e)[:200]})

    # 5c) Karakter Tasarımcısı (Blender gerekir; yoksa dürüstçe BLOCKED)
    if sheet:
        try:
            cr = cw.run(os.path.join(base, sid), bible)
            led.add("character_model", cr["status"], f"{len(cr['characters'])} karakter; yaklaşık: {cr['approximations']}",
                    os.path.join(base, sid, "assets", "character_plan.json"))
            report["steps"].append({"worker": "character_model", "status": cr["status"],
                                    "approximations": cr["approximations"]})
            write_json(bible_path, bible)
        except Exception as e:
            led.add("character_model", "BLOCKED", f"{type(e).__name__}: {str(e)[:200]}")
            report["steps"].append({"worker": "character_model", "status": "BLOCKED", "error": str(e)[:200]})

    # 5d) Render (yerel Blender, kare kare; render_seconds=0 atlar, -1 tüm bölüm) + bağımsız video denetimi
    if sheet and render_seconds:
        t1 = float(seconds) if render_seconds < 0 else min(float(render_seconds), float(seconds))
        try:
            rm = rw.run(out, bible, 0.0, t1, os.path.join(base, sid))
            if rm.get("status") == "PASSED":
                led.add("render", "DONE_DRAFT", f"{rm['frames']} kare, {rm.get('sec_per_frame')} sn/kare, 8 dk tahmini {rm.get('estimate_hours_for_480s')} saat", rm["clip"])
                vq = vqa.check(rm["clip"], t1)
                write_json(os.path.join(out, "video_quality_report.json"), vq)
                led.add("qa_video", vq["verdict"], "; ".join(vq["problems"]) or "otomatik kontroller geçti (yaratıcı kalite: sahip izler)", rm["clip"])
                report["steps"].append({"worker": "render", "status": "DONE_DRAFT", "clip": rm["clip"],
                                        "estimate_hours_480s": rm.get("estimate_hours_for_480s")})
                report["steps"].append({"worker": "qa(video)", "status": vq["verdict"], "problems": vq["problems"]})
            else:
                led.add("render", "BLOCKED", str(rm.get("error")))
                report["steps"].append({"worker": "render", "status": "BLOCKED", "error": rm.get("error")})
        except Exception as e:
            led.add("render", "BLOCKED", f"{type(e).__name__}: {str(e)[:200]}")
            report["steps"].append({"worker": "render", "status": "BLOCKED", "error": str(e)[:200]})

    # 6) Kalan aşamalar: dürüst durum
    for wid, skill, what, connected in PIPELINE:
        if wid in ("director", "qa") or connected:
            continue
        led.add(wid, "NOT_CONNECTED", f"{what}: bu dizi için işçi bağlantısı henüz yok")
    report["not_connected"] = [w for w, _, _, c in PIPELINE if not c]
    write_json(os.path.join(out, "manager_report.json"), report)
    return report


def tell(report):
    L = [f"Dizi: {report['series_id']} · Bölüm: {report['episode']}"]
    for s in report["steps"]:
        L.append(f"- {s['worker']}: {s['status']}" + (f" (skor {s['score']})" if "score" in s else ""))
    if report.get("not_connected"):
        L.append("Henüz bağlı olmayan işçiler: " + ", ".join(report["not_connected"]))
    L.append("Yaratıcı onay yalnız sahibindedir. Hiçbir şey yayınlanmadı, harcama: 0 EUR.")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--command", required=True); p.add_argument("--series-id")
    p.add_argument("--seconds", type=int, default=480)
    p.add_argument("--render-seconds", type=int, default=12, help="0=render yok, -1=tüm bölüm")
    p.add_argument("--script-file", help="sahibin senaryo metni (sadık mod)")
    a = p.parse_args()
    txt = open(a.script_file, encoding="utf-8").read() if a.script_file else None
    print(tell(run(a.command, a.series_id, a.seconds, render_seconds=a.render_seconds, script_text=txt)))


if __name__ == "__main__":
    main()
