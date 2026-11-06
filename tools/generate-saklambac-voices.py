import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import edge_tts

WWW = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www")
html = (WWW / "sokak-oyunlari.html").read_text(encoding="utf-8", errors="replace")
print("Saklambac sınıfı:", "function Saklambac" in html, "| CLASSES:", "var CLASSES" in html,
      "| oyun kaydı:", "saklambac" in html)

OUT = WWW / "voices" / "ahos"
OUT.mkdir(parents=True, exist_ok=True)

CLIPS = {
    "t-14-saklambac": [
        "Saklambaç oynuyoruz.",
        "Ebe saymaya başlamadan yeşil bir yere dokunup saklan.",
        "Saklandıktan sonra kıpırdama, ebe seni görmesin.",
    ],
    "t-15-ipucu-saklambac": [
        "İpucu: ebenin baktığı yönün tersine kaç.",
        "Yeşil kutular seni gizler.",
    ],
}


async def build(name: str, sentences: list[str]) -> None:
    frames = []
    for sentence in sentences:
        data = b""
        for attempt in range(3):
            buffer = io.BytesIO()
            try:
                communicate = edge_tts.Communicate(sentence, "tr-TR-EmelNeural", rate="-4%")
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
    target = OUT / f"{name}.mp3"
    if frames:
        target.write_bytes(b"".join(frames))
        print(f"  {name:22} {target.stat().st_size:>7} bayt")
    else:
        print(f"  {name:22} HATA")


async def main() -> None:
    for name, sentences in CLIPS.items():
        await build(name, sentences)
    print("toplam ses dosyası:", len(list(OUT.glob('*.mp3'))))


asyncio.run(main())
