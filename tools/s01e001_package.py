# -*- coding: utf-8 -*-
"""S01E001 üretim paketi üreticisi (offline, deterministik, LLM'siz, GPU'suz, ücretsiz).
Çıktı: studio/s01e001-parkin-kurallari/ altında JSON+MD paket. Eski 'Uçurtmanın Kayıp Kuyruğu' taslağına DOKUNMAZ.
Dürüstlük: hazır olmayan bağımlılıklar readiness.json'da açıkça listelenir; hiçbir şey 'tamamlandı' diye uydurulmaz."""
import hashlib, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import s01e001_data as D  # noqa: E402

OUT_REL = os.path.join("studio", "s01e001-parkin-kurallari")
ROSTER = os.path.join("studio", "reference", "owner_accepted_roster_v1")
LENS = {"geniş": "24mm eşdeğeri (geniş, hafif derin alan)", "çok geniş": "18mm eşdeğeri", "orta": "40mm eşdeğeri (doğal, yüz bozulmaz)",
        "yakın": "65mm eşdeğeri (yüz odaklı, sığ alan)"}
LANG_FACTOR = {"tr": 1.0, "de": 1.15, "en": 0.95, "ar": 1.05, "fr": 1.15, "es": 1.12, "kmr": 1.1}   # TAHMİN katsayısı, ölçüm değil
LANG_NAME = {"tr": "Türkçe", "de": "Almanca", "en": "İngilizce", "ar": "Arapça", "fr": "Fransızca", "es": "İspanyolca", "kmr": "Kurmancî"}
SFX_RULES = [(r"elma", "elma ısırığı / sap düşüşü"), (r"zil", "bisiklet zili"), (r"kapı", "kapı açılma/kapanma"), (r"kelebek", "kelebek kanat çırpışı (hafif)"),
             (r"çöp", "çöp kutusu kapağı, hafif metalik tık"), (r"kaydırak|kayar|kayd", "kaydırak kayma sesi"), (r"alkış", "çocuk ve yetişkin alkışı"),
             (r"adım|yürü|koş", "ayak sesi (çimen/taş/ahşap yüzeye göre)"), (r"uçurtma", "uçurtma kanat hışırtısı"), (r"sepet", "sepet kapağı/hışırtı"),
             (r"tekerlek|teker|araba", "bebek arabası teker sesi")]
MUSIC = {"sc01": ("Günaydın teması", "hafif, 96 bpm, ksilofon+pizzicato, majör", "yumuşak giriş"),
         "sc02": ("Aile mutfağı", "100 bpm, ukulele+hafif perküsyon", "aynı tema, sıcak"),
         "sc03": ("Hazırlanma", "104 bpm, ana tema varyasyonu", "hafif tempo artışı"),
         "sc04": ("Komşular geliyor", "100 bpm, akordeon+pizzicato", "yeni renk, aynı tonalite"),
         "sc05": ("Park girişi", "108 bpm, flüt+gitar, açık gökyüzü hissi", "enerji yükselir"),
         "sc06": ("Kurallar şarkısı", "112 bpm, 4 kısa motif (her kural bir motif)", "öğretici, net ritim"),
         "sc07": ("Çöp avcıları", "116 bpm, komik fagot+pizzicato", "oyun hissi"),
         "sc08": ("Çiçekler", "88 bpm, harp+flüt, yavaş", "sakin, nazik"),
         "sc09": ("Kaydırak sırası", "120 bpm, ksilofon, merdiven motifi", "oyun, kısa sıralı vurgu"),
         "sc10": ("Güvenli yol", "104 bpm, tempolu yürüyüş motifi", "dengeli"),
         "sc11": ("Tekrar", "112 bpm, 4 kural motifi art arda", "öğrenme pekiştirme"),
         "sc12": ("Aile finali", "100 bpm, tam ana tema, orkestra dokunuşu", "kapanış, yavaşlayarak biter")}
AMBIENCE = {"home": "iç mekân: hafif ev sessizliği, uzak sokak, saat tik", "park": "dış mekân: kuş cıvıltısı, uzak çocuk sesleri, hafif rüzgâr, yaprak"}


def _j(p, d=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return d


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def _w(out, name, obj):
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, name)
    with open(p, "w", encoding="utf-8") as f:
        if name.endswith(".json"):
            json.dump(obj, f, ensure_ascii=False, indent=1)
        else:
            f.write(obj)
    return p


def ms(sec):
    return int(round(sec * 1000))


def words(t):
    return len([w for w in re.sub(r"[^\w\s']", " ", t).split() if w])


def parse_line(s):
    who, text = s.split(":", 1)
    return who.strip(), text.strip()


# ---------------------------------------------------------------- 1) kanon doğrulaması
def character_status(root):
    man = _j(os.path.join(root, ROSTER, "manifest.json"), {}) or {}
    appr = _j(os.path.join(root, "studio", "production", "approvals.json"), {}) or {}
    ready = {r["character_id"]: r for r in (_j(os.path.join(root, "studio", "production", "cast-readiness.json"), {}) or {}).get("rows", [])}
    by_id = {c["id"]: c for c in man.get("characters", [])}
    approved_ids = {a.get("character_id") or a.get("id") for a in appr.get("approvals", [])}
    rows = []
    for cid in D.ORDER:
        c = by_id.get(cid); fp = os.path.join(root, ROSTER, c["file"]) if c else None
        exists = bool(fp and os.path.exists(fp)); sha_ok = None
        if exists:
            sha_ok = _sha(fp) == c.get("sha256")
        cand = os.path.join(root, "studio", "candidates", cid)
        rr = ready.get(cid, {})
        rows.append({"character_id": cid, "age": (c or {}).get("age"), "approved_visual_path": (fp if exists else None),
                     "file_exists": exists, "sha256_matches_manifest": sha_ok,
                     "roster_status": (c or {}).get("status", "MISSING_IN_MANIFEST"),
                     "formal_approval_record": cid in approved_ids,
                     "owner_accepted_level": "POSTER_LEVEL_2D_DIRECTION" if exists else "NONE",
                     "independent_model_sheet": os.path.isdir(os.path.join(cand, "model-sheet")) and "CANDIDATE_ONLY_NOT_APPROVED" or "MISSING",
                     "mesh_3d": rr.get("mesh_3d", "MISSING"), "rig": rr.get("rig", "MISSING"),
                     "voice_reference": rr.get("voice_reference", "UNKNOWN"), "qa": rr.get("qa", "NOT_EVALUATED"),
                     "wardrobe_in_this_episode": D.WARDROBE[cid]})
    return {"roster_manifest_status": man.get("status"), "poster_sha256_recorded": man.get("source_sha256"),
            "formal_approvals_count": len([a for a in appr.get("approvals", [])]),
            "note": "Kırpımlar tek posterden alınmıştır; bağımsız model sheet / 3D mesh / rig YOKTUR. Eski aday dosyaları (studio/candidates) onaylı sayılmadı.",
            "characters": rows}


def fatos_headscarf_check(root):
    """Fatoş başörtüsü çelişkisi: kaynakları tarar; son sahip beyanı (P7, 2026-11-08) ve onaylı poster esas alınır."""
    hits = []
    cands = [os.path.join(root, "studio", "canon", "p7-owner-constraints.json"), os.path.join(root, "docs", "KARAKTER-KANONU.md"),
             os.path.join(root, "docs", "KARAKTER-TASARIM.md"), os.path.join(root, "docs", "KARAKTER-BIRLESTIRME.md"),
             os.path.join(root, "studio", "characters", "fatos", "character.json"), os.path.join(root, "studio", "characters", "fatos", "visual-dna.json"),
             os.path.join(root, "studio", "characters", "fatos", "portrait-design.json"), os.path.join(root, "studio", "canon", "cast-manifest.json")]
    for p in cands:
        if not os.path.exists(p):
            continue
        try:
            for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                low = line.lower()
                if "fato" in low and ("örtü" in low or "ortu" in low or "headscarf" in low or "hijab" in low or "uncovered" in low):
                    v = "UNCOVERED" if re.search(r"başörtüsüz|basortusuz|uncovered|without", low) else "COVERED"
                    hits.append({"file": os.path.relpath(p, root), "line": i, "reads_as": v, "text": line.strip()[:200]})
        except OSError:
            pass
    kinds = {h["reads_as"] for h in hits}
    return {"sources_found": len(hits), "hits": hits[:20], "conflict": len(kinds) > 1,
            "decision": "BAŞÖRTÜSÜZ (sahibin son beyanı: P7 2026-11-08 + onaylı poster kırpımı); çelişen kaynak varsa ESKİ kabul edilir",
            "episode_rule": "Fatoş bu bölümde başörtüsüz, omuz hizası kestane saçlı çizilir; hastalık/ameliyat anlatılmaz, saygılı ve doğal."}


# ---------------------------------------------------------------- 2) paket
def _positions(who):
    n = len(who); out = {}
    for i, c in enumerate(who):
        x = 0.0 if n == 1 else round(-1.6 + 3.2 * i / (n - 1), 2)
        out[c] = {"x_m": x, "depth": "ön" if i % 2 == 0 else "arka", "facing": "kameraya" if i % 3 != 2 else "diğer karaktere"}
    return out


def _trajectory(who, p0, p1):
    return {c: {"from": p0, "to": p1, "path": "kısa, yaşa uygun yürüyüş/emekleme; çizgi dışına taşmaz"} for c in who}


def _sfx(text):
    out = []
    for rx, name in SFX_RULES:
        if re.search(rx, text, re.I) and name not in out:
            out.append(name)
    return out


def _face(c, scene_title):
    kid = {"aden": "meraklı, parlak göz, geniş gülümseme", "kaan": "şaşkın ve neşeli, geniş açık göz, gülme", "salih": "oyunbaz, yuvarlak yanak, kısa kahkaha",
           "emos": "kendinden emin, kaşlar hareketli", "berzan": "yaramaz göz kırpma, kıkırdama", "aras": "sakin, yumuşak bakış, kısa gülümseme",
           "medine": "uyku/gevşek yüz, hafif mimik", "ramin": "uyku/gevşek yüz, hafif mimik"}
    if c in kid:
        return kid[c]
    return {"esra": "sakin, güven veren gülümseme", "ahmet": "rahat, hafif alaycı gülümseme", "esma": "zarif, sıcak, gözlerle gülen", "harun": "sakin karizmatik, hafif komik kaş",
            "veysel": "arkadaş canlısı, mavi gözler parlak", "oznur": "dingin, net bakış", "davut": "kahkahalı, geniş mimik", "fatos": "doğal, dostane, açık mimik"}[c]


def build_package(root=None, out=None):
    root = root or ROOT
    out = out or os.path.join(root, OUT_REL)
    scenes, flat, lines_all = [], [], []
    for sc in D.SCENES:
        loc = D.LOCATIONS[sc["loc"]]; t = ms(sc["s"]); sc_start = t; shots = []
        for si, (dur, framing, move, who, p0, p1, action, lines, trans) in enumerate(sc["shots"], 1):
            sid = f"{sc['id']}_sh{si:02d}"; sd = ms(dur)
            parsed = [parse_line(x) for x in lines]
            vcs, off = [], 450
            for li, (who_, text) in enumerate(parsed, 1):
                babble = text.startswith("[")
                est = 0 if babble else int(words(text) * (420 if who_ in D.WORD_LIMIT else 340) + 300)
                if babble:
                    est = 1200
                line = {"line_id": f"{sid}_l{li}", "character_id": who_, "text": text, "non_speech": babble,
                        "start_ms": t + off, "end_ms": t + off + est, "shot_id": sid, "scene_id": sc["id"]}
                off += est + 350; vcs.append(line); lines_all.append(line)
            shot = {"shot_id": sid, "scene_id": sc["id"], "framing": framing, "lens_perspective": LENS.get(framing.split(" ")[0], LENS["orta"]),
                    "camera_movement": move, "character_ids": who, "character_positions": _positions(who),
                    "movement_trajectory": _trajectory(who, p0, p1), "initial_pose": p0, "final_pose": p1, "action": action,
                    "duration_ms": sd, "exact_start_ms": t, "exact_end_ms": t + sd,
                    "visual_asset_refs": [loc["id"]] + [f"char_{c}_roster_v1" for c in who] + [f"wardrobe_{c}_ep001_v1" for c in who],
                    "voice_cue_refs": [v["line_id"] for v in vcs], "dialogue_lines": lines, "transition": trans}
            t += sd; shots.append(shot); flat.append(shot)
        assert t == ms(sc["e"]), sc["id"]
        text_all = sc["act"] + " " + " ".join(s["action"] for s in shots)
        scenes.append({
            "scene_id": sc["id"], "title": sc["title"], "location_id": loc["id"], "location_code": sc["loc"], "environment_asset_ref": loc["id"],
            "exact_start_ms": sc_start, "exact_end_ms": ms(sc["e"]), "duration_ms": ms(sc["e"]) - sc_start,
            "participating_character_ids": sc["cast"], "wardrobe_asset_refs": [f"wardrobe_{c}_ep001_v1" for c in sc["cast"]],
            "prop_asset_refs": ["prop_" + re.sub(r"\W+", "_", p.lower()) + "_v1" for p in sc["props"]], "props": sc["props"],
            "shot_list": [s["shot_id"] for s in shots], "shots": shots,
            "dialogue_lines": [l for s in shots for l in s["dialogue_lines"]],
            "acting_instructions": sc["act"] + " Karakterler durağan konuşmaz: konuşmadan önce bakar, bekler, karşıdakine tepki verir.",
            "facial_expressions": {c: _face(c, sc["title"]) for c in sc["cast"]},
            "body_motion": {c: ("emekleme/oturma/uzanma (1 yaş)" if c == "kaan" else "yatma/taşınma (bebek, hareket minimum)" if c in D.BABIES
                                else "kısa adım, el hareketi, zıplama (yaşa uygun)" if c in D.WORD_LIMIT else "doğal yetişkin hareketi, çocuklara eğilme") for c in sc["cast"]},
            "camera": "; ".join(f"{s['shot_id']}: {s['framing']} / {s['camera_movement']}" for s in shots),
            "lighting": sc["light"] + "; güneş yönü sabit: doğu-güneydoğu, gölgeler batı-kuzeybatıya",
            "ambience": AMBIENCE[loc["group"]],
            "sound_effects": sorted(set(x for s in shots for x in _sfx(s["action"] + " " + " ".join(s["dialogue_lines"])))) + ["adım/kıyafet hışırtısı"],
            "music": {"cue": MUSIC[sc["id"]][0], "style": MUSIC[sc["id"]][1], "dynamics": MUSIC[sc["id"]][2],
                      "rights": "özgün/prosedürel üretim (music_worker); telif sorunu yok, insan kulağıyla onay bekler"},
            "lip_sync": {"method": "fonem/viseme tabanlı (Rhubarb-uyumlu zaman çizelgesi)", "close_up_mouth_check": [s["shot_id"] for s in shots if s["framing"].startswith("yakın")],
                         "lines": len([l for l in lines_all if l["scene_id"] == sc["id"] and not l["non_speech"]])},
            "continuity_requirements": [f"Kıyafetler wardrobe_*_ep001_v1 ile sabit ({', '.join(sc['cast'][:4])}...)", "Aden: sarı yıldız toka ve sol yanakta üç çil HER çekimde",
                                        "Fatoş başörtüsüz", "Işık yönü ve güneş konumu sahneler arası sabit (doğu-güneydoğu)", f"Mekân {loc['id']} sürümü değişmez"],
            "negative_constraints": ["Yeni karakter kimliği tasarlama", "Yüzleri birbirine benzetme (ikizler hariç)", "Bebeklere konuşma verme", "Kaan'a 2 kelimeden uzun cümle verme",
                                     "Hareketsiz, yalnız konuşan figür", "Şiddet/korku/tehlikeli oyun", "Onaylı poster dışı yüz uydurma"],
            "quality_requirements": ["Çocuklarda göz hareketi, doğal bekleme, el hareketi, tepki görünür olmalı", "Dudak hareketi yakın planda kontrol edilir",
                                     "Video QA + yaratıcı kalite insan onayı olmadan 'tamamlandı' denmez"]})
    return {"scenes": scenes, "shots": flat, "lines": lines_all}


# ---------------------------------------------------------------- 3) doğrulama (kodla)
def validate(pkg):
    errs = []; sc = pkg["scenes"]
    if not sc or sc[0]["exact_start_ms"] != 0:
        errs.append("ilk sahne 0 ms'de başlamıyor")
    for a, b in zip(sc, sc[1:]):
        if a["exact_end_ms"] != b["exact_start_ms"]:
            errs.append(f"{a['scene_id']}→{b['scene_id']}: boşluk/üst üste binme")
    if sc and sc[-1]["exact_end_ms"] != D.TARGET_MS:
        errs.append(f"toplam {sc[-1]['exact_end_ms']} ms != {D.TARGET_MS}")
    if len(sc) != 12:
        errs.append(f"{len(sc)} sahne != 12")
    exp = [(0, 35), (35, 75), (75, 125), (125, 170), (170, 215), (215, 255), (255, 300), (300, 340), (340, 385), (385, 425), (425, 460), (460, 480)]
    for s, (a, b) in zip(sc, exp):
        if (s["exact_start_ms"], s["exact_end_ms"]) != (a * 1000, b * 1000):
            errs.append(f"{s['scene_id']}: süre sahibin zaman çizelgesiyle uyuşmuyor")
    seen = set()
    for s in sc:
        seen.update(s["participating_character_ids"])
        if sum(x["duration_ms"] for x in s["shots"]) != s["duration_ms"]:
            errs.append(f"{s['scene_id']}: çekim süreleri toplamı sahne süresine eşit değil")
    for c in D.ORDER:
        if c not in seen:
            errs.append(f"{c} hiçbir sahnede yok")
    spoken = {}
    for l in pkg["lines"]:
        c = l["character_id"]
        if c in D.BABIES and not l["non_speech"]:
            errs.append(f"{c} (bebek) konuşuyor: {l['text']}")
        if not l["non_speech"]:
            lim = D.WORD_LIMIT.get(c)
            if lim and words(l["text"]) > lim:
                errs.append(f"{c} satırı {lim} kelimeyi aşıyor: {l['text']}")
        spoken.setdefault(c, 0); spoken[c] += 1
    for a, b in zip(pkg["lines"], pkg["lines"][1:]):
        if a["shot_id"] == b["shot_id"] and a["end_ms"] > b["start_ms"]:
            errs.append(f"{a['line_id']} ile {b['line_id']} üst üste biniyor")
    for sh in pkg["shots"]:
        last = [l for l in pkg["lines"] if l["shot_id"] == sh["shot_id"]]
        if last and last[-1]["end_ms"] > sh["exact_end_ms"]:
            errs.append(f"{sh['shot_id']}: replikler çekime sığmıyor ({last[-1]['end_ms']} > {sh['exact_end_ms']})")
        if sh["duration_ms"] > 9500:
            errs.append(f"{sh['shot_id']}: çekim çok uzun")
        if len(sh["character_ids"]) == 1 and not sh["dialogue_lines"] and sh["framing"].startswith("yakın"):
            errs.append(f"{sh['shot_id']}: sessiz tek figür yakın plan")
    for c in ("medine", "ramin"):
        intros = [l for l in pkg["lines"] if not l["non_speech"] and c in l["text"].lower()]
        if not intros:
            errs.append(f"{c} aile tarafından tanıtılmıyor")
    for c in ("aden", "kaan", "salih", "emos", "berzan", "aras"):
        if spoken.get(c, 0) == 0:
            errs.append(f"{c} hiç konuşmuyor")
    if any("hasta" in l["text"].lower() or "ameliyat" in l["text"].lower() for l in pkg["lines"]):
        errs.append("Fatoş/hastalık atfı yasak")
    return errs


# ---------------------------------------------------------------- 4) planlar
def continuity(pkg):
    rows = []
    for s in pkg["scenes"]:
        el = round(30 + 25 * (s["exact_start_ms"] / D.TARGET_MS), 1)
        rows.append({"scene_id": s["scene_id"], "environment": s["environment_asset_ref"], "sun": {"azimuth_deg": 110, "elevation_deg": el, "direction": "doğu-güneydoğu"},
                     "characters": {c: {"wardrobe": f"wardrobe_{c}_ep001_v1", "identity_lock": f"char_{c}_roster_v1",
                                        "must_keep": ("sarı yıldız toka + sol yanakta üç çil" if c == "aden" else "başörtüsüz" if c == "fatos" else "başörtülü" if c in ("esra", "esma", "oznur")
                                                      else "mavi gözler" if c == "veysel" else "hamile (5 ay)" if c == "esma" else "")}
                                    for c in s["participating_character_ids"]},
                     "props": s["prop_asset_refs"]})
    return rows


def voice_plan(pkg):
    langs = {}
    for lg, f in LANG_FACTOR.items():
        items = []
        for l in pkg["lines"]:
            if l["non_speech"]:
                continue
            dur = l["end_ms"] - l["start_ms"]; est = int(dur * f)
            sh = next(s for s in pkg["shots"] if s["shot_id"] == l["shot_id"])
            fits = l["start_ms"] + est <= sh["exact_end_ms"]
            items.append({"line_id": l["line_id"], "window_ms": [l["start_ms"], sh["exact_end_ms"]], "est_audio_ms": est, "fits_window": fits})
        langs[lg] = {"language": LANG_NAME[lg], "duration_factor_estimate": f, "factor_is_estimate_not_measurement": True,
                     "needs_retiming": [i["line_id"] for i in items if not i["fits_window"]], "lines": len(items),
                     "rule": "Çekim süreleri kilitli; dil uzarsa ses yeniden hizalanır/cümle kısaltılır, görüntü uzatılmaz"}
    return {"base_language": "tr", "voice_identity_rule": "Her karakter aynı ses kimliğini (voice-profile.json) tüm dillerde korur",
            "babies": "Medine ve Ramin: yalnız nefes/mırıltı; konuşma yok", "kaan": "en çok 2 kelime", "lip_sync_method": "fonem/viseme zaman çizelgesi; yakın planlarda ağız kontrolü zorunlu",
            "lines": [{k: l[k] for k in ("line_id", "character_id", "text", "start_ms", "end_ms", "shot_id", "non_speech")} for l in pkg["lines"]],
            "languages": langs, "note": "Süreler kelime sayısından hesaplanan planlama tahminidir; gerçek ses üretilince ölçülüp güncellenir (yerel ses motoru: edge-tts/MMS; native kalite henüz doğrulanmadı)"}


def audio_plan(pkg):
    cues = []
    for s in pkg["scenes"]:
        for sh in s["shots"]:
            for sfx in _sfx(sh["action"] + " " + " ".join(sh["dialogue_lines"])):
                cues.append({"shot_id": sh["shot_id"], "start_ms": sh["exact_start_ms"], "sfx": sfx})
    return {"music": [{"scene_id": s["scene_id"], **s["music"], "start_ms": s["exact_start_ms"], "end_ms": s["exact_end_ms"]} for s in pkg["scenes"]],
            "ambience": [{"scene_id": s["scene_id"], "bed": s["ambience"], "start_ms": s["exact_start_ms"], "end_ms": s["exact_end_ms"]} for s in pkg["scenes"]],
            "sfx_cues": cues, "mix_rules": ["Diyalog her zaman öncelikli; müzik diyalog sırasında otomatik kısılır (ducking)", "Hedef: yaşa uygun, ani yüksek ses yok",
                                            "Müzik motifi: Aile teması her bölümde geri döner (sc01 ve sc12)"],
            "engine": "tools/music_worker.py (prosedürel, telifsiz) + insan kulağıyla onay", "status": "PLANNED_NOT_RENDERED"}


def tasks_and_workers():
    T = [("T01", "Kanon doğrulama (poster sha256, onay durumu, Fatoş)", "character_canon / s01e001_package", [], "READY", "Bu paket içinde çalıştırıldı"),
         ("T02", "Senaryo → yapılandırılmış üretim formatı (60 çekim)", "writers_room (sadık mod) / s01e001_package", ["T01"], "READY", "Paket üretildi; yaratıcı onay sahibin"),
         ("T03", "Ortam görselleri (A–J) arka plan üretimi", "studio_2d (scenes2d) / visual_pipeline", ["T02"], "BLOCKED", "Onaylı park ortam varlığı yok; 2D motorda sahne/köy/oda/bahçe var, A–J birebir yok"),
         ("T04", "Karakter görsel/model sheet (poster kırpımından referans-korumalı)", "character_worker / visual_pipeline", ["T01"], "BLOCKED", "Bağımsız model sheet yok; sahip onayı + GPU/yerel görüntü motoru gerekir"),
         ("T05", "Ses üretimi (TR) + viseme zamanları", "voice_worker / audio_pipeline", ["T02"], "READY", "Yerel ses motoru var; native kalite onayı insan kulağıyla"),
         ("T06", "Animatik (ses + durağan/düşük hareket)", "animatic_worker / studio_2d", ["T02", "T05"], "READY", "Poster kırpımlarıyla 2D animatik yapılabilir (gerçek karakter animasyonu değil)"),
         ("T07", "Müzik + ambiyans + SFX", "music_worker / audio_pipeline", ["T02"], "READY", "Prosedürel müzik; sahip kulak onayı"),
         ("T08", "Karakter rig/animasyon kütüphanesi (hareketli oyunculuk)", "rig worker / studio_2d", ["T04"], "BLOCKED", "Rig ve mesh yok (0/16)"),
         ("T09", "Render (480 sn)", "render_worker / studio_2d", ["T03", "T04", "T08"], "BLOCKED", "T03/T04/T08 tamamlanmadan gerçek karakter renderı yok"),
         ("T10", "Dublaj: DE/EN/AR/FR/ES/Kurmancî", "localisation_worker", ["T05"], "PARTIAL", "EN doğrulandı; diğerleri denenmedi; Kurmancî ana dil incelemesi gerekir"),
         ("T11", "Video QA + yaratıcı kalite", "studio_qa / video_qa", ["T09"], "BLOCKED", "Render yok"),
         ("T12", "Release gate + sahip onayı", "release_gate", ["T11"], "BLOCKED", "Onay kaydı yok; yayın sahibin kararı")]
    return [{"task_id": a, "title": b, "worker": c, "depends_on": d, "status": e, "note": f} for a, b, c, d, e, f in T]


def readiness(chars, fatos):
    miss = [c["character_id"] for c in chars["characters"] if not c["file_exists"]]
    return {"ready_stages": ["senaryo+shot manifest (taslak, sahip onayı bekler)", "continuity matrix", "ses/müzik/SFX planı", "yerel TR ses sentezi", "2D animatik"],
            "not_ready": [
                {"dependency": "16 karakterin bağımsız model sheet/ifade sheet'i", "state": "MISSING", "why": "yalnız tek poster kırpımı var"},
                {"dependency": "3D mesh + rig + animasyon kütüphanesi", "state": "MISSING (0/16)", "why": "Blender/GPU yok; sahip onayı gerekir"},
                {"dependency": "Park ortamı A–J onaylı ortam varlıkları", "state": "SPEC_ONLY", "why": "park-kite spec dışında ortam yok"},
                {"dependency": "Bebek (Medine, Ramin) ses referansı", "state": "MISSING", "why": "yalnız nefes/mırıltı SFX gerekir"},
                {"dependency": "Sahip onay kayıtları (approvals.json)", "state": "EMPTY", "why": "hiçbir varlık biçimsel onay almadı"},
                {"dependency": "Gerçek GPU / ücretli sağlayıcı", "state": "NOT_APPROVED", "why": "sahip onayı olmadan çağrılmaz"},
                {"dependency": "Dublaj: 5 dil denenmedi, Kurmancî native inceleme", "state": "PARTIAL", "why": "bkz. T10"}],
            "missing_character_files": miss, "fatos_check_conflict": fatos["conflict"],
            "honesty": "Bu paket PLAN ve manifesttir. Video, 3D, gerçek karakter animasyonu veya 'tamamlandı' iddiası YOKTUR."}


def script_md(pkg):
    L = [f"# {D.EPISODE_ID} — {D.TITLE}", "", "Süre: 480 sn · Dil: Türkçe · Yaş: 2–5 · Durum: TASLAK (sahip onayı bekler)", ""]
    for s in pkg["scenes"]:
        a, b = s["exact_start_ms"] // 1000, s["exact_end_ms"] // 1000
        L += [f"## {s['scene_id'].upper()} — {s['title']} ({a//60:02d}:{a%60:02d}–{b//60:02d}:{b%60:02d}) · {s['location_id']}", "",
              f"**Işık:** {s['lighting']}", f"**Oyunculuk:** {s['acting_instructions']}", ""]
        for sh in s["shots"]:
            L += [f"- {sh['shot_id']} ({sh['duration_ms']//1000} sn, {sh['framing']}, {sh['camera_movement']}): {sh['action']}"]
            for x in sh["dialogue_lines"]:
                L += [f"  {x}"]
        L += [""]
    return "\n".join(L)


def continuity_md(rows):
    L = ["# Continuity matrix (S01E001)", "", "| Sahne | Ortam | Güneş (yükseklik) | Karakterler | Kritik kilit |", "|---|---|---|---|---|"]
    for r in rows:
        keep = "; ".join(sorted({v["must_keep"] for v in r["characters"].values() if v["must_keep"]}))
        L.append(f"| {r['scene_id']} | {r['environment']} | {r['sun']['elevation_deg']}° ({r['sun']['direction']}) | {len(r['characters'])} | {keep} |")
    return "\n".join(L) + "\n"


def run(root=None, out=None):
    root = root or ROOT; out = out or os.path.join(root, OUT_REL)
    pkg = build_package(root, out); errs = validate(pkg)
    chars = character_status(root); fatos = fatos_headscarf_check(root)
    cm = continuity(pkg); env = {"locations": D.LOCATIONS, "geography": D.PARK_GEOGRAPHY, "props": sorted({p for s in D.SCENES for p in s["props"]}),
                                 "rule": "Her mekân sabit environment ID; ağaç/tabela/çöp kutusu/oyun ekipmanı sahneler arası değişmez; yeni park tasarımı onay olmadan eski kanonun yerine geçmez"}
    rd = readiness(chars, fatos)
    val = {"status": "PASSED" if not errs else "FAILED", "problems": errs, "scenes": len(pkg["scenes"]), "shots": len(pkg["shots"]),
           "lines": len(pkg["lines"]), "total_ms": pkg["scenes"][-1]["exact_end_ms"], "generated": time.strftime("%Y-%m-%d %H:%M"),
           "scope": "yalnız yapısal/offline doğrulama; yaratıcı kalite ve görsel üretim değerlendirilmedi"}
    files = [_w(out, "production_package.json", pkg), _w(out, "scene_shot_manifest.json", {"episode_id": D.EPISODE_ID, "title": D.TITLE, "target_ms": D.TARGET_MS, "shots": pkg["shots"]}),
             _w(out, "SENARYO-FINAL-TASLAK.md", script_md(pkg)), _w(out, "character_status.json", chars), _w(out, "character_differentiation_proposals.json",
             {"authority": "sahip: 'bazıları birbirine çok benziyor, ayar ver' (2026-11-22)", "status": "PROPOSED_NOT_APPROVED",
              "note": "Onaylı poster kırpımları değiştirilmedi; bunlar yeni üretimlerde uygulanacak ayrıştırma önerileridir", "pairs": D.DIFFERENTIATION}),
             _w(out, "fatos_headscarf_check.json", fatos), _w(out, "environment_library.json", env), _w(out, "continuity_matrix.json", cm),
             _w(out, "CONTINUITY-MATRIX.md", continuity_md(cm)), _w(out, "voice_lipsync_plan.json", voice_plan(pkg)), _w(out, "audio_music_plan.json", audio_plan(pkg)),
             _w(out, "production_tasks_workers.json", tasks_and_workers()), _w(out, "readiness.json", rd), _w(out, "validation_report.json", val)]
    return {"validation": val, "files": files, "readiness": rd}


if __name__ == "__main__":
    r = run(); print(json.dumps({"validation": r["validation"], "files": [os.path.basename(f) for f in r["files"]]}, ensure_ascii=False, indent=1))
    sys.exit(0 if r["validation"]["status"] == "PASSED" else 1)
