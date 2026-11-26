"""AHOS 2D kare çizici: plan + poz -> PNG kareleri (çok işlemcili, kaldığı yerden devam)."""
import json, math, multiprocessing, os, shutil, sys, time
from concurrent.futures import ProcessPoolExecutor
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shot_motion as sm  # noqa: E402
import puppet2d as pp  # noqa: E402
import scenes2d as sc  # noqa: E402
import props2d
import object_state  # noqa: E402
import setpieces2d  # noqa: E402
import fx_layer  # noqa: E402
try:
    import bg_art  # noqa: E402
except ImportError:      # arka plan boyama katmanı yoksa eski görünüm
    bg_art = None

EMO = {"laugh": "laugh", "surprise": "surprise", "jump": "happy", "dance": "happy", "run": "happy", "wave": "happy"}
BACK_PROPS = ("leaves", "drops")
ZOOM = {"wide": 1.0, "medium": 1.1, "close": 1.6, "xclose": 2.3}


def _prof():
    try:
        import style_profile
        return style_profile.current()
    except Exception:
        return {}


def letter_at(cues, t):
    for c in cues:
        if c[0] <= t < c[1]:
            return c[3] if len(c) > 3 else "C"
    return "X"


def letter_window(cues, lt, frame_dt, lead=0.03):
    """Kare penceresine göre ağız harfi: 12 fps'te kısa görüntü birimleri (viseme) kaçmasın; ağız sesten ~30 ms önce hareket eder (animasyon geleneği)."""
    a, b = lt + lead, lt + lead + frame_dt
    best, bo, bx = None, 0.0, 0.0
    for c in cues:
        ov = min(b, c[1]) - max(a, c[0])
        if ov <= 0:
            continue
        v = c[3] if len(c) > 3 else "C"
        if v == "X":
            bx = max(bx, ov)
        elif ov > bo:
            best, bo = v, ov
    if best is not None and bo >= 0.30 * frame_dt:
        return best
    return "X"


def _hash(*a):
    h = 2166136261
    for v in a:
        h = ((h ^ int(v * 1000) & 0xFFFFFFFF) * 16777619) & 0xFFFFFFFF
    return h / 4294967295.0


def blink_at(t, seed):
    """Düzensiz göz kırpma: ~3,3 sn'de bir, bazen çift."""
    slot = int(t / 0.9)
    ph = (t / 0.9) - slot
    r = _hash(slot, seed)
    return (r < 0.27 and ph < 0.14) or (0.27 <= r < 0.32 and (ph < 0.12 or 0.30 < ph < 0.42))


def emphasis(cues, lt):
    """Açık ünlü (C/D) başlangıçlarında kısa vurgu darbeleri: kafa/kaş/el için."""
    e = 0.0
    for c in cues:
        if len(c) > 3 and c[3] in "CD":
            e += math.exp(-(((lt - c[0]) / 0.13) ** 2))
    return min(1.0, e)



def _x_at(px, cid, m):
    return px.get(cid, m["x1"])


def _hold_pos(cid, items, designs, beat, lt, hand=None):
    """Nesnenin bir karakterin ELİNDEKİ dünya konumu: çizilen elin gerçek yeri (pp.hand_offset). Hangi el: açıkça verilmişse o, yoksa karşıdaki kişiye/yürüyüş yönüne yakın olan."""
    for cid_, d_, p_, m_, _lk, _e in items:
        if cid_ == cid:
            H = d_["height"]
            if hand is None:
                others = [q["x"] for c2, _d, q, _m, _l, _e2 in items if c2 != cid]
                side = 1.0 if (others and others[0] > p_["x"]) else -1.0
                if m_["kind"] in ("walk", "carry", "run") and abs(m_["x1"] - m_["x0"]) > 0.05:
                    side = 1.0 if m_["x1"] > m_["x0"] else -1.0
                hand = "R" if side > 0 else "L"
            dx, h = pp.hand_offset(d_, p_, hand)
            return p_["x"] + dx, max(0.0, h - 0.08), H           # şişe tabanı avucun biraz altında: nesne elin içinde


    return None


def _draw_objects(cv, cam, beat, items, designs, lt):
    """Koreografideki nesne izi, object_state durum makinesi üzerinden: yerde -> AL -> elde -> VER (yay) -> elde -> BIRAK/İMHA."""
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        def hold(holder, t_, hand=None):
            h = _hold_pos(holder, items, designs, beat, t_, hand)
            return (h[0], h[1]) if h else (0.0, 0.0)
        def target(at):
            at = setpieces2d.TARGETS[at] if isinstance(at, str) else at
            return (at[0], at[1])
        x, y, st = object_state.position(tr, lt, hold, target)
        if x is None:                                           # imha edildi (örn. çöp kutusuna girdi): kutunun ağzında asılı kalmaz
            continue
        props2d.draw(cv, cam, ob["prop"], x, y, 0.0, 0, scale=ob.get("scale", 0.55))


def object_effects(beat, cid, lt):
    """Nesne olaylarından oyuncu etkisi: (uzanma yerel zamanı, uzanma süresi) veya None; ve taşınan ağırlık (kg-benzeri) -> poz farkı.
    Alma/verme/bırakma'da karakter temastan ÖNCE uzanır (hazırlık), temas anında kol en uzakta (tepe)."""
    reach = None; weight = 0.0
    for ob in (beat.get("choreo") or {}).get("objects", []):
        tr = ob.get("track") or []
        if not tr:
            continue
        for w in object_state.reach_windows(tr):
            if w["actor"] == cid and w["t0"] <= lt <= w["t1"] + (w["t1"] - w["t0"]):
                reach = (lt - w["t0"], 2.0 * max(0.3, w["t1"] - w["t0"]))
        st = object_state.state_at(tr, lt)
        if st["state"] in ("held", "put") and st["holder"] == cid or (st["state"] == "transfer" and cid in (st["holder"], st["to"])):
            weight = max(weight, object_state.weight_of(ob.get("prop")))
    return reach, weight


def _head_cropped(cam, x, H):
    """Başın/saçın/omzun ekran sınırında KISMEN kesilip kesilmediği (tamamen içerde/tamamen dışarıda sorun değil).
    Çocukta baş büyük (çene ~0.50H), yetişkinde çene ~0.70H; alt kenarda ön plan çimi (y>640) yüzü örter."""
    hw = 0.30 * H * cam.s; cx = cam.x(x); top = cam.y(H * 1.02); bot = cam.y(H * (0.50 if H < 1.3 else 0.70))
    inside_x = (cx - hw >= 0) and (cx + hw <= 1280)
    outside_x = (cx + hw <= 0) or (cx - hw >= 1280)
    inside_y = (top >= 0) and (bot <= 640)
    outside_y = bot <= 0 or top >= 720
    return not ((inside_x and inside_y) or outside_x or outside_y)

REACT_AFTER = 1.0      # replik bittikten sonra dinleyene kesme süresi (sn)
REACT_MID = 0.9        # uzun replikin ortasında tepki süresi (sn)
REACT_MIN_LINE = 3.0   # bu süreden uzun replikte orta tepki


def reaction_target(beat, t):
    """Tepki planında kamera kimde olmalı? Yalnız >1 karakter varsa; konuşan olmayan (dinleyen) karakter döner, yoksa None."""
    cast = beat.get("cast") or []
    if len(cast) < 2 or not beat.get("lines"):
        return None
    lines = beat["lines"]
    for ln in lines:
        d = ln["end"] - ln["start"]
        others = [c for c in cast if c != ln["char"]]
        if not others:
            continue
        if ln["end"] <= t < ln["end"] + REACT_AFTER and not any(l["start"] <= t < l["end"] for l in lines):
            return others[0]                              # replik bitti, kimse konuşmuyor: dinleyen yüz
        mid = ln["start"] + 0.62 * d
        if d >= REACT_MIN_LINE and mid <= t < mid + REACT_MID:
            return others[0]                              # uzun replikte araya tepki
    return None


def frame(plan, designs, t, bible_chars=None):
    beat = next((b for b in plan["beats"] if b["t_start"] <= t < b["t_end"]), None)
    if beat is None:
        return None
    lt, dur = t - beat["t_start"], beat["t_end"] - beat["t_start"]
    speaker, letters = None, {}
    spk_mood = {}
    for ln in beat["lines"]:
        if ln["start"] <= t < ln["end"]:
            speaker = ln["char"]
            spk_mood[ln["char"]] = ln.get("mood", "neutral")
            letters[ln["char"]] = letter_window(ln["cues"], t - ln["start"], 1.0 / float(plan.get("fps", 12))) if ln["cues"] else "CBDX"[int(t * 9) % 4]
    items, xs = [], []
    sp_cues = next((ln["cues"] for ln in beat["lines"] if ln["char"] == speaker and ln["start"] <= t < ln["end"]), [])
    sp_start = next((ln["start"] for ln in beat["lines"] if ln["char"] == speaker and ln["start"] <= t < ln["end"]), 0)
    E = emphasis(sp_cues, t - sp_start) if speaker else 0.0
    px = {}
    for cid in beat["cast"]:
        px[cid] = sm.pose_at(beat["motion"][cid]["kind"], lt, dur, beat["motion"][cid]["seed"], beat["motion"][cid]["x0"],
                             beat["motion"][cid]["x1"], designs[cid]["height"], designs[cid]["height"] * 0.45)["x"]
    for cid in beat["cast"]:
        m, d = beat["motion"][cid], designs[cid]
        Hm = d["height"]
        rc = ((beat.get("choreo") or {}).get("react") or {}).get(cid)           # yönetmen tepkisi: belirli andan sonra (ör. şaşırma)
        lte, kind_e = lt, m["kind"]
        if rc and lt >= float(rc["t"]):
            lte, kind_e = lt - float(rc["t"]), rc["kind"]
            m = dict(m); m["kind"] = kind_e; m["x0"] = m["x1"] = _x_at(px, cid, m)
        reach_w, carry_w = object_effects(beat, cid, lt)
        dur_e = dur
        if reach_w and kind_e in ("idle", "look") and not rc:      # nesne teması yaklaşıyor ve karakter boşta: uzanma hazırlığı otomatik
            lte, dur_e, kind_e = reach_w[0], reach_w[1], "reach"
            m = dict(m); m["kind"] = "reach"; m["x0"] = m["x1"] = _x_at(px, cid, m)
        args = (kind_e, 0, dur_e, m["seed"], m["x0"], m["x1"], Hm, Hm * 0.45)
        spk = (cid == speaker)
        p = sm.pose_at(args[0], lte, *args[2:], speaking=spk)
        # takip (follow-through): kollar gövdeden, kafa da biraz geriden gelir
        pa = sm.pose_at(args[0], max(0.0, lte - 0.11), *args[2:], speaking=spk)
        ph_ = sm.pose_at(args[0], max(0.0, lte - 0.05), *args[2:], speaking=spk)
        p["aL"], p["aR"], p["head"] = list(pa["aL"]), list(pa["aR"]), list(ph_["head"])
        if carry_w:                                                # taşınan ağırlık: ağır nesne geri yaslanma, ezilme, baş eğme
            adj = object_state.carry_adjust(carry_w)
            p["lean"] += adj["lean"]; p["sq"] = p.get("sq", 1.0) + adj["sq"]; p["head"][0] += adj["head_nod"]
        look = 0.0
        gz = ((beat.get("choreo") or {}).get("gaze") or {}).get(cid)       # yönetmen bakışı: konuşulan kişiye/nesneye
        if gz in px and gz != cid:
            look = 1.0 if px[gz] > px[cid] else -1.0
            p["head"][2] += 0.8 * look
        elif speaker and cid != speaker and speaker in px:            # dinleyen konuşana bakar
            look = 1.0 if px[speaker] > px[cid] else -1.0
            p["head"][2] += 0.7 * look
        if spk:                                                      # vurgulu hecede baş, kaş, el
            p["head"][0] += 0.14 * E
            p["z"] += 0.012 * Hm * E
            p["aR"][1] = (p["aR"][1] if p["aR"][1] else -0.2) - 0.5 * E
        items.append((cid, d, p, m, look, E if spk else 0.0))
        xs.append(p["x"])
    avg = sum(xs) / len(xs) if xs else 0.0
    focus = beat.get("focus")
    reaction = reaction_target(beat, t)               # tepki planı: replik bitince / uzun replikin ortasında dinleyene kesilir
    if reaction:
        focus = reaction
    elif speaker and speaker in beat["cast"]:       # yakın planda kamera hep o an konuşana bakar (yüz + omuz kadrajda)
        focus = speaker
    fh = designs[focus]["height"] if focus in designs else 1.1
    fx = xs[beat["cast"].index(focus)] if focus in beat["cast"] else avg
    SUB = 3.5                                          # kurgu: uzun vuruş 3,5 sn'lik çekimlere bölünür (kesme)
    sub = int(lt / SUB) if dur > 5.0 else 0
    ph = ((lt % SUB) / SUB) if dur > 5.0 else lt / max(dur, 0.1)
    preset = beat["camera"]
    if sub > 0:
        preset = ("wide", "medium", "close", "wide")[(int(beat.get("i", 0)) + sub) % 4]
        if beat.get("props") and sub % 2 == 0:
            preset = "insert"
    if lt < 1.4 and any(m_["kind"] == "surprise" for m_ in beat["motion"].values()):
        preset = "xclose"                               # şaşırma anında aşırı yakın plan (yüz dolsun)
    if reaction:
        preset = "close"                                # tepki planı her zaman yakın plan
    if speaker and speaker in beat["cast"] and preset in ("close", "xclose") and not reaction:
        fx = xs[beat["cast"].index(speaker)]
    zoom = ZOOM.get(preset, 1.5) * (1.0 + 0.05 * ph) * (1.0 + 0.18 * E if preset == "close" else 1.0)   # vurguda kamera içeri vurur
    if preset in ("close", "xclose") and focus in designs and designs[focus]["height"] > 1.3:
        zoom *= 0.78                                    # yetişkin yakın planda ekranı doldurmasın: kadraj biraz açılır
    cx = fx if preset in ("close", "xclose") else avg
    cy = {"wide": 0.95, "medium": min(0.85, fh * 0.62 + 0.25)}.get(preset, fh * 0.80)   # orta planda çocuk için kamera alçalır (bacak değil gövde+yüz)
    if preset in ("wide", "medium") and len(xs) > 1:            # kadraj güvenliği: tüm oyuncular kadraja sığsın
        lo, hi = min(xs), max(xs); half = (hi - lo) / 2 + 0.7
        zoom = max(0.8, min(zoom, 5.12 / (2 * half))); cx = (lo + hi) / 2
    cam = sc.Cam(cx, cy, zoom)
    if preset == "insert" and beat.get("props"):
        ix, iy = props2d.place(beat["props"][0], xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
        cam = sc.Cam(ix, max(0.55, min(iy - 0.35, 1.0)), 1.05)      # ek plan: nesne + karakterler birlikte kadrajda (başsız/bacaksız kadraj yok)
    cv = pp.Cv()
    sc.scene_back(cv, beat["scene"], cam, t, light=beat.get("light", ""))
    if preset != "insert":
        setpieces2d.draw(cv, cam, beat.get("loc"), t)
    if bg_art is not None:
        try:
            bg_art.enhance(cv, beat["scene"], beat.get("light"), t)
        except Exception:      # boyama katmanı kare üretimini asla düşürmesin
            pass
    for cid_, d_, p_, m_, _lk, _e in items:                          # koşu/yürüyüş: ayak tozu + hız çizgisi
        if _prof().get("dust", True) and m_["kind"] in ("walk", "run") and lt / max(dur, 0.1) < 0.85 and abs(m_["x1"] - m_["x0"]) > 0.05:
            fx_layer.dust(cv, cam, p_["x"], 1.0 if m_["x1"] >= m_["x0"] else -1.0, t, m_["kind"] == "run", d_["height"])
    for k_, kind in enumerate(beat.get("props") or []):             # arka katman nesneleri (yaprak, damla) karakterlerden ÖNCE çizilir: yüzlerin üstüne binmez
        if kind in BACK_PROPS and preset != "insert":
            wx, wy = props2d.place(kind, xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
            props2d.draw(cv, cam, kind, wx, wy, t, k_)
    for cid, d, p, m, look, e in sorted(items, key=lambda it: it[2]["x"]):
        if preset in ("close", "xclose") and cid != focus and _head_cropped(cam, p["x"], d["height"]):
            continue                                        # yakın planda odak dışı karakterin yüzü kenarda yarım kesilecekse çizilmez (kazara kesik yüz yok)
        emo = EMO.get(m["kind"], "neutral")
        mood_ = spk_mood.get(cid) or beat.get("mood", "neutral")
        if emo == "neutral" and mood_ != "neutral":
            emo = mood_
        slot = int(t / 1.6 + m["seed"])
        dart = (_hash(slot, m["seed"], 3) - 0.5) * 1.4
        st = {"mouth": letters.get(cid, "X"), "blink": blink_at(t, m["seed"]), "emotion": emo,
              "gaze": look * 0.9 + (0 if look else dart), "brow": e, "pulse": e}
        pp.draw_character(cv, d, p, st, cam.x(p["x"]), cam.y(0.0), cam.s, t)
    if xs:
        fx_layer.icons(cv, cam, beat, xs, [designs[c]["height"] for c in beat["cast"]], t, lt)
    _draw_objects(cv, cam, beat, items, designs, lt)
    for k_, kind in enumerate(beat.get("props") or []):
        if kind in BACK_PROPS:
            continue
        wx, wy = props2d.place(kind, xs, [designs[c]["height"] for c in beat["cast"]], t, lt, dur)
        props2d.draw(cv, cam, kind, wx, wy, t, k_)
    if xs:
        hy = max(designs[c]["height"] for c in beat["cast"]) * 1.1
        for kind in beat.get("fx") or []:
            if kind == "speed":      # eski üst-katman hız çizgisi yüzlerin üstüne biniyordu; yerine fx_layer.dust (arkada) var
                continue
            props2d.draw_fx(cv, cam, kind, sum(xs) / len(xs), hy if kind != "speed" else 0.1, t, lt)
    sc.scene_front(cv, beat["scene"], cam, t)
    im = grade(cv.done(), beat.get("light") or "", t)
    try:
        return fx_layer.post(im, beat, t, lt, dur, float(plan.get("total_s", 480.0)), bool(beat.get("first_of_scene")))
    except Exception:          # efekt katmanı asla kare üretimini düşürmesin
        return im


_VIG = {}


def grade(im, light, t):
    """Işık/atmosfer: sahne ışığına göre renk tonu + hafif vinyet (derinlik hissi). Yazıdaki ışık notundan türetilir."""
    from PIL import Image, ImageChops
    l = str(light).lower()
    if any(k in l for k in ("gün batım", "akşam", "altın", "kızıl")):
        tint, k = (255, 200, 150), 0.30
    elif any(k_ in l for k_ in ("sabah", "doğu")):
        tint, k = (255, 232, 200), 0.22
    elif any(k_ in l for k_ in ("bulut", "kapalı", "gölge")):
        tint, k = (215, 225, 245), 0.20
    elif any(k_ in l for k_ in ("öğle", "güneşli", "parlak")):
        tint, k = (255, 248, 230), 0.10
    else:
        tint, k = (255, 245, 225), 0.12
    sz = im.size
    tinted = ImageChops.multiply(im, Image.new("RGB", sz, tint))
    im = Image.blend(im, tinted, k)
    m = _VIG.get(sz)
    if m is None:
        w, h = sz; small = Image.new("L", (64, 36), 255)
        px = small.load()
        for y in range(36):
            for x in range(64):
                d = (((x - 31.5) / 32) ** 2 + ((y - 17.5) / 18) ** 2) ** 0.5
                px[x, y] = int(255 - 70 * max(0.0, d - 0.55) / 0.9)
        m = _VIG[sz] = small.resize(sz, Image.BILINEAR)
    return ImageChops.multiply(im, Image.merge("RGB", (m, m, m)))


_G = {}
ENGINE_FILES = ("render2d.py", "puppet2d.py", "scenes2d.py", "setpieces2d.py", "props2d.py", "fx_layer.py", "bg_art.py", "shot_motion.py", "puppet_side.py", "object_state.py",
                "shot_planner.py", "style_profile.py", "mood_engine.py")


def available_mem_mb():
    """Kullanılabilir RAM (MB). Windows: GlobalMemoryStatusEx; Linux: /proc/meminfo. Okunamazsa None."""
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
            m = MS(); m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return int(m.ap / 1048576)
        for ln in open("/proc/meminfo"):
            if ln.startswith("MemAvailable:"):
                return int(ln.split()[1]) // 1024
    except Exception:
        pass
    return None


def pick_workers(requested=None, per_worker_mb=450, reserve_mb=1200, mem_mb="auto"):
    """İşçi sayısı = min(istenen/CPU-1, (boş RAM - rezerv) / işçi başı RAM), en az 1. AHOS_RENDER_WORKERS ortam değişkeni zorlar (1 = güvenli tek işçi yolu)."""
    env = os.environ.get("AHOS_RENDER_WORKERS", "").strip()
    if env.isdigit() and int(env) >= 1:
        return int(env)
    cap = requested or max(1, (os.cpu_count() or 2) - 1)
    mem = available_mem_mb() if mem_mb == "auto" else mem_mb
    if mem is None:
        return max(1, min(cap, 2))                      # bellek bilinmiyorsa temkinli
    return max(1, min(cap, int((mem - reserve_mb) // per_worker_mb)))


def engine_stamp(plan, designs, fps):
    """Önbellek damgası: motor kaynakları + karakter tasarımları + plan vuruşları + fps + üslup profili. Değişirse eski kareler kullanılmaz."""
    import hashlib
    h = hashlib.sha256()
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in ENGINE_FILES:
        p = os.path.join(here, fn)
        if os.path.exists(p):
            h.update(fn.encode()); h.update(open(p, "rb").read())
    h.update(json.dumps(designs, sort_keys=True, default=str).encode())
    h.update(json.dumps(plan.get("beats", []), sort_keys=True, default=str).encode())
    h.update(str(fps).encode()); h.update(os.environ.get("AHOS_STYLE", "").encode())
    return h.hexdigest()[:16]


def valid_png(path, size=(1280, 720)):
    try:
        if os.path.getsize(path) < 2000:
            return False
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.size == size
    except Exception:
        return False


def _init(plan, designs):
    _G["plan"], _G["des"] = plan, designs


def _work(args):
    """Kareyi geçici dosyaya yaz, doğrula, sonra nihai adına taşı (yarım/bozuk kare tamamlanmış sayılmaz)."""
    f, path, fps = args
    if valid_png(path):
        return 0
    if os.environ.get("AHOS_TEST_FAULT") and multiprocessing.current_process().name != "MainProcess":   # yalnız testler: gerçek işçi ölümü / takılma
        if os.environ["AHOS_TEST_FAULT"] == "crash":
            os._exit(3)
        if os.environ["AHOS_TEST_FAULT"] == "hang":
            time.sleep(60)
    im = frame(_G["plan"], _G["des"], f / float(fps))
    if im is None:
        return 0
    tmp = path + ".tmp.png"
    im.save(tmp)
    if not valid_png(tmp, im.size):
        raise RuntimeError("kare doğrulanamadı: %s" % path)
    os.replace(tmp, path)
    return 1


def _acquire_lock(out_dir, stale_s=1200):
    """Aynı sahne için ikinci çakışan iş başlatma. Başkasının canlı kilidini ASLA kırmaz/sonlandırmaz; yalnız bayat (kalp atışı yok) kilidi devralır."""
    lp = os.path.join(out_dir, ".render.lock")
    if os.path.exists(lp):
        try:
            j = json.load(open(lp, encoding="utf-8"))
        except Exception:
            j = {}
        if time.time() - float(j.get("beat", 0)) < stale_s:
            raise RuntimeError("AYNI SAHNE İÇİN BAŞKA İŞ ÇALIŞIYOR (pid=%s, %s). İkinci iş başlatılmadı; o işi kimliğini doğrulamadan sonlandırmıyorum." % (j.get("pid"), j.get("started")))
    json.dump({"pid": os.getpid(), "started": time.strftime("%H:%M:%S"), "beat": time.time()}, open(lp, "w", encoding="utf-8"))
    return lp


def _beat_lock(lp):
    try:
        j = json.load(open(lp, encoding="utf-8")); j["beat"] = time.time()
        json.dump(j, open(lp, "w", encoding="utf-8"))
    except Exception:
        pass


def render_window(plan, designs, out_dir, workers=None, progress=True, frame_timeout=240, window_mult=3):
    """Dayanıklı render: bellek-duyarlı işçi sayısı, sınırlı kuyruk (parça parça), kare zaman aşımı, çöken işçide yeniden deneme (az işçiyle,
    en sonunda tek işçi), atomik kare yazımı, motor/varlık değişince bayat kare karantinası, kilit + iptal dosyası (.cancel)."""
    from concurrent.futures import wait, FIRST_COMPLETED
    from concurrent.futures.process import BrokenProcessPool
    os.makedirs(out_dir, exist_ok=True)
    fps = plan["fps"]
    f0, f1 = int(round(plan["t0"] * fps)), int(round(plan["t1"] * fps))
    jobs = [(f, os.path.join(out_dir, "f%05d.png" % f), fps) for f in range(f0, f1)]
    lock = _acquire_lock(out_dir)
    t0 = time.time(); done = 0; stats = {"retries": 0, "stale_moved": 0, "timeouts": 0, "cancelled": False}
    try:
        stamp = engine_stamp(plan, designs, fps); sp = os.path.join(out_dir, "_stamp_%d_%d.json" % (f0, f1))
        old = json.load(open(sp, encoding="utf-8")).get("stamp") if os.path.exists(sp) else None
        existing = [j for j in jobs if os.path.exists(j[1])]
        if existing and old != stamp:                       # motor/varlık/plan değişti (veya damga yok): eski kareleri körlemesine kullanma
            qd = out_dir + "_stale_" + time.strftime("%H%M%S"); os.makedirs(qd, exist_ok=True)
            for j in existing:
                os.replace(j[1], os.path.join(qd, os.path.basename(j[1])))
            stats["stale_moved"] = len(existing)
        json.dump({"stamp": stamp, "fps": fps, "created": time.strftime("%Y-%m-%d %H:%M:%S")}, open(sp, "w", encoding="utf-8"))
        for fn in os.listdir(out_dir):                      # yarım kalmış geçici dosyalar
            if fn.endswith(".tmp.png"):
                os.replace(os.path.join(out_dir, fn), os.path.join(out_dir, fn + ".bad"))
        need_n = len([j for j in jobs if not valid_png(j[1])])
        sizes = [os.path.getsize(j[1]) for j in jobs[:200] if os.path.exists(j[1])][:30]
        avg = (sum(sizes) / len(sizes)) if sizes else 1.3e6                  # ölçülmüş kare boyutu yoksa 1,3 MB varsay
        need = int(need_n * avg * 1.3 + 200e6)                                # %30 pay + klip/geçici dosya payı
        free = shutil.disk_usage(out_dir).free
        stats["disk_free_mb"] = int(free / 1e6); stats["disk_need_mb"] = int(need / 1e6)
        if need_n and free < need:                                            # alan yetmiyorsa işi BAŞLATMA (yarım kare ve ENOSPC çöküşü yok)
            stats["disk_blocked"] = True
            print("DUR: disk yetersiz: boş %d MB < gereken %d MB" % (free / 1e6, need / 1e6), flush=True)
            return {"rendered": 0, "missing": need_n, "seconds": 0.0, "sec_per_frame": None, "engine": "puppet2d", **stats}
        w = pick_workers(workers)
        stats["workers_start"] = w; stats["mem_mb"] = available_mem_mb()
        cancel = os.path.join(out_dir, ".cancel")
        for attempt in range(4):
            todo = [j for j in jobs if not valid_png(j[1])]
            if not todo or os.path.exists(cancel):
                stats["cancelled"] = os.path.exists(cancel)
                break
            try:
                if w == 1:                                  # güvenli tek işçi yolu: ayrı süreç yok
                    _init(plan, designs)
                    for j in todo:
                        if os.path.exists(cancel):
                            stats["cancelled"] = True; break
                        done += _work(j); _beat_lock(lock)
                else:
                    ex = ProcessPoolExecutor(w, initializer=_init, initargs=(plan, designs))
                    try:
                        pending = set(); it = iter(todo); n = 0
                        while True:
                            while len(pending) < w * window_mult:       # sınırlı kuyruk: bellekte en çok w*3 görev
                                try:
                                    pending.add(ex.submit(_work, next(it)))
                                except StopIteration:
                                    break
                            if not pending:
                                break
                            fin, pending = wait(pending, timeout=frame_timeout, return_when=FIRST_COMPLETED)
                            if not fin:
                                stats["timeouts"] += 1
                                raise TimeoutError("kare zaman aşımı (%ds)" % frame_timeout)
                            for fu in fin:
                                done += fu.result(); n += 1
                            _beat_lock(lock)
                            if progress and n % 48 < len(fin):
                                print("PROGRESS kare=%d/%d  %.2f sn/kare" % (n, len(todo), (time.time() - t0) / max(1, n)), flush=True)
                            if os.path.exists(cancel):
                                stats["cancelled"] = True; break
                    finally:
                        for p_ in list(getattr(ex, "_processes", {}).values()):
                            try:
                                p_.terminate()                    # yalnız KENDİ başlattığımız işçiler
                            except Exception:
                                pass
                        ex.shutdown(wait=False, cancel_futures=True)
                break
            except (BrokenProcessPool, MemoryError, TimeoutError, RuntimeError) as e:
                stats["retries"] += 1
                print("UYARI: %s (%s); işçi sayısı %d -> %d" % (type(e).__name__, e, w, max(1, w // 2)), flush=True)
                w = max(1, w // 2)
        stats["workers_end"] = w
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass
    missing = len([j for j in jobs if not valid_png(j[1])])
    el = time.time() - t0
    return {"rendered": done, "missing": missing, "seconds": round(el, 1), "sec_per_frame": round(el / done, 3) if done else None, "engine": "puppet2d", **stats}
