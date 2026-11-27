"""Canlı ofis: işçilerin durumunu yalnız gerçek olaylardan ve kuyruktan türetir; CEO ile konuşma.

CEO kendi başına iş başlatmaz: görev ÖNERİR, sahip onaylayınca mevcut kuyruğa (studio_enqueue) girer.
Durum soruları model kullanılmadan kayıtlardan yanıtlanır; böylece CEO ilerleme uyduramaz."""
import json, os, re, urllib.request

# Çalışırken canlı bildirim gönderen işçiler (motor kodunda bağlı). Diğerleri için ofis 'çalışıyor' diyemez.
INSTRUMENTED = ("showrunner", "director", "writers_room", "validator", "voice", "animatic", "character", "render", "video_qa")


def derive(workers, events, running_ids, alive, now):
    """workers: [(id, ad, görev, _)] -> işçi durumları. 'working' yalnız: stüdyo canlı + iş şu an çalışıyor + start kapanmamış."""
    running_ids = set(running_ids)
    out = {}
    for w in workers:
        out[w[0]] = {"id": w[0], "name": "CEO (Yapımcı)" if w[0] == "showrunner" else w[1], "role": w[2], "live": w[0] in INSTRUMENTED,
                     "state": "idle", "text": "", "since": None, "job": None, "last": None, "history": []}
    for e in events:
        s = out.get(e["worker"])
        if not s:
            continue
        s["history"].append(e)
        k = e["kind"]
        if k == "start":
            s.update(state="working", text=e["text"], since=e["at"], job=e["job"], last=None)
        elif k == "note":
            if s["state"] == "working" and s["job"] == e["job"]:
                s["text"] = e["text"]
        else:
            dur = round(e["at"] - s["since"], 1) if s["state"] == "working" and s["job"] == e["job"] and s["since"] else None
            s.update(state="idle", text="", since=None, job=e["job"],
                     last={"ok": k == "done", "text": e["text"], "at": e["at"], "seconds": dur, "job": e["job"]})
    # kuyruk "tamamlandı" dese de aynı işte hata veren işçi varsa CEO bunu başarı göstermez
    boss = out.get("showrunner")
    if boss and boss["last"] and boss["last"]["ok"]:
        job = boss["last"]["job"]
        bad = {e["worker"] for e in events if e["job"] == job and e["kind"] == "failed" and e["worker"] != "showrunner"}
        if bad:
            boss["last"].update(ok=False, text="iş bitti ama sorunlu: " + ", ".join(sorted(out[w]["name"] for w in bad if w in out)))
    for s in out.values():
        if s["state"] == "working" and not (alive and s["job"] in running_ids):
            s.update(state="interrupted", text="yarım kaldı: " + s["text"])
        s["history"] = s["history"][-15:]
    return [out[w[0]] for w in workers]


def facts(live, jobs, alive):
    """CEO'nun durum raporu: yalnız kayıttaki bilgiler."""
    L = []
    L.append("Stüdyo açık." if alive else "Stüdyo kapalı: şu anda kimse çalışmıyor.")
    pend = [j for j in jobs if j["state"] == "pending"]
    busy = [w for w in live if w["state"] == "working"]
    for w in busy:
        L.append("%s çalışıyor: %s" % (w["name"], w["text"]))
    if alive and not busy:
        L.append("Şu an çalışan işçi kaydı yok.")
    if pend:
        L.append("Sırada bekleyen iş: %d." % len(pend))
    for w in live:
        if w["state"] == "interrupted":
            L.append("%s: %s" % (w["name"], w["text"]))
    last_job = next((e["job"] for w in live if w["id"] == "showrunner" for e in reversed(w["history"])), None)
    if last_job:
        res = [w for w in live if w["last"] and w["job"] == last_job and w["id"] != "showrunner"]
        if res:
            L.append("Son işin sonuçları:")
            L += ["- %s: %s (%s)" % (w["name"], "tamam" if w["last"]["ok"] else "SORUN", w["last"]["text"]) for w in res]
        boss = next(w for w in live if w["id"] == "showrunner")
        if boss["last"] and not boss["last"]["ok"]:
            L.append("Genel sonuç BAŞARILI DEĞİL: " + boss["last"]["text"])
    return "\n".join(L)


_TR = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _norm(t):
    return t.replace("İ", "i").replace("I", "ı").lower().translate(_TR)


STATUS = r"\b(durum\w*|rapor\w*|ne yapiyor\w*|ne yapiyosun\w*|neler oluyor|nerede kal\w*|bitti mi|hazir mi|kim calisiyor|ilerleme\w*|sonuc\w*|sorun var mi)\b"
STOP = r"^(lutfen )?(isi |uretimi |gorevi )?(durdur|iptal et|iptal)\b"
ORDER_VERB = r"\b(hazirla|hazirlayin|yap|yapin|uret|uretin|yaz|yazin|olustur|olusturun|cek|cekin|baslat|baslatin)\b"
QUESTION = r"(\?\s*$|\b(mi|mu|misin|musun|misiniz|musunuz|nasil|neden|niye)\b)"


def classify(msg):
    n = _norm(msg).strip()
    if re.search(STOP, n):
        return "stop"
    if re.search(STATUS, n) and not re.search(ORDER_VERB, n):
        return "status"
    if re.search(ORDER_VERB, n):
        # 'yapabilir misin?' gibi sorular görev sayılmaz; emir fiili yalın hâlde olmalı
        return "task"
    if re.search(r"\b(bolum|film|sahne)\b", n) and not re.search(QUESTION, n) and len(n.split()) >= 4:
        return "task"
    return "chat"


CEO_SYS = ("Sen bir çizgi film stüdyosunun yapay zekâ CEO'susun. Sahibinle kısa, sade Türkçe konuş (en çok 4 cümle). "
           "Üretim durumu hakkında YALNIZ sana verilen KAYITLAR bölümündekileri söyle; olmayan ilerleme, sonuç veya yetenek uydurma. "
           "Sen buradan iş başlatamazsın: sahip iş istiyorsa 'hazırla' diye açık bir görev yazmasını söyle; ofis onay düğmesi gösterir.")


def model_reply(msg, context, env=None, opener=urllib.request.urlopen, timeout=60):
    """Mevcut yazı modeli ayarıyla (AHOS_LLM_*) tek deneme. Erişilemezse None."""
    env = os.environ if env is None else env
    base = env.get("AHOS_LLM_BASE", "http://localhost:20128/v1").rstrip("/")
    key = env.get("AHOS_LLM_KEY", "")
    body = {"model": env.get("AHOS_LLM_MODEL", "auto"), "temperature": 0.4,
            "messages": [{"role": "system", "content": CEO_SYS + "\n\nKAYITLAR:\n" + context}, {"role": "user", "content": msg}]}
    hdr = {"Content-Type": "application/json", **({"Authorization": "Bearer " + key} if key else {})}
    try:
        with opener(urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(), hdr), timeout=timeout) as r:
            txt = str(json.load(r)["choices"][0]["message"]["content"] or "").strip()
        return txt or None
    except Exception:
        return None


def ceo_reply(msg, live, jobs, alive, model=model_reply):
    """-> {"reply", "source": kayit|kural|model, "proposal": None | {...}}. Hiçbir yan etkisi yoktur."""
    kind = classify(msg)
    if kind == "status":
        return {"reply": facts(live, jobs, alive), "source": "kayit", "proposal": None}
    if kind == "stop":
        if not any(j["state"] == "running" for j in jobs):
            return {"reply": "Şu anda çalışan bir iş yok; durdurulacak bir şey bulunmuyor.", "source": "kayit", "proposal": None}
        return {"reply": "Çalışan işi durdurmamı istiyorsun. Onaylarsan iptal isteği gönderirim.", "source": "kural",
                "proposal": {"action": "cancel"}}
    if kind == "task":
        wait = len([j for j in jobs if j["state"] in ("pending", "running")])
        text = ("Görevi anladım. Onaylarsan kuyruğa alırım; ekip sırayla yürütür: yönetmen, senaryo odası, denetçi, ses, "
                "animatik, karakter tasarımı, render, video kalite.")
        if wait:
            text += " Önünde %d iş var." % wait
        return {"reply": text, "source": "kural", "proposal": {"action": "enqueue", "command": msg.strip()}}
    ans = model(msg, facts(live, jobs, alive))
    if ans:
        return {"reply": ans, "source": "model", "proposal": None}
    return {"reply": "Sohbet için yazı modeline şu an ulaşamıyorum. Durum sorabilir ('durum ne?'), görev verebilir "
                     "('... hakkında yeni bölüm hazırla') ya da 'işi durdur' diyebilirsin.", "source": "kural", "proposal": None}
