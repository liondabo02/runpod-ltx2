import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
f = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www\index.html")
text = f.read_text(encoding="utf-8", errors="replace")

if "sokak-oyunlari.html" in text:
    print("zaten ekli")
    raise SystemExit(0)

marker = '<div class="cards">'
card = (
    '<div class="cards"> '
    '<a class="card" href="sokak-oyunlari.html" '
    'style="text-decoration:none;color:inherit">'
    '<span>🏫</span><strong>Sokak Oyunları</strong>'
    '<small>Seksek · Beş Taş · Yakar Top · Yedi Kule</small></a> '
)
if marker not in text:
    print("cards kapsayicisi bulunamadi")
    raise SystemExit(1)

text = text.replace(marker, card, 1)
f.write_text(text, encoding="utf-8")
print("eklendi · yeni boyut:", len(text))
