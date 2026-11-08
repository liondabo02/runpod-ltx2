import io
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core")

os.environ["AHOS_PROVIDER_CHAIN"] = "1"

from ahos import ceo

R = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime")
R_alt = R

for message in ("durum ne", "oyun departmanında geliştirilmesi gereken çok şey var onları yaptır"):
    result = ceo.answer(R_alt, message)
    print("SORU:", message)
    print("  mod:", result.get("mode"), "| yönlendirme:", result.get("routed"), "| görev:", result.get("tasks"))
    print("  cevap:", str(result.get("reply"))[:260].replace("\n", " "))
    print()
