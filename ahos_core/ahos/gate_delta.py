"""Kabul kapısı "delta" yardımcıları.

Sorun: projenin kendi kapısı zaten kırıksa (ör. önbellek listesi eksik), her
düzenleme reddediliyor ve işçi hiçbir zaman teslim edemiyor. Doğru davranış:
düzenleme **yeni** bir hata eklemiyorsa teslim kabul edilir; yeni hata
ekliyorsa geri alınır.
"""

from __future__ import annotations

import re

_FAILURE_HINTS = (
    "hata", "başarısız", "basarisiz", "eksik", "error", "fail", "missing",
    "bulunamadı", "bulunamadi", "sorun", "dışı", "disi", "geçersiz", "gecersiz", "kırık",
)


def failure_lines(output: str) -> set[str]:
    """Kapı çıktısındaki hata satırlarını normalize ederek döndürür."""

    result: set[str] = set()
    for line in (output or "").splitlines():
        text = " ".join(line.split()).strip().casefold()
        if not text:
            continue
        if any(hint in text for hint in _FAILURE_HINTS):
            # Sayıları normalize et: "3 sorun" ile "4 sorun" aynı sınıf sayılsın.
            normalized = re.sub(r"\d+", "#", text)
            result.add(normalized)
    return result


def new_failures(baseline_output: str, after_output: str) -> set[str]:
    """Düzenlemeden sonra **yeni** eklenen hata satırları."""

    return failure_lines(after_output) - failure_lines(baseline_output)


def gate_acceptable(baseline_ok: bool, baseline_output: str, after_ok: bool, after_output: str) -> tuple[bool, str]:
    """Kapı sonucunu delta kuralına göre yorumlar.

    - Düzenleme sonrası kapı geçtiyse: kabul.
    - Kapı düştü ama düzenleme öncesi de düşüyordu ve yeni hata yoksa: kabul
      (mevcut kırık durum işçinin suçu değil).
    - Yeni hata varsa: reddet.
    """

    if after_ok:
        return True, ""
    if not baseline_ok:
        added = new_failures(baseline_output, after_output)
        if not added:
            return True, "mevcut kapı hataları değişmedi (delta kabul)"
        return False, "yeni kapı hatası: " + "; ".join(sorted(added)[:3])
    return False, "kapı düştü"
