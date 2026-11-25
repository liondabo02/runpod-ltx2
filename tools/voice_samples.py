"""Ses motoru A/B örnekleri + otomatik teknik denetim (ASR YOK: yanlış dil/telaffuzu yakalayamaz; insan dinlemesi gerekir).
Kullanım: python tools/voice_samples.py [engine=edge|piper] [çıktı klasörü]
Üretir: <çıktı>/<engine>/*.wav + rapor.json (süre, tepe, clipping, sessizlik, doğrulama sorunları)."""
import asyncio, json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import audio_qa

LINES = [  # (ad, metin, karakter-tipi, not)
    ("normal", "Bugün parka gidip çöpleri toplayacağız.", "adult", "düz anlatım"),
    ("soru", "Bu şişeyi nereye atmamız gerekiyor acaba?", "child", "soru tonu"),
    ("saskinlik", "Aaa! Bu şişe nereden çıktı böyle?", "child", "şaşırma"),
    ("uzgun", "Keşke daha önce fark etseydik, çok üzüldüm.", "child", "üzüntü"),
    ("sevinc", "Harikasın Aden! Hepsini tek başına topladın!", "adult", "sevinç"),
    ("isimler", "Aden ile Harun, Dortmund'dan gelen Kurmancî Kaan'a merhaba dedi.", "adult", "özel isimler"),
    ("rakam", "Tam yirmi üç şişe topladık, hepsi geri dönüşüm kutusunda.", "adult", "sayı okuma"),
]
EDGE = {"adult": ("tr-TR-AhmetNeural", "+0%", "+0Hz"), "child": ("tr-TR-EmelNeural", "+8%", "+25Hz")}

def tts_edge(text, kind, out_wav):
    import edge_tts
    v, r, p = EDGE[kind]; mp3 = out_wav[:-4] + ".mp3"
    asyncio.run(edge_tts.Communicate(text, v, rate=r, pitch=p).save(mp3))
    subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ar", "16000", "-ac", "1", out_wav], check=True); os.remove(mp3)

def run(engine="edge", out="qa/ses_ornekleri"):
    d = os.path.join(out, engine); os.makedirs(d, exist_ok=True); rep = []
    fn = {"edge": tts_edge}.get(engine)
    if engine == "piper":
        import voice_worker as vw
        fn = lambda text, kind, wav: vw.tts_piper(text, "", "+0%", "+0Hz", wav)
    for name, text, kind, note in LINES:
        wav = os.path.join(d, name + ".wav"); t0 = time.time(); row = {"ad": name, "metin": text, "not": note, "motor": engine}
        try:
            fn(text, kind, wav); x, sr = audio_qa.read_wav(wav); probs, st = audio_qa.validate_speech(x, sr, text)
            row.update({"süre_s": round(st["dur"], 2), "tepe_dB": round(st["peak_db"], 1), "clip": round(st["clip_frac"], 5), "sorunlar": probs, "üretim_s": round(time.time() - t0, 1)})
        except Exception as e:
            row.update({"hata": f"{type(e).__name__}: {str(e)[:150]}"})
        rep.append(row)
    json.dump(rep, open(os.path.join(d, "rapor.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for r in rep if "hata" not in r and not r["sorunlar"]); print(f"{engine}: {ok}/{len(rep)} örnek teknik denetimden geçti (dinleme DEĞİL)")
    return rep

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "edge", sys.argv[2] if len(sys.argv) > 2 else "qa/ses_ornekleri")
