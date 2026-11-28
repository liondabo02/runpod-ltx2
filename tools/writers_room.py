#!/usr/bin/env python3
"""AHOS Yazarlar Odası işçisi: Yazar -> Eleştirmen -> Düzeltmen (en çok 2 tur).

Yalnız standart kütüphane. LLM'e OpenAI uyumlu uçtan (OmniRoute) bağlanır.
Kullanım:
  python tools/writers_room.py --series series/<id>/series-bible.json \
      --idea "bir cümlelik fikir" --out out/s01e002 [--seconds 480]
Ortam: AHOS_LLM_BASE (varsayılan http://localhost:20128/v1), AHOS_LLM_KEY (varsa),
       AHOS_LLM_MODEL (varsayılan auto)
Ücretli çağrı yapmaz; yaratıcı onay VERMEZ (status her zaman DRAFT_FOR_OWNER_APPROVAL).
"""
import argparse, hashlib, json, os, re, sys, time, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_beat_sheet import validate  # noqa: E402
import lessons  # noqa: E402
import llm_guard  # noqa: E402
import worker_events as we  # noqa: E402

ACT_SECONDS = 40
PASS_SCORE = 80


def say(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def llm_call(system, user, temperature=0.7):
    base = os.environ.get("AHOS_LLM_BASE", "http://localhost:20128/v1").rstrip("/")
    key = os.environ.get("AHOS_LLM_KEY", "")
    g = llm_guard.check(os.environ.get("AHOS_LLM_MODEL", "auto"), base)
    if not g["ok"]:
        raise RuntimeError("LLM_ODENEK_ENGELI: " + g["reason"])
    body = {"model": os.environ.get("AHOS_LLM_MODEL", "auto"), "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    data = json.dumps(body).encode()
    hdr = {"Content-Type": "application/json", **({"Authorization": "Bearer " + key} if key else {})}
    last = None
    for attempt in range(1, 7):          # ücretsiz modeller takılabilir: yeniden dene (auto her seferinde başka hedef seçebilir)
        we.note("yazı modeline istek gönderdi, yanıt bekliyor" + (" (deneme %d)" % attempt if attempt > 1 else ""))
        req = urllib.request.Request(base + "/chat/completions", data, hdr)
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                txt = json.load(r)["choices"][0]["message"]["content"]
                if txt and str(txt).strip():
                    return txt
                last = "LLM boş yanıt döndürdü"
        except urllib.error.HTTPError as e:
            last = f"LLM HTTP {e.code}: {e.read()[:300]!r}"
            if e.code not in (401, 408, 429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = f"LLM bağlantı hatası: {e}"
        time.sleep(min(3 * attempt, 20))
    raise RuntimeError(last)


def extract_json(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    s = m.group(1) if m else text
    a = min([i for i in (s.find("{"), s.find("[")) if i >= 0] or [0])
    b = max(s.rfind("}"), s.rfind("]"))
    raw = s[a:b + 1]
    try:
        return json.loads(raw)
    except ValueError:
        return json.loads(repair_json(raw))


def repair_json(raw):
    """Ücretsiz modellerin sık yaptığı hatalar: eksik virgül, fazla virgül, kesik kapanış, akıllı tırnak."""
    t = raw.replace("\u201c", '"').replace("\u201d", '"')
    t = re.sub(r'([}\]"0-9el])\s*\n\s*(["{\[])', r'\1,\n\2', t)        # satır sonunda eksik virgül
    t = re.sub(r'}\s*{', '},{', t)
    t = re.sub(r',\s*([}\]])', r'\1', t)                                  # fazla virgül
    stack = []; instr = False; esc = False
    for ch in t:
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
        elif ch == '"': instr = True
        elif ch in "{[": stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack: stack.pop()
    if instr: t += '"'
    return t + "".join(reversed(stack))



def llm_json(system, user, temperature=0.7, need=None, tries=7):
    """LLM'den JSON iste; bozuk/boş/eksik anahtarlı yanıtta yeniden dene (ücretsiz modeller sık takılır)."""
    last = None
    for i in range(tries):
        try:
            txt = llm_call(system, user + ("\n\nÖNEMLİ: yalnızca geçerli JSON döndür, başka metin yok." if i else ""),
                           max(0.1, temperature - 0.15 * i))
            data = extract_json(txt)
            if need and not (isinstance(data, dict) and all(k in data for k in need)):
                raise ValueError(f"eksik anahtar: {need}")
            return data
        except (ValueError, KeyError, TypeError, RuntimeError) as e:
            last = e
            time.sleep(min(4 * (i + 1), 25))
    raise RuntimeError(f"LLM geçerli JSON üretemedi ({tries} deneme): {last}")

def bible_summary(bible):
    chars = [{"id": c["id"], "name": c.get("name"), "age": c.get("age"), "role": c.get("role"),
              "safety_notes": c.get("safety_notes", [])} for c in bible.get("characters", [])]
    locs = [{"id": l["id"], "name": l.get("name")} for l in bible.get("locations", [])]
    return json.dumps({"series": bible.get("title"), "age_band": bible.get("age_band"),
                       "tone": bible.get("tone"), "characters": chars, "locations": locs},
                      ensure_ascii=False)


WRITER_SYS = ("Sen bir çocuk çizgi filmi senaristisin. SADECE geçerli JSON döndür. "
              "Kamerada görünen somut eylem yaz; diyalog az olabilir; dersi sloganla değil davranışla göster. "
              "Yetişkin kontrolü olmadan bebeğe ip, şerit, küçük parça verme. Bible dışında karakter/mekân kullanma. "
              "DİL: sade, doğru, günlük Türkçe; kelime UYDURMA, İngilizce kelime/kamera jargonu (worm's-eye vb.) kullanma, kamerayı Türkçe yaz. "
              "ÇEŞİTLİLİK: art arda iki vuruşta aynı eylemi yazma; her vuruşta yeni bir somut olay, tepki veya espri olsun. "
              "DİYALOG: karakterler konuşsun; her 2-3 vuruştan en az birinde 1-2 kısa, karaktere özgü cümle olsun (çocuk dili, tek cümle 8 kelimeyi geçmesin). Diyalog biçimi KESİN: \"karakter_id: cümle\" ; birden fazla konuşan varsa ' | ' ile ayır (örn. \"pelin: Bak! | tosun: Nerede?\"). karakter_id bible'daki id olmalı. "
              "YAPI VE EĞLENCE: bölümde net bir amaç, engel ve çözüm olsun (kuru anlatım değil); her 3-4 vuruşta bir görsel espri/şaşırtma (kayma, yanlış anlama, abartılı tepki) koy; "
              "bölüm sonunda küçük bir sürpriz veya sıcak kapanış olsun. "
              "GÖRÜNÜRLÜK: 'action' metninde olay örgüsünün nesnelerini adıyla yaz (tohum, taş, şapka, şişe, kürek, çiçek...) ve karakterin ne yaptığını fiille söyle; çizim motoru bu kelimeleri sahnede gösterir. "
              "MEKÂN: bible'daki mekânlar arasında geçiş yap (en az iki farklı mekân kullan), her mekânda farklı eylem olsun.")
CRITIC_SYS = ("Sen KATI, bağımsız bir senaryo eleştirmenisin. SADECE JSON döndür: "
              '{"scores":{"merak":0-20,"yas_uygunluk":0-20,"kimlik_surekliligi":0-20,"eylem_cesitliligi":0-15,'
              '"ses_duygu":0-15,"guvenlik":0-10},"findings":[{"beat":int,"priority":"P0|P1|P2","issue":"","fix":""}]}. '
              "KURALLAR: findings'e YALNIZ sorunları yaz; övgü YAZMA. Her bulgu için somut 'fix' öner. "
              "Anlamsız/bozuk Türkçe cümle, tekrar eden eylem, yaşa uygun olmayan içerik, karakter tutarsızlığı birer sorundur. "
              "Ortalama bir senaryo 60-75 alır; 85 üstü yalnız kusursuz işe verilir. Beat numaraları listedeki sıraya göre 0'dan başlar.")




def _cache_load(out_dir, key):
    try:
        d = json.load(open(os.path.join(out_dir, "acts_cache.json"), encoding="utf-8"))
        return d if d.get("key") == key else {"key": key, "outline": None, "acts": {}}
    except Exception:
        return {"key": key, "outline": None, "acts": {}}


def _cache_save(out_dir, c):
    os.makedirs(out_dir, exist_ok=True)
    json.dump(c, open(os.path.join(out_dir, "acts_cache.json"), "w", encoding="utf-8"), ensure_ascii=False)


def need_beats(t0, t1):
    return max(1, round((t1 - t0) / 7.5))


def split_long(beats, t0, t1, max_len=9.5):
    """Son çare: model yeterli vuruş yazmadıysa uzun vuruşları kodla böl (diyalog satırları sırayla dağıtılır)."""
    out = []
    for b in beats:
        try:
            d = float(b.get("t_end")) - float(b.get("t_start"))
        except Exception:
            d = 8.0
        parts = max(1, int(-(-d // max_len)))
        if parts == 1:
            out.append(b); continue
        lines = [x.strip() for x in str(b.get("dialogue") or "").split("|") if x.strip()]
        for k in range(parts):
            c = dict(b)
            c["dialogue"] = " | ".join(lines[k::parts]) if lines else ""
            if k:
                c["action"] = f"Sahne sürüyor ({k+1}/{parts}): " + str(b.get("action", ""))
            c["t_start"], c["t_end"] = 0, 8       # normalize_act süreleri yeniden hesaplar
            out.append(c)
    return out


SOURCE = {"text": None}   # sahibin senaryosu; doluysa yazarlar METNE SADIK kalır


def set_source(text):
    SOURCE["text"] = text or None


FAITHFUL = ("SADAKAT MODU: Sahibin yazdığı senaryo KANUNDUR. Olayları, sırayı, mekânları, karakter adlarını ve repliklerini DEĞİŞTİRME, "
            "yeni olay/karakter/replik UYDURMA, hiçbir olayı atlama. Görevin yalnız metni vuruşlara bölmek, kamerayı/eylemi görünür hâle getirmek "
            "ve replikleri biçime çevirmektir. Metinde olmayan şeyi yalnız geçiş/hareket gerekiyorsa ekle.")


def _source_slice(act_no, n_acts):
    paras = [p for p in re.split(r"\n\s*\n", SOURCE["text"] or "") if p.strip()]
    if not paras:
        return ""
    a = int(len(paras) * (act_no - 1) / n_acts); b = max(a + 1, int(round(len(paras) * act_no / n_acts)))
    return "\n\n".join(paras[a:b])


def write_outline(bible, idea, seconds):
    if SOURCE["text"]:
        n = max(1, round(seconds / ACT_SECONDS))
        u = (f"Bible: {bible_summary(bible)}\nSAHİBİN SENARYOSU:\n{SOURCE['text'][:12000]}\nToplam {seconds} sn, {n} perde. Perdeleri senaryonun sırasına göre böl. "
             f'JSON: {{"title":"","logline":"","acts":[{{"act":1,"summary":"","location_id":"","goal":"","obstacle":""}}]}}')
        return llm_json(WRITER_SYS + " " + FAITHFUL + lessons.prompt_block("writer"), u, need=["acts"])
    n = max(1, round(seconds / ACT_SECONDS))
    u = (f"Bible: {bible_summary(bible)}\nFikir: {idea}\nToplam {seconds} sn, {n} perde. "
         f'JSON: {{"title":"","logline":"","acts":[{{"act":1,"summary":"","location_id":"","goal":"","obstacle":""}}]}}')
    return llm_json(WRITER_SYS + lessons.prompt_block("writer"), u, need=["acts"])


def write_act(bible, outline, act_no, t0, t1, notes=None, prev_tail=None):
    a = outline["acts"][act_no - 1]
    src = _source_slice(act_no, len(outline["acts"])) if SOURCE["text"] else ""
    u = (f"Bible: {bible_summary(bible)}\nPerde {act_no}/{len(outline['acts'])}: {json.dumps(a, ensure_ascii=False)}\n"
         f"{('BU PERDENİN SENARYO METNİ (sadık kal):' + chr(10) + src + chr(10)) if src else ''}"
         f"Zaman aralığı: {t0}-{t1} sn. TAM OLARAK {need_beats(t0, t1)} vuruş yaz (vuruş başına 6-9 sn), aralıksız ve kesintisiz; her vuruşta en az bir diyalog satırı olsun.\n"
         + (f"Önceki perde sonu: {prev_tail}\n" if prev_tail else "")
         + (f"Düzeltilecek eleştiriler: {json.dumps(notes, ensure_ascii=False)}\n" if notes else "")
         + 'JSON: {"beats":[{"t_start":0,"t_end":6,"scene_id":"","location":"<bible id>","light_time":"",'
           '"characters":["<bible id>"],"action":"","dialogue":"","emotion":{"valence":0,"arousal":0,"intensity":0},'
           '"camera":"","sound":"","safety_note":""}]}')
    return llm_json(WRITER_SYS + (" " + FAITHFUL if SOURCE["text"] else "") + lessons.prompt_block("writer"), u, need=["beats"])["beats"]




def _lev1(a, b):
    """Düzenleme mesafesi <= 1 mi? (yazım hatası tespiti)"""
    if a == b: return False
    if abs(len(a) - len(b)) > 1: return False
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1; j += 1
        else:
            d += 1
            if d > 1: return False
            if len(a) > len(b): i += 1
            elif len(a) < len(b): j += 1
            else: i += 1; j += 1
    return d + (len(a) - i) + (len(b) - j) <= 1


def fix_names(beats, bible):
    """Modelin karakter adlarını yanlış yazması (Tosan -> Tosun) kodla düzeltilir; modele güvenilmez."""
    names = {}
    for c in bible.get("characters", []):
        nm = (c.get("name") or "").strip()
        if len(nm) >= 4 and " " not in nm:
            names[nm.casefold()] = nm
    if not names: return 0
    fixed = 0
    def repl(m):
        nonlocal fixed
        w = m.group(0); wl = w.casefold()
        if wl in names: return names[wl] if w[0].isupper() else names[wl].lower() if False else w
        for k, nm in names.items():
            if _lev1(wl, k) and w[0].isupper() and wl[0] == k[0]:   # özel ad gibi büyük harfli VE ilk harf aynı ('Gelin'->'Pelin' yanlışını önler)
                fixed += 1
                return nm
        return w
    for b in beats:
        for key in ("action", "dialogue"):
            if isinstance(b.get(key), str):
                b[key] = re.sub(r"[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]+", repl, b[key])
    return fixed


PROOF_SYS = ("Sen bir Türkçe dil editörüsün. SADECE JSON döndür. Çocuk çizgi filmi senaryosundaki yazım hatalarını, "
             "anlamsız/uydurma kelimeleri ve bozuk cümleleri düzelt; anlamı, sırayı ve karakter adlarını KORU. "
             "Cümleyi gereksiz uzatma. Diyalogdaki 'Ad:' konuşan etiketlerini aynen bırak. İngilizce kelime kullanma.")


def proofread(beats, chunk=12):
    """Dil editörü: action/dialogue metinlerini düzeltir; süre/karakter/sayı DEĞİŞMEZ. Başarısızsa orijinal kalır."""
    changed = 0
    for s0 in range(0, len(beats), chunk):
        part = beats[s0:s0 + chunk]
        payload = [{"i": s0 + k, "action": b.get("action", ""), "dialogue": b.get("dialogue", "")} for k, b in enumerate(part)]
        try:
            data = llm_json(PROOF_SYS, "Düzelt ve aynı yapıda döndür: " + json.dumps({"beats": payload}, ensure_ascii=False),
                            temperature=0.2, need=["beats"], tries=3)
        except RuntimeError:
            continue
        for it in data["beats"]:
            try: i = int(it["i"])
            except Exception: continue
            if not (s0 <= i < s0 + len(part)): continue
            b = beats[i]
            for key in ("action", "dialogue"):
                new, old = it.get(key), b.get(key, "")
                if isinstance(new, str) and new.strip() and isinstance(old, str) and old and 0.5 <= len(new) / len(old) <= 1.8 and new != old:
                    b[key] = new.strip(); changed += 1
                elif isinstance(new, str) and not old:
                    pass
    return changed

def normalize_act(beats, t0, t1, act_no, default_loc=None, valid_locs=None):
    """Modelin zaman kodlarına güvenme: süreleri kodla yeniden hesapla, eksik zorunlu alanları işaretle."""
    beats = [b for b in beats if isinstance(b, dict)]
    if not beats:
        return beats
    durs = []
    for b in beats:
        try:
            d = float(b.get("t_end")) - float(b.get("t_start"))
        except Exception:
            d = 8.0
        durs.append(min(10.0, max(5.0, d)))
    k = (t1 - t0) / sum(durs)
    t = float(t0)
    for i, (b, d) in enumerate(zip(beats, durs)):
        b["t_start"] = round(t, 1)
        t += d * k
        b["t_end"] = round(t if i < len(beats) - 1 else float(t1), 1)
        b.setdefault("scene_id", f"act{act_no}")
        if not b.get("scene_id"):
            b["scene_id"] = f"act{act_no}"
        if not b.get("sound"):
            b["sound"] = "ortam sesi (varsayılan)"
        if default_loc and (not b.get("location") or (valid_locs and b["location"] not in valid_locs)):
            b["location"] = default_loc
        b.setdefault("dialogue", "")
    return beats

def build(bible, outline, seconds, notes_by_act=None, cache=None, out_dir=None):
    """Perdeler paralel yazılır (AHOS_ACT_PARALLEL, varsayılan 3): ücretsiz LLM'ler yavaş; süreklilik için önceki perdenin PLANI verilir."""
    from concurrent.futures import ThreadPoolExecutor
    n = len(outline["acts"]); step = seconds / n
    locs = {l["id"] for l in bible.get("locations", [])}
    lock = __import__("threading").Lock()
    done = {}

    def gen(i):
        t0, t1 = round((i - 1) * step), round(i * step)
        if cache is not None and not notes_by_act and str(i) in cache["acts"]:
            say(f"Perde {i}/{n}: önceki denemeden alındı.")
            return i, cache["acts"][str(i)]
        say(f"Perde {i}/{n} yazılıyor ({t0}-{t1} sn)...")
        prev = outline["acts"][i - 2].get("summary") if i > 1 else None
        tail = ("önceki perdenin özeti: " + str(prev)) if prev else None
        dl = outline["acts"][i - 1].get("location_id")
        got = write_act(bible, outline, i, t0, t1, (notes_by_act or {}).get(i), tail)
        want = need_beats(t0, t1)
        for _ in range(2):                       # model az vuruş yazdıysa sayıyı açıkça isteyip tekrar dene
            if len([x for x in got if isinstance(x, dict)]) >= want * 0.8:
                break
            try:
                got = write_act(bible, outline, i, t0, t1, [{"issue": f"Yalnız {len(got)} vuruş yazdın; TAM {want} vuruş yaz, her biri 6-9 sn."}], tail)
            except RuntimeError:
                break
        if len([x for x in got if isinstance(x, dict)]) < want * 0.8:
            got = split_long([x for x in got if isinstance(x, dict)], t0, t1)
        res = normalize_act(got, t0, t1, i, dl if dl in locs else None, locs)
        if cache is not None and not notes_by_act:
            with lock:
                cache["acts"][str(i)] = res
                _cache_save(out_dir, cache)
        say(f"Perde {i}/{n} hazır.")
        return i, res

    workers = max(1, int(os.environ.get("AHOS_ACT_PARALLEL", "3")))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(gen, i) for i in range(1, n + 1)]
        errs = []
        for f in futs:
            try:
                i, res = f.result(); done[i] = res
            except Exception as e:   # biri düşerse kalanlar yine de önbelleğe yazılır; sonra hata verilir
                errs.append(e)
    if errs:
        raise errs[0]
    beats = []
    for i in range(1, n + 1):
        beats += done[i]
    fix_names(beats, bible)
    return beats


def critique(beats, bible):
    u = f"Bible: {bible_summary(bible)}\nBeats: {json.dumps(beats, ensure_ascii=False)}"
    c = llm_json(CRITIC_SYS + lessons.prompt_block("critic"), u, temperature=0.2, need=["scores"])
    total = sum(c["scores"].values())
    return total, c


def save(out_dir, outline, beats, seconds, bible, history, errs, total):
    os.makedirs(out_dir, exist_ok=True)
    sheet = {"schema": "ahos.beat_sheet.v1", "status": "DRAFT_FOR_OWNER_APPROVAL",
             "series_id": bible.get("series_id"), "title": outline.get("title"), "logline": outline.get("logline"),
             "total_seconds": seconds, "beats": beats}
    with open(os.path.join(out_dir, "beat_sheet.json"), "w", encoding="utf-8") as f:
        json.dump(sheet, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "writers_room_report.json"), "w", encoding="utf-8") as f:
        json.dump({"history": history, "final_validator_errors": errs, "final_score": total,
                   "creative_approval": "OWNER_ONLY"}, f, ensure_ascii=False, indent=2)
    return sheet


def run(bible, idea, seconds, out_dir, rounds=2):
    key = hashlib.sha1(json.dumps([bible.get("series_id"), idea, seconds], ensure_ascii=False).encode()).hexdigest()[:12]
    cache = _cache_load(out_dir, key)
    if cache.get("outline"):
        say("Perde planı önceki denemeden alındı.")
        outline = cache["outline"]
    else:
        say("Taslak (perde planı) yazılıyor...")
        outline = write_outline(bible, idea, seconds)
        cache["outline"] = outline; _cache_save(out_dir, cache)
    beats = build(bible, outline, seconds, cache=cache, out_dir=out_dir)
    history, best = [], None
    n = len(outline["acts"]); step = seconds / n
    for r in range(rounds + 1):
        errs, warns = validate({"beats": beats}, bible, seconds)
        say(f"Tur {r}: doğrulayıcı hata {len(errs)}; eleştirmen puanlıyor...")
        try:
            total, crit = critique(beats, bible)
        except RuntimeError as e:           # eleştirmen cevap vermezse doğrulayıcıya güven
            total, crit = 0, {"scores": {}, "findings": [], "note": str(e)}
        safety_ok = crit["scores"].get("guvenlik", 10) >= 10
        say(f"Tur {r}: puan {total}, hata {len(errs)}")
        history.append({"round": r, "validator_errors": errs, "score": total, "findings": crit.get("findings", [])})
        key = (len(errs), -total)
        if best is None or key < best[0]:
            best = (key, beats, errs, total)
            save(out_dir, outline, beats, seconds, bible, history, errs, total)   # kontrol noktası
        if not errs and total >= PASS_SCORE and safety_ok:
            break
        if r == rounds:
            break
        notes = {}
        for f in crit.get("findings", []):
            if isinstance(f.get("beat"), int) and 0 <= f["beat"] < len(beats):
                act = min(n, int(float(beats[f["beat"]]["t_start"]) // step) + 1)
                notes.setdefault(act, []).append(f)
        for e in errs[:20]:
            notes.setdefault(1, []).append({"issue": e})
        try:
            beats = build(bible, outline, seconds, notes or None)
        except RuntimeError as e:
            history.append({"round": r + 1, "repair_failed": str(e)})
            break
    _, beats, errs, total = best
    say("Dil editörü metni düzeltiyor...")
    n_fix = proofread(beats)
    n_names = fix_names(beats, bible)
    errs, _ = validate({"beats": beats}, bible, seconds)
    history.append({"proofread_changes": n_fix, "name_fixes": n_names})
    sheet = save(out_dir, outline, beats, seconds, bible, history, errs, total)
    last = {"validator_errors": errs, "score": total, "proofread_changes": n_fix, "name_fixes": n_names}
    return sheet, [h for h in history if "score" in h] + [last]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--series", required=True); p.add_argument("--idea", required=True)
    p.add_argument("--out", required=True); p.add_argument("--seconds", type=int, default=480)
    a = p.parse_args()
    bible = json.load(open(a.series, encoding="utf-8"))
    sheet, hist = run(bible, a.idea, a.seconds, a.out)
    last = hist[-1]
    print(f"Tur: {len(hist)} | Doğrulayıcı hata: {len(last['validator_errors'])} | Eleştirmen puanı: {last['score']}")
    print("Çıktı:", os.path.join(a.out, "beat_sheet.json"))
    print("Durum: DRAFT_FOR_OWNER_APPROVAL (yaratıcı onay yalnız sahibindedir)")


if __name__ == "__main__":
    main()
