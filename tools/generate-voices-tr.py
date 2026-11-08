"""Türkçe diakritikli, doğal seslendirme üretici.

Not: Metni ASCII'ye çevirmek (canim/hos/ogretmen) nöral sesin Türkçe
fonetiklerini bozuyor ve "yabancı aksan" gibi duyuluyor. Bu yüzden metinler
tam Türkçe karakterlerle yazılır; perde kaydırma (pitch) kullanılmaz.
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import edge_tts

OUT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\voices\ahos")
OUT.mkdir(parents=True, exist_ok=True)
VOICE = "tr-TR-EmelNeural"

TEACHER = {
    "t-01-merhaba": ["Merhaba canım, hoş geldin.", "Ben senin öğretmeninim.",
                     "Bugün birlikte sokak oyunları oynayacağız.", "Hazırsan başlayalım mı?"],
    "t-02-seksek": ["Seksek şöyle oynanır.", "Önce taşı kareye atarsın.",
                    "Sonra tek ayağınla karelere basarsın.", "Hadi, birlikte deneyelim."],
    "t-03-bestas": ["Beş taş oyununda taşları havaya atarsın.", "Yere düşürmeden toplarsın.",
                    "Önce tek taşla başlayalım.", "Sonra biraz hızlanacağız."],
    "t-04-yakartop": ["Yakar top oyununda ortadaki arkadaşını vurmaya çalışırsın.",
                      "Ama dikkat, top sana da gelebilir.", "Hazır ol, başlıyoruz."],
    "t-05-yerdenyuksek": ["Yerden yüksek oyunu.", "Yerden yüksek bir yere basarsan güvendesin.",
                          "Yakalanmamak için hızlı olmalısın."],
    "t-06-yedikule": ["Yedi kule oyunu.", "Karşı takımın kulelerini devirmeye çalışırsın.",
                      "Birlikte çalışmak çok önemli."],
    "t-07-yanlis": ["Sorun değil canım.", "Hata yapmak öğrenmenin bir parçası.",
                    "Gel, birlikte bir daha deneyelim."],
    "t-08-tebrik": ["Çok güzel yaptın.", "Seninle gurur duyuyorum.", "Devam edelim mi?"],
    "t-09-ipucu-seksek": ["İpucu: sıradaki sayıya bak.", "Kareler soldan sağa artıyor."],
    "t-10-ipucu-bestas": ["İpucu: taşları tek tek topla.", "Acele etme, sırayla dokun."],
    "t-11-ipucu-yakartop": ["İpucu: top sana yaklaşınca yer değiştir.", "Kenarlara kaçmak daha güvenli."],
    "t-12-ipucu-yerden": ["İpucu: yüksek yerlere bas.", "Ağaç ve merdiven seni korur."],
    "t-13-ipucu-yedikule": ["İpucu: kuleleri soldan sağa devir.", "Hepsini bitirince puan kazanırsın."],
}

GIRL = {
    "k-01-merhaba": ["Merhaba! Ben Mipiluna.", "Hadi birlikte oynayalım, çok eğlenceli olacak!"],
    "k-02-dogru": ["Yuppi! Doğru yaptın.", "Harikasın!"],
    "k-03-yanlis": ["Hmm, olmadı galiba.", "Birlikte tekrar deneyelim mi?"],
    "k-04-yardim": ["İstersen sana ipucu verebilirim.", "Hazır mısın?"],
    "k-05-basladik": ["Başladık!", "Ben de seninleyim, hadi!"],
}


async def build(name: str, sentences: list[str], *, rate: str) -> None:
    frames = []
    for sentence in sentences:
        data = b""
        for attempt in range(3):
            buffer = io.BytesIO()
            try:
                communicate = edge_tts.Communicate(sentence, VOICE, rate=rate)
                async for chunk in communicate.stream():
                    if chunk.get("type") == "audio" and chunk.get("data"):
                        buffer.write(chunk["data"])
                data = buffer.getvalue()
            except Exception:
                data = b""
            if data:
                break
            await asyncio.sleep(0.6 * (attempt + 1))
        if data:
            frames.append(data)
    if not frames:
        print(f"  {name:20} HATA")
        return
    target = OUT / f"{name}.mp3"
    target.write_bytes(b"".join(frames))
    print(f"  {name:20} {target.stat().st_size:>7} bayt · {len(frames)} cümle")


async def main() -> None:
    print("ÖĞRETMEN (Türkçe diakritik, perde kaydırma yok):")
    for name, sentences in TEACHER.items():
        await build(name, sentences, rate="-4%")
    print("MİPİLUNA (aynı doğal ses, hafif hızlı — çocuk enerjisi):")
    for name, sentences in GIRL.items():
        await build(name, sentences, rate="+2%")
    files = sorted(OUT.glob("*.mp3"))
    print(f"\ntoplam {len(files)} dosya · {round(sum(p.stat().st_size for p in files)/1024)} KB")


asyncio.run(main())
