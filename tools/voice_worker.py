#!/usr/bin/env python3
"""AHOS Ses + Dudak Senkronu işçisi (diziden bağımsız).

beat_sheet.json'daki her diyalog satırını edge-tts ile seslendirir, 16 kHz mono WAV'a çevirir,
Rhubarb ile viseme (ağız şekli) zamanları üretir, süre uygunluğunu denetler, SHA-256 kayıt tutar.
Ücretsiz; edge-tts Microsoft hizmet şartlarına bağlıdır -> licence_status = review_required.

Kullanım: python tools/voice_worker.py --episode-dir series/<id>/episodes/e001 --series series/<id>/series-bible.json
"""
import argparse, asyncio, hashlib, json, os, re, shutil, subprocess, sys, wave, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FEMALE = re.compile(r"kız|kadın|anne|nine|teyze|abla|girl|woman|female|dişi", re.I)
VOICE_F, VOICE_M = "tr-TR-EmelNeural", "tr-TR-AhmetNeural"


def load_languages():
    path = os.path.join(ROOT, "studio", "pipeline", "languages.json")
    try:
        return json.load(open(path, encoding="utf-8"))["languages"]
    except Exception:
        return {"tr": {"female": VOICE_F, "male": VOICE_M, "child_female": VOICE_F, "child_male": VOICE_M}}


def pick_voice(char, lang="tr"):
    hint = " ".join(str(char.get(k, "")) for k in ("name", "role", "voice_hint")) + " " + str(char.get("voice", {}).get("hint", ""))
    female = bool(FEMALE.search(hint))
    age = char.get("age") or 30
    try: age = float(age)
    except Exception: age = 30
    table = load_languages().get(lang) or load_languages().get("tr")
    key = ("child_" if age <= 8 else "") + ("female" if female else "male")
    voice = table.get(key) or table.get("female" if female else "male") or (VOICE_F if female else VOICE_M)
    if age <= 8:   pitch, rate = "+35Hz", "+5%"      # çocuk tınısı
    elif age >= 60: pitch, rate = "-8Hz", "-10%"     # yaşlı
    else:          pitch, rate = "+0Hz", "+0%"
    # karakter başına kalıcı ses kimliği: aynı cinsiyet/yaştaki iki karakter farklı duyulsun
    h = int(hashlib.sha1(str(char.get("id") or char.get("name") or "").encode("utf-8")).hexdigest()[:6], 16)
    dp, dr = (h % 25) - 12, ((h >> 5) % 13) - 6
    pitch = "%+dHz" % (int(re.sub(r"[^\d+-]", "", pitch) or 0) + dp)
    rate = "%+d%%" % (int(re.sub(r"[^\d+-]", "", rate) or 0) + dr)
    return voice, rate, pitch


def _num(v):
    return int(re.sub(r"[^\d+-]", "", v) or 0)


def expressive(text, rate, pitch, seed=0):
    """Noktalamaya göre canlı tonlama (robotik düzlüğü kırar): ! heyecan, ? yükselen ton, ... yavaş/düşük."""
    r, p = _num(rate), _num(pitch)
    t = str(text)
    if t.rstrip().endswith("!"):
        r += 8; p += 14
    elif t.rstrip().endswith("?"):
        p += 10
    if "..." in t or "…" in t:
        r -= 10; p -= 6
    if len(t) < 14:
        r += 4                              # kısa tepkiler hızlı
    jitter = ((seed * 7919) % 11) - 5       # satırdan satıra küçük, kararlı değişim
    r += jitter * 0.8; p += jitter
    r = max(-25, min(25, r)); p = max(-30, min(60, p))
    return "%+d%%" % round(r), "%+dHz" % round(p)


def parse_dialogue(text, default_char, chars=None):
    """'Pelin: Bak! Tosun: Nerede?' veya 'pelin: ... | tosun: ...' -> [(id, metin), ...]. Ad VEYA id, büyük/küçük harf farketmez.
    default_char: str veya sahnedeki karakter listesi. Etiketsiz / tanınmayan etiketli satırlar listedeki karakterlere
    sırayla dağıtılır (hep ilk karakterin konuşması önlenir); etiket yazıdan çıkarılır."""
    text = str(text or "").strip()
    if not text: return []
    pool = [c for c in (default_char if isinstance(default_char, (list, tuple)) else [default_char]) if c]
    if chars:
        pool = [c for c in pool if c in chars] or pool
    rot = {"i": 0, "last": None}

    def nxt():
        if not pool: return None
        # önceki konuşandan farklı olan sıradaki karakter
        for _ in range(len(pool)):
            c = pool[rot["i"] % len(pool)]; rot["i"] += 1
            if c != rot["last"] or len(pool) == 1:
                rot["last"] = c; return c
        return pool[0]

    lookup = {}
    for cid, c in (chars or {}).items():
        lookup[cid.casefold()] = cid
        if c.get("name"): lookup[str(c["name"]).casefold()] = cid
    out = []
    for part in re.split(r"\s*\|\s*|\n", text):
        part = part.strip()
        if not part: continue
        # satır içinde birden çok 'Ad:' olabilir -> bölerek ele al
        pieces = [part]
        if lookup:
            pat = r"(?:(?<=^)|(?<=[\s]))(" + "|".join(re.escape(k) for k in sorted(lookup, key=len, reverse=True)) + r")\s*:\s*"
            marks = list(re.finditer(pat, part, re.I))
            if marks:
                pieces = []
                if marks[0].start() > 0 and part[:marks[0].start()].strip():
                    pieces.append((None, part[:marks[0].start()].strip()))
                for k, m in enumerate(marks):
                    end = marks[k + 1].start() if k + 1 < len(marks) else len(part)
                    seg = part[m.end():end].strip()
                    if seg: pieces.append((lookup[m.group(1).casefold()], seg))
                for cid, seg in pieces:
                    out.append((cid or nxt(), seg))
                    rot["last"] = out[-1][0]
                continue
        m = re.match(r"^([A-Za-zÇĞİÖŞÜçğıöşü0-9_ ]{1,30})\s*:\s*(.+)$", part, re.S)
        if m:                                    # tanınmayan etiket ('Nine:', 'Anlatıcı:')
            cid = lookup.get(m.group(1).strip().casefold())
            out.append((cid or nxt(), m.group(2).strip()))
        else:
            out.append((nxt(), part))
        rot["last"] = out[-1][0]
    return [(c, t) for c, t in out if c]


def wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---- gerçek motorlar (testte değiştirilebilir) ----
def piper_model(voice_hint=""):
    d = os.environ.get("AHOS_PIPER_DIR") or os.path.join(ROOT, "models", "piper")
    name = os.environ.get("AHOS_PIPER_MODEL", "tr_TR-dfki-medium")
    return os.path.join(d, name + ".onnx")


def tts_piper(text, voice, rate, pitch, out_wav):
    """Açık kaynak (MIT) Piper Türkçe ses. Hız: length_scale; ton: ffmpeg ile perde kaydırma (çocuk/yaşlı)."""
    model = piper_model()
    if not os.path.exists(model):
        raise RuntimeError("Piper modeli yok: python tools/get_piper_voice.py")
    tmp = out_wav[:-4] + ".piper.wav"
    ls = 1.0 / max(0.5, 1.0 + _num(rate) / 100.0)
    subprocess.run([sys.executable, "-m", "piper", "-m", model, "-f", tmp, "--length-scale", "%.3f" % ls],
                   input=text, text=True, encoding="utf-8", check=True, capture_output=True)
    k = max(0.7, min(1.5, 1.0 + _num(pitch) / 200.0))
    ff = shutil.which("ffmpeg") or "ffmpeg"
    with wave.open(tmp, "rb") as w:
        sr = w.getframerate()
    af = "asetrate=%d,aresample=16000,atempo=%.4f" % (int(sr * k), 1.0 / k)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", tmp, "-af", af, "-ar", "16000", "-ac", "1", out_wav], check=True)
    os.remove(tmp)


def tts_real(text, voice, rate, pitch, out_wav):
    if os.environ.get("AHOS_TTS", "edge").lower() == "piper":
        return tts_piper(text, voice, rate, pitch, out_wav)
    return tts_real_edge(text, voice, rate, pitch, out_wav)


def tts_real_edge(text, voice, rate, pitch, out_wav):
    import edge_tts
    mp3 = out_wav[:-4] + ".mp3"
    asyncio.run(edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(mp3))
    ff = shutil.which("ffmpeg") or "ffmpeg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", mp3, "-ar", "16000", "-ac", "1", out_wav], check=True)
    os.remove(mp3)


def find_rhubarb():
    for c in (os.environ.get("AHOS_RHUBARB_EXE"), shutil.which("rhubarb"),
              os.path.join(HERE, "rhubarb.cmd"),
              r"C:\actions-runner\_work\tools\rhubarb\Rhubarb-Lip-Sync-1.14.0-Windows\rhubarb.exe"):
        if c and os.path.exists(c): return c
    return None


def visemes_real(wav, out_json):
    exe = find_rhubarb()
    if not exe: raise RuntimeError("Rhubarb bulunamadı")
    subprocess.run([exe, "-f", "json", "-r", "phonetic", "-o", out_json, wav], check=True, capture_output=True)  # phonetic: İngilizce dışı diller
    return json.load(open(out_json, encoding="utf-8")).get("mouthCues", [])


def run(episode_dir, bible, tts=tts_real, visemes=visemes_real, margin=0.3, lang="tr"):
    sheet = json.load(open(os.path.join(episode_dir, "beat_sheet.json"), encoding="utf-8"))
    chars = {c["id"]: c for c in bible["characters"]}
    adir = os.path.join(episode_dir, "audio"); vdir = os.path.join(episode_dir, "visemes")
    os.makedirs(adir, exist_ok=True); os.makedirs(vdir, exist_ok=True)
    items, problems = [], []
    for bi, b in enumerate(sheet["beats"]):
        speakers = [c for c in b.get("characters", [])]
        lines = parse_dialogue(b.get("dialogue"), speakers or None, chars)
        budget = float(b["t_end"]) - float(b["t_start"])
        used = 0.0
        for li, (cid, text) in enumerate(lines):
            if cid not in chars:
                problems.append(f"beat[{bi}]: bilinmeyen konuşan '{cid}'"); continue
            voice, rate, pitch = pick_voice(chars[cid], lang)
            rate, pitch = expressive(text, rate, pitch, bi * 7 + li)
            name = f"b{bi:03d}_{li}_{cid}"
            wav = os.path.join(adir, name + ".wav"); vj = os.path.join(vdir, name + ".json")
            try:
                tts(text, voice, rate, pitch, wav)
                dur = wav_duration(wav)
                cues = visemes(wav, vj)
            except Exception as e:
                problems.append(f"beat[{bi}] {cid}: {type(e).__name__}: {str(e)[:120]}"); continue
            used += dur
            items.append({"beat": bi, "char": cid, "text": text, "voice": voice, "wav": os.path.relpath(wav, episode_dir),
                          "sha256": sha(wav), "duration_s": round(dur, 2), "mouth_cues": len(cues),
                          "visemes": os.path.relpath(vj, episode_dir) if os.path.exists(vj) else None})
            if len(cues) == 0:
                problems.append(f"beat[{bi}] {cid}: viseme üretilemedi")
        if used > budget - margin and used > 0:
            problems.append(f"beat[{bi}]: konuşma {used:.1f}s, vuruş {budget:.1f}s -> yazar kısaltmalı")
    status = "PASSED" if items and not problems else "NEEDS_REVISION"
    man = {"stage": "voice+lipsync", "status": status, "cost_eur": 0, "licence_status": "review_required",
           "licence_note": "edge-tts Microsoft hizmet şartlarına bağlı; ticari kullanım sahibin kararına kadar kapalı",
           "lines": len(items), "problems": problems, "items": items,
           "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    with open(os.path.join(episode_dir, "voice_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=2)
    # ders hafızası: yazar için geri bildirim (işçileri eğitme döngüsü)
    lessons = [p for p in problems if "kısaltmalı" in p]
    if lessons:
        mem = os.path.join(ROOT, "studio", "agents", "memory"); os.makedirs(mem, exist_ok=True)
        with open(os.path.join(mem, "director.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"status": "LESSON", "from": "voice", "lesson": "diyalog vuruş süresine sığmadı; kısa yaz",
                                "count": len(lessons), "at": man["generated_at"]}, ensure_ascii=False) + "\n")
    return man


def main():
    p = argparse.ArgumentParser(); p.add_argument("--episode-dir", required=True); p.add_argument("--series", required=True)
    a = p.parse_args()
    bible = json.load(open(a.series, encoding="utf-8"))
    m = run(a.episode_dir, bible)
    print(f"Ses/dudak senkronu: {m['status']} | satır: {m['lines']} | sorun: {len(m['problems'])}")
    for x in m["problems"][:10]: print(" -", x)


if __name__ == "__main__":
    main()
