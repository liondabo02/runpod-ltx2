"""Doğal seslendirme üretici — cümle cümle sentez + yumuşak birleştirme.

Tek uzun cümle yerine, metni kısa cümlelere bölüp her cümleyi ayrı sentezleriz;
Edge nöral sesleri cümle sonlarında doğal duraklama yapar. Parçalar aynı codec ile
üretildiği için MP3 baytları doğrudan birleştirilebilir (ek araç gerekmez).
"""

from __future__ import annotations

import asyncio
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import edge_tts

OUT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\voices\ahos")
OUT.mkdir(parents=True, exist_ok=True)

VOICE = "tr-TR-EmelNeural"

# Öğretmen: sıcak, sakin, öğretmen tonu (çok yavaş değil — robotik olmasın)
TEACHER = {
    "t-01-merhaba": [
        "Merhaba canım, hoş geldin.",
        "Ben senin öğretmeninim.",
        "Bugün birlikte sokak oyunları oynayacağız.",
        "Hazırsan başlayalım mı?",
    ],
    "t-02-seksek": [
        "Seksek şöyle oynanır.",
        "Önce taşı kareye atarsın.",
        "Sonra tek ayağınla karelere basarsın.",
        "Hadi, birlikte deneyelim.",
    ],
    "t-03-bestas": [
        "Beş taş oyununda taşları havaya atarsın.",
        "Yere düşürmeden toplarsın.",
        "Önce tek taşla başlayalım.",
        "Sonra biraz hızlanacağız.",
    ],
    "t-04-yakartop": [
        "Yakar top oyununda, ortadaki arkadaşını vurmaya çalışırsın.",
        "Ama dikkat, top sana da gelebilir.",
        "Hazır ol, başlıyoruz.",
    ],
    "t-05-yerdenyuksek": [
        "Yerden yüksek oyunu.",
        "Yerden yüksek bir yere basarsan güvendesin.",
        "Yakalanmamak için hızlı olmalısın.",
    ],
    "t-06-yedikule": [
        "Yedi kule oyunu.",
        "Karşı takımın kulelerini devirmeye çalışırsın.",
        "Birlikte çalışmak çok önemli.",
    ],
    "t-07-yanlis": [
        "Sorun değil canım.",
        "Hata yapmak, öğrenmenin bir parçası.",
        "Gel, birlikte bir daha deneyelim.",
    ],
    "t-08-tebrik": [
        "Çok güzel yaptın.",
        "Seninle gurur duyuyorum.",
        "Devam edelim mi?",
    ],
}

# Mipiluna: tatlı ama doğal çocuk tonu (aşırı incelik yok)
GIRL = {
    "k-01-merhaba": ["Merhaba! Ben Mipiluna.", "Hadi birlikte oynayalım, çok eğlenceli olacak!"],
    "k-02-dogru": ["Yuppi! Doğru yaptın.", "Harikasın!"],
    "k-03-yanlis": ["Hmm, olmadı galiba.", "Birlikte tekrar deneyelim mi?"],
    "k-04-yardim": ["İstersen sana ipucu verebilirim.", "Hazır mısın?"],
    "k-05-basladik": ["Başladık!", "Ben de seninleyim, hadi!"],
}


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


async def synth(text: str, *, rate: str, pitch: str | None) -> bytes:
    communicate = edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch) if pitch else edge_tts.Communicate(text, VOICE, rate=rate)
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            buffer.write(chunk["data"])
    return buffer.getvalue()


async def build(name: str, sentences: list[str], *, rate: str, pitch: str | None) -> None:
    frames = []
    for sentence in sentences:
        try:
            data = await synth(sentence, rate=rate, pitch=pitch)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name:16} cümle hatası: {exc}")
            continue
        if data:
            frames.append(data)
    if not frames:
        print(f"  {name:16} HATA (ses yok)")
        return
    target = OUT / f"{name}.mp3"
    target.write_bytes(b"".join(frames))
    print(f"  {name:16} {target.stat().st_size:>7} bayt · {len(frames)} cümle")


async def main() -> None:
    print("ÖĞRETMEN (sıcak, sakin, cümle arası doğal duraklama):")
    for name, sentences in TEACHER.items():
        await build(name, sentences, rate="-4%", pitch=None)

    print("MİPİLUNA (tatlı çocuk tonu, doğal):")
    for name, sentences in GIRL.items():
        await build(name, sentences, rate="+2%", pitch="+22Hz")

    files = sorted(OUT.glob("*.mp3"))
    print(f"\ntoplam {len(files)} dosya · {round(sum(p.stat().st_size for p in files)/1024)} KB")


asyncio.run(main())
