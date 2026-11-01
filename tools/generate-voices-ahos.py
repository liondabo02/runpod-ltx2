import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\voices\ahos")
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable

TEACHER = {
    "t-01-merhaba": "Merhaba canim, hos geldin! Ben senin ogretmeninim. Bugun birlikte sokak oyunlari oynayacagiz. Hazirsan baslayalim.",
    "t-02-seksek": "Seksek oyunu soyle oynanir: tek ayaginla karelere basarsin, tasi en uzaga atarsin. Hadi sirayla deneyelim.",
    "t-03-bestas": "Bes tas oyununda taslari havaya atar, yere dusurmeden toplarsin. Once tek tasla basliyoruz, sonra hizlanacagiz.",
    "t-04-yakartop": "Yakar top, ortada duran arkadasini topla vurmaya calisirsin. Ama dikkat, top sana da gelebilir!",
    "t-05-yerdenyuksek": "Yerden yuksek oyununda yerden yuksek bir yere basarsan guvendesin. Yakalanmamak icin hizli ol.",
    "t-06-yedikule": "Yedi kule oyununda karsi takimin kulelerini devirmeye calisirsin. Takimca oynanir, birlikte calismak onemli.",
    "t-07-yanlis": "Sorun degil canim, hata yapmak ogrenmenin parcasi. Birlikte bir daha deneyelim.",
    "t-08-tebrik": "Cok guzel yaptin! Seninle gurur duyuyorum. Devam edelim mi?",
}

GIRL = {
    "k-01-merhaba": "Merhaba! Ben Mipiluna! Hadi birlikte oynayalim, cok eglenceli olacak!",
    "k-02-dogru": "Yuppi! Dogru yaptin, harikasin!",
    "k-03-yanlis": "Hmm, olmadi galiba. Birlikte tekrar deneyelim mi?",
    "k-04-yardim": "Istersen sana ipucu verebilirim, hazir misin?",
    "k-05-basladik": "Basladik! Ben de seninleyim, hadi!",
}


def run(name: str, text: str, extra: list[str]) -> None:
    target = OUT / f"{name}.mp3"
    command = [
        PY, "-m", "edge_tts",
        "--voice", "tr-TR-EmelNeural",
        "--text", text,
        *extra,
        "--write-media", str(target),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0 or not target.exists():
        print(f"  {name:18} HATA {completed.stderr.strip()[:70]}")
        return
    print(f"  {name:18} {target.stat().st_size:>7} bayt")


print("OGRETMEN (dogal, sicak, yavas):")
for name, text in TEACHER.items():
    run(name, text, ["--rate=-8%"])

print("MIPILUNA (tatli kiz cocugu):")
for name, text in GIRL.items():
    run(name, text, ["--pitch=+40Hz", "--rate=+4%"])

files = sorted(OUT.glob("*.mp3"))
print(f"\ntoplam: {len(files)} dosya · {round(sum(p.stat().st_size for p in files)/1024)} KB")
