import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import edge_tts

OUT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\voices\ahos")
VOICE = "tr-TR-EmelNeural"

HINTS = {
    "t-09-ipucu-seksek": ["İpucu: sıradaki sayıya bak.", "Kareler soldan sağa artıyor."],
    "t-10-ipucu-bestas": ["İpucu: taşları tek tek topla.", "Acele etme, sırayla dokun."],
    "t-11-ipucu-yakartop": ["İpucu: top sana yaklaşınca yer değiştir.", "Kenarlara kaçmak daha güvenli."],
    "t-12-ipucu-yerden": ["İpucu: yüksek yerlere bas.", "Ağaç ve merdiven seni korur."],
    "t-13-ipucu-yedikule": ["İpucu: kuleleri soldan sağa devir.", "Hepsini bitirince puan kazanırsın."],
}


async def build(name: str, sentences: list[str]) -> None:
    frames = []
    for sentence in sentences:
        audio = io.BytesIO()
        communicate = edge_tts.Communicate(sentence, VOICE, rate="-4%")
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                audio.write(chunk["data"])
        if audio.getvalue():
            frames.append(audio.getvalue())
    if not frames:
        print(f"  {name} HATA")
        return
    target = OUT / f"{name}.mp3"
    target.write_bytes(b"".join(frames))
    print(f"  {name:22} {target.stat().st_size:>7} bayt")


async def main() -> None:
    for name, sentences in HINTS.items():
        await build(name, sentences)
    files = sorted(OUT.glob("*.mp3"))
    print(f"\ntoplam {len(files)} dosya")


asyncio.run(main())
