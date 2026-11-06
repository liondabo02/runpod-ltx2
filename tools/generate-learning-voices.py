"""Mipiluna · Öğrenme paketi sesleri: sayılar ve harfler.

Rakip analizi (Khan Academy Kids, Lingokids) müfredat içeriğini öne çıkarıyor.
Burada okul öncesi çekirdek set üretilir: 1-10 sayıları ve 8 temel harf.
"""

from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import edge_tts

OUT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\voices\ogrenme")
OUT.mkdir(parents=True, exist_ok=True)
VOICE = "tr-TR-EmelNeural"

NUMBERS = {
    1: "bir", 2: "iki", 3: "üç", 4: "dört", 5: "beş",
    6: "altı", 7: "yedi", 8: "sekiz", 9: "dokuz", 10: "on",
}

LETTERS = {
    "a": "a", "e": "e", "i": "i", "o": "o", "u": "u",
    "b": "be", "k": "ke", "s": "se",
}


async def say(name: str, text: str, rate: str = "-6%") -> None:
    data = b""
    for attempt in range(3):
        buffer = io.BytesIO()
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate=rate)
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    buffer.write(chunk["data"])
            data = buffer.getvalue()
        except Exception:
            data = b""
        if data:
            break
        await asyncio.sleep(0.5 * (attempt + 1))
    target = OUT / f"{name}.mp3"
    if data:
        target.write_bytes(data)
        print(f"  {name:14} {target.stat().st_size:>7} bayt")
    else:
        print(f"  {name:14} HATA")


async def main() -> None:
    for value, word in NUMBERS.items():
        await say(f"sayi-{value:02d}", word)
    for letter, sound in LETTERS.items():
        await say(f"harf-{letter}", sound)
    await say("sayi-01-yonerge", "Kaç tane var? Doğru sayıya dokun.", rate="-4%")
    await say("harf-01-yonerge", "Hangi harfle başlıyor? Doğru harfe dokun.", rate="-4%")
    files = sorted(OUT.glob("*.mp3"))
    print(f"\ntoplam {len(files)} dosya · {round(sum(p.stat().st_size for p in files)/1024)} KB")


asyncio.run(main())
