"""AHOS 2D kare çizici: plan + poz -> PNG kareleri (çok işlemcili, kaldığı yerden devam)."""
import json, math, os, sys, time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shot_motion as sm  # noqa: E402
import puppet2d as pp  # noqa: E402
import scenes2d as sc  # noqa: E402
import props2d
import setpieces2d  # noqa: E402
import fx_layer  # noqa: E402
try:
    import bg_art  # noqa: E402
except ImportError:      # arka plan boyama katmanı yoksa eski görünüm
    bg_art = None

EMO = {"laugh": "laugh", "surprise": "surprise", "jump": "happy", "dance": "happy", "run": "happy", "wave": "happy"}
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
        args = (m["kind"], 0, dur, m["seed"], m["x0"], m["x1"], Hm, Hm * 0.45)
        spk = (cid == speaker)
        p = sm.pose_at(args[0], lt, *args[2:], speaking=spk)
        # takip (follow-through): kollar gövdeden, kafa da biraz geriden gelir
        pa = sm.pose_at(args[0], max(0.0, lt - 0.11), *args[2:], speaking=spk)
        ph_ = sm.pose_at(args[0], max(0.0, lt - 0.05), *args[2:], speaking=spk)
        p["aL"], p["aR"], p["head"] = list(pa["aL"]), list(pa["aR"]), list(ph_["head"])
        look = 0.0
        if speaker and cid != speaker and speaker in px:            # dinleyen konuşana bakar
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
    if speaker and speaker in beat["cast"]:       # yakın planda kamera hep o an konuşana bakar (yüz + omuz kadrajda)
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
    if speaker and speaker in beat["cast"] and preset in ("close", "xclose"):
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
    sc.scene_back(cv, beat["scene"], cam, t)
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
    for cid, d, p, m, look, e in sorted(items, key=lambda it: it[2]["x"]):
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
    for k_, kind in enumerate(beat.get("props") or []):
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


def _init(plan, designs):
    _G["plan"], _G["des"] = plan, designs


def _work(args):
    f, path, fps = args
    if os.path.exists(path):
        return 0
    im = frame(_G["plan"], _G["des"], f / float(fps))
    if im is None:
        return 0
    im.save(path)
    return 1


def render_window(plan, designs, out_dir, workers=None, progress=True):
    os.makedirs(out_dir, exist_ok=True)
    fps = plan["fps"]
    f0, f1 = int(round(plan["t0"] * fps)), int(round(plan["t1"] * fps))
    jobs = [(f, os.path.join(out_dir, "f%05d.png" % f), fps) for f in range(f0, f1)]
    t0 = time.time(); done = 0
    workers = workers or max(1, min(4, (os.cpu_count() or 2) - 1))          # bellek: işçi başına ~400 MB; en çok 4
    from concurrent.futures.process import BrokenProcessPool
    for attempt in range(3):                                                # işçi çökerse (ör. MemoryError) eksik kareleri daha az işçiyle tamamla
        todo = [j for j in jobs if not os.path.exists(j[1])]
        if not todo:
            break
        try:
            if workers == 1:
                _init(plan, designs)
                for j in todo:
                    done += _work(j)
            else:
                with ProcessPoolExecutor(workers, initializer=_init, initargs=(plan, designs)) as ex:
                    for i, r in enumerate(ex.map(_work, todo, chunksize=2)):
                        done += r
                        if progress and (i + 1) % 48 == 0:
                            print("PROGRESS kare=%d/%d  %.2f sn/kare" % (i + 1, len(todo), (time.time() - t0) / (i + 1)), flush=True)
            break
        except (BrokenProcessPool, MemoryError) as e:
            print("UYARI: işçi çöktü (%s); %d kare eksik, işçi sayısı azaltılıyor" % (type(e).__name__, len([j for j in jobs if not os.path.exists(j[1])])), flush=True)
            workers = max(1, workers // 2)
    el = time.time() - t0
    return {"rendered": done, "seconds": round(el, 1), "sec_per_frame": round(el / done, 3) if done else None, "engine": "puppet2d"}
