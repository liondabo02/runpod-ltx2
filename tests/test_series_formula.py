import copy, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import series_formula as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sheet(plan):
    """plan: [(slot, saniye, karakterler, diyalog, ekstra)] -> ardışık vuruşlar."""
    beats, t = [], 0.0
    for slot, sec, chars, dlg, extra in plan:
        b = {"t_start": t, "t_end": t + sec, "formula_slot": slot, "characters": list(chars),
             "action": "%s sahnesi" % slot, "dialogue": dlg, "sound": ""}
        b.update(extra or {})
        beats.append(b); t += sec
    return beats


GIZEM_BIBLE = {"format_id": "gizem_komedi_ekibi", "characters": [
    {"id": "deniz", "name": "Deniz", "formula_role": "lider"},
    {"id": "ece", "name": "Ece", "formula_role": "akilli"},
    {"id": "bora", "name": "Bora", "formula_role": "korkak_yardimci"},
    {"id": "pofuduk", "name": "Pofuduk", "formula_role": "hayvan_yardimci"},
    {"id": "bekci", "name": "Bekçi Rıza", "formula_role": "supheli"},
    {"id": "muzeci", "name": "Müzeci Nur", "formula_role": "supheli"}]}
D = "deniz: Bakın!"


def _gizem():
    team = ["deniz", "ece", "bora", "pofuduk"]
    p = [("soguk_acilis", 36, ["bekci"], "bekci: İmdat!", None),
         ("varis", 54, team + ["muzeci"], D, None),
         ("sorusturma", 50, team + ["bekci"], D, None),
         ("ipucu", 15, ["ece"], "ece: Bir iz!", None),
         ("sorusturma", 40, team, "", None),
         ("ipucu", 15, ["ece"], "ece: Toz!", None),
         ("imza_an", 15, ["pofuduk", "bora"], "bora: Acıktım.", None),
         ("ipucu", 15, ["deniz"], D, None),
         ("kovalamaca", 70, ["bora", "pofuduk"], "", None),
         ("imza_an", 15, ["pofuduk"], "", None),
         ("tuzak_plani", 40, team, D, None),
         ("tuzak_aksiligi", 40, team, "bora: Eyvah!", None),
         ("maske_dusurme", 60, team + ["muzeci"], "ece: İpuçları belli!", None),
         ("kapanis_espri", 25, team, "pofuduk: Hih hih!", None)]
    return _sheet(p)


def test_gizem_uyumlu_bolum_gecer_ve_iskelet_sure_toplami_dogru():
    fmt = F.load("gizem_komedi_ekibi")
    assert F.cast_errors(GIZEM_BIBLE, fmt) == []
    assert F.episode_errors(_gizem(), fmt, GIZEM_BIBLE) == []
    sk = F.skeleton(fmt, 600)
    assert sk[0]["t0"] == 0 and sk[-1]["t1"] == 600
    assert all(a["t1"] == b["t0"] for a, b in zip(sk, sk[1:]))
    assert [x["slot"] for x in sk] == [s["slot"] for s in fmt["yapi"] if not s.get("serbest")]


def test_gizem_bilerek_bozma():
    fmt = F.load("gizem_komedi_ekibi")
    beats = _gizem()
    # 1) ipuçları maske düşürmeden sonraya kayarsa çözüm adil değildir
    b = [dict(x, formula_slot="sorusturma") if x["formula_slot"] == "ipucu" else x for x in beats]
    assert any(e.startswith("KURAL_ONCE") for e in F.episode_errors(b, fmt, GIZEM_BIBLE))
    # 2) maske düşürmede şüpheli yoksa
    b = copy.deepcopy(beats); b[12]["characters"] = ["deniz", "ece"]
    assert any(e.startswith("KURAL_ROL") for e in F.episode_errors(b, fmt, GIZEM_BIBLE))
    # 3) akış sırası bozulursa
    b = copy.deepcopy(beats); b[0], b[12] = dict(b[12], t_start=0, t_end=60), dict(b[0], t_start=600, t_end=636)
    assert any(e.startswith("SIRA_BOZUK") for e in F.episode_errors(b, fmt, GIZEM_BIBLE))
    # 4) etiketsiz vuruş, kısa bölüm, şiddet kelimesi
    b = copy.deepcopy(beats); b[4]["formula_slot"] = ""
    assert any(e.startswith("SLOT_ETIKETI_YOK") for e in F.episode_errors(b, fmt, GIZEM_BIBLE))
    assert any(e.startswith("SURE_KISA") for e in F.episode_errors(beats[:6], fmt, GIZEM_BIBLE))
    b = copy.deepcopy(beats); b[8]["action"] = "Kostümlü bıçak sallıyor"
    assert any(e.startswith("KURAL_GUVENLIK") for e in F.episode_errors(b, fmt, GIZEM_BIBLE))
    # 5) zorunlu slot eksik
    b = [x for x in beats if x["formula_slot"] != "tuzak_plani"]
    assert any("SLOT_EKSIK: 'tuzak_plani'" in e for e in F.episode_errors(b, fmt, GIZEM_BIBLE))


def test_oyuncu_kadrosu_ve_ozgunluk():
    fmt = F.load("gizem_komedi_ekibi")
    b = copy.deepcopy(GIZEM_BIBLE); b["characters"][3]["name"] = "Scooby"
    assert any(e.startswith("OZGUN_DEGIL") for e in F.cast_errors(b, fmt))
    b = copy.deepcopy(GIZEM_BIBLE); b["characters"][3]["name"] = "Tomurcuk"  # 'tom' kelime içinde: özgün sayılır
    assert F.cast_errors(b, fmt) == []
    b = copy.deepcopy(GIZEM_BIBLE); b["characters"] = b["characters"][:5]
    assert any(e.startswith("ROL_SAYISI: supheli") for e in F.cast_errors(b, fmt))
    b = copy.deepcopy(GIZEM_BIBLE); del b["characters"][0]["formula_role"]
    assert any(e.startswith("FORMUL_ROLU_YOK") for e in F.cast_errors(b, fmt))
    assert F.cast_errors({"characters": []}) == []  # formülsüz dizi: eski davranış


def test_sessiz_kovalamaca_kurallari():
    fmt = F.load("sessiz_kovalamaca")
    bible = {"format_id": "sessiz_kovalamaca", "characters": [
        {"id": "pasa", "name": "Paşa", "formula_role": "avci"}, {"id": "fistik", "name": "Fıstık", "formula_role": "kurnaz_kacan"}]}
    two = ["pasa", "fistik"]
    plan = [("kurulum", 40, two, "", None), ("kizisma", 60, two, "", None)]
    plan += [("gag", 22, two, "", {"sound": "boing", "gag_motif": "tırmık" if i % 3 == 0 else "kapı%d" % i}) for i in range(12)]
    plan += [("doruk", 70, two, "", None), ("ters_kose", 30, ["fistik"], "", None), ("kapanis", 20, two, "", None)]
    beats = _sheet(plan)
    assert F.cast_errors(bible, fmt) == []
    assert F.episode_errors(beats, fmt, bible) == []
    talky = [dict(b, dialogue="pasa: Yakalarım seni!") for b in beats]
    assert any(e.startswith("KURAL_DIYALOG") for e in F.episode_errors(talky, fmt, bible))
    mute = copy.deepcopy(beats); mute[3]["sound"] = ""
    assert any(e.startswith("KURAL_ALAN") for e in F.episode_errors(mute, fmt, bible))
    mute[3]["sound"] = "ortam sesi (varsayılan)"  # senaryo odasının yer tutucusu efekt sayılmaz
    assert any(e.startswith("KURAL_ALAN") for e in F.episode_errors(mute, fmt, bible))
    nomotif = [dict(b, gag_motif="m%d" % i) for i, b in enumerate(beats)]
    assert any(e.startswith("KURAL_MOTIF") for e in F.episode_errors(nomotif, fmt, bible))
    few = [b for i, b in enumerate(beats) if not (b["formula_slot"] == "gag" and i > 4)]
    few = _sheet([(b["formula_slot"], (b["t_end"] - b["t_start"]) * 2 if b["formula_slot"] == "gag" else b["t_end"] - b["t_start"],
                   b["characters"], "", {k: b[k] for k in ("sound", "gag_motif") if k in b}) for b in few])
    errs = F.episode_errors(few, fmt, bible)
    assert any(e.startswith("KURAL_YOGUNLUK") for e in errs) or any(e.startswith("SLOT_ADEDI") for e in errs)


def test_koy_toplulugu_ozellik_ve_isbirligi():
    fmt = F.load("koy_toplulugu")
    chars = [{"id": "dede", "name": "Ulu Dede", "formula_role": "bilge_buyuk"}]
    for i, (n, o) in enumerate([("Pıtır", "telaşlı"), ("Çivi", "mucit"), ("Gıdık", "şakacı"), ("Lale", "bahçıvan")]):
        chars.append({"id": "k%d" % i, "name": n, "formula_role": "ozellik_karakteri", "ozellik": o})
    bible = {"format_id": "koy_toplulugu", "characters": chars}
    assert F.cast_errors(bible, fmt) == []
    v = ["k0", "k1", "k2", "k3"]
    # isteğe bağlı 'tehdit' ve 'sarki_ani' yokken de zorunlu bölümlerin payları 480 sn'ye sığmalı
    good = _sheet([("koy_hayati", 75, v, "k0: Günaydın!", None), ("sorun", 70, ["dede", "k0"], "dede: Eyvah.", None),
                   ("ozellik_carpismasi", 90, v[:3], "k1: Ben yaparım!", None), ("ozellik_carpismasi", 90, v[1:], "", None),
                   ("isbirligi_cozum", 120, v + ["dede"], "k2: Oldu! Birlikte!", None), ("ders_kapanis", 45, v, "k3: Yaşasın!", None)])
    assert F.episode_errors(good, fmt, bible) == []  # "Oldu!" şiddet kelimesi (öldü) sayılmaz
    dead = copy.deepcopy(good); dead[1]["action"] = "Çiçek öldü sandılar"
    assert any(e.startswith("KURAL_GUVENLIK") for e in F.episode_errors(dead, fmt, bible))
    lonely = copy.deepcopy(good); lonely[2]["characters"] = ["k0"]; lonely[3]["characters"] = ["k0", "dede"]
    assert any(e.startswith("KURAL_KARAKTER") for e in F.episode_errors(lonely, fmt, bible))
    same = copy.deepcopy(bible); same["characters"][2]["ozellik"] = "telaşlı"
    assert any(e.startswith("ALAN_TEKRARI") for e in F.cast_errors(same, fmt))


def test_secim_ve_yonergeler():
    assert F.detect("Scooby-Doo gibi bir gizem dizisi") == "gizem_komedi_ekibi"
    assert F.detect("kedi ile fare kovalamaca, sessiz komedi") == "sessiz_kovalamaca"
    assert F.detect("küçük bir köyde yaşayan topluluk") == "koy_toplulugu"
    assert F.detect("format: koy_toplulugu ama gizem olsun") == "koy_toplulugu"
    assert F.detect("parkta oynayan iki kardeş") is None
    for fid in F.format_ids():
        fmt = F.load(fid)
        w = F.writer_block(fmt, 480, 0, 160)
        assert "formula_slot" in w and fmt["yapi"][0]["slot"] in w
        assert "formula_role" in F.director_block(fmt) and "ÖZGÜN" in F.director_block(fmt)


def test_formatlar_tutarli_ve_hazirlik_gercek_haritadan():
    import engine_gaps
    ids = {c["id"] for c in engine_gaps.load(REPO)["yetenekler"]}
    rep = engine_gaps.check(REPO)
    assert len(F.format_ids()) >= 3
    for fid in F.format_ids():
        fmt = F.load(fid)
        assert fmt["id"] == fid and fmt["hedef_sure_sn"][0] >= 480
        assert set(fmt["gerekli_yetenekler"]) <= ids, fid
        for s in fmt["yapi"]:
            assert s["adet"][0] <= s["adet"][1] and (not s.get("pay") or s["pay"][0] <= s["pay"][1])
        r = F.readiness(fmt, REPO, rep)
        assert r["gerekli"] == len(fmt["gerekli_yetenekler"]) and "HARITADA_YOK" not in r["sayim"]
    try:
        F.load("../gizli")
        assert False
    except ValueError:
        pass


def test_cli(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"total_seconds": 525, "beats": _gizem()}, ensure_ascii=False), encoding="utf-8")
    b = tmp_path / "b.json"
    b.write_text(json.dumps(GIZEM_BIBLE, ensure_ascii=False), encoding="utf-8")
    assert F.main(["denetle", "gizem_komedi_ekibi", str(p), "--bible", str(b)]) == 0
    assert F.main(["hazirlik"]) == 0 and F.main(["liste"]) == 0


# ---- entegrasyon: yönetmen -> bible -> senaryo odası -> denetçi (sahte LLM, ağ yok) ----
import re as _re
import tempfile
import showrunner as sr, writers_room as wr

FORM_BIBLE_RAW = {"title": "Sis Koyu Dedektifleri", "tone": "ürkütücü ama komik", "age_band": "6-10",
                  "visual_style": {"look": "düz renk, kalın çizgi"},
                  "characters": [dict(c, age=a, gender=g, role=c["formula_role"], voice_hint="ses")
                                 for c, a, g in zip(GIZEM_BIBLE["characters"], [14, 13, 14, 4, 60, 45],
                                                    ["male", "female", "male", "male", "male", "female"])],
                  "locations": [{"id": "fener", "name": "Eski Fener"}, {"id": "liman", "name": "Liman"}]}


def _slot_at(sk, t):
    for s in sk:
        if s["t0"] <= t < s["t1"]:
            return s["slot"]
    return sk[-1]["slot"]


class FormulaFake:
    """Senaryo odasının formül yönergesini okuyup ona uyan vuruşlar döndüren sahte model."""
    def __init__(self, fmt, seconds, bible):
        self.sk, self.seen, self.n = F.skeleton(fmt, seconds), [], 0
        self.roles = {c["id"]: c["formula_role"] for c in bible["characters"]}

    def __call__(self, system, user, temperature=0.7):
        self.seen.append(user)
        if "yaratıcı direktör" in system:
            return json.dumps(FORM_BIBLE_RAW, ensure_ascii=False)
        if "dil editörü" in system:
            return user.split("aynı yapıda döndür: ", 1)[1]
        if "eleştirmen" in system:
            return json.dumps({"scores": {"merak": 18, "yas_uygunluk": 18, "kimlik_surekliligi": 18,
                                          "eylem_cesitliligi": 13, "ses_duygu": 13, "guvenlik": 10}, "findings": []})
        if "Toplam" in user:
            return json.dumps({"title": "Fenerdeki Işık", "logline": "L", "acts": [{"act": i} for i in range(1, 7)]})
        t0, t1 = map(int, _re.search(r"Zaman aralığı: (\d+)-(\d+)", user).groups())
        out, t = [], t0
        team = ["deniz", "ece", "bora", "pofuduk"]
        while t < t1:
            e = min(t + 8, t1); self.n += 1
            slot = _slot_at(self.sk, (t + e) / 2.0)
            chars = team + (["muzeci"] if slot in ("maske_dusurme", "varis") else []) + (["bekci"] if slot == "soguk_acilis" else [])
            if slot == "sorusturma" and self.n % 3 == 0:
                slot = "ipucu"
            if slot == "kovalamaca" and self.n % 4 == 0:
                slot = "imza_an"
            out.append({"t_start": t, "t_end": e, "scene_id": "s", "location": "fener", "characters": chars,
                        "action": "eylem %d yeni olay %d" % (t, self.n),
                        "dialogue": "" if self.n % 5 == 0 else "ece: merhaba %d arkadaş nasılsın" % self.n,
                        "emotion": {"valence": .5, "arousal": .5, "intensity": .5}, "camera": "orta", "sound": "müzik",
                        "formula_slot": slot})
            t = e
        return json.dumps({"beats": out}, ensure_ascii=False)


class _Stubs:
    def __enter__(self):
        self.saved = (sr.vw.run, wr.llm_call, wr.time.sleep, sr.aw.run, sr.rw.run, sr.cw.run)
        sr.aw.run = lambda out: {"status": "PASSED", "duration_s": 480, "voiced_lines": 3}
        sr.rw.run = lambda *a, **k: {"status": "BLOCKED", "error": "FAKE"}
        sr.cw.run = lambda d, b: {"status": "PASSED", "characters": [], "approximations": []}
        sr.vw.run = lambda out, bible: {"status": "PASSED", "lines": 3, "problems": []}
        wr.time.sleep = lambda *_: None
        return self

    def __exit__(self, *a):
        sr.vw.run, wr.llm_call, wr.time.sleep, sr.aw.run, sr.rw.run, sr.cw.run = self.saved


def test_uctan_uca_gizem_formulu_yonetmenden_denetciye():
    fmt = F.load("gizem_komedi_ekibi")
    with _Stubs(), tempfile.TemporaryDirectory() as d:
        fake = FormulaFake(fmt, 480, FORM_BIBLE_RAW); wr.llm_call = fake
        rep = sr.run("Scooby-Doo gibi bir gizem dizisi: fenerde hayalet ışığı", None, 480, d)
        sid = rep["series_id"]
        bible = json.load(open(os.path.join(d, sid, "series-bible.json"), encoding="utf-8"))
        assert bible["format_id"] == "gizem_komedi_ekibi"
        assert any("DİZİ FORMÜLÜ" in u and "formula_role" in u for u in fake.seen)          # yönetmen yönergesi
        assert any("formula_slot" in u and "Bu perdenin" in u for u in fake.seen)           # senaryo odası yönergesi
        sheet = json.load(open(os.path.join(d, sid, "episodes", "e001", "beat_sheet.json"), encoding="utf-8"))
        assert F.episode_errors(sheet["beats"], fmt, bible, 480) == []
        wr_step = [s for s in rep["steps"] if s["worker"] == "writers_room"][0]
        assert wr_step["status"] == "DONE_DRAFT", wr_step


def test_formul_ihlali_senaryo_odasinda_hata_olur_ve_sessiz_turde_diyalog_kurali_kalkar():
    with _Stubs(), tempfile.TemporaryDirectory() as d:
        from test_writers_room import Fake
        wr.llm_call = Fake()
        bible = {"series_id": "t", "title": "T", "format_id": "gizem_komedi_ekibi", "characters": GIZEM_BIBLE["characters"],
                 "locations": [{"id": "park"}]}
        sheet, hist = wr.run(bible, "fikir", 480, d)
        assert any(e.startswith("FORMUL SLOT_ETIKETI_YOK") for e in hist[-1]["validator_errors"])
        # formülsüz aynı dizi: formül hatası yok (eski davranış)
        plain = dict(bible); plain.pop("format_id")
        sheet, hist = wr.run(plain, "fikir", 480, os.path.join(d, "p"))
        assert not any(e.startswith("FORMUL") for e in hist[-1]["validator_errors"])
        quiet = {"format_id": "sessiz_kovalamaca", "characters": []}
        errs, _ = wr.formula_check(["diyalog çok az: 0 kelime/dk (en az 15)"], [], quiet, 480)
        assert not any(e.startswith("diyalog çok az") for e in errs)
        loud, _ = wr.formula_check(["diyalog çok az: 0 kelime/dk (en az 15)"], [], bible, 480)
        assert any(e.startswith("diyalog çok az") for e in loud)
        wr.set_source("SAHİBİN METNİ")      # sahibin senaryosu: formül yalnız uyarı
        try:
            errs, warns = wr.formula_check([], [{"t_start": 0, "t_end": 480}], bible, 480)
            assert errs == [] and warns
        finally:
            wr.set_source(None)
