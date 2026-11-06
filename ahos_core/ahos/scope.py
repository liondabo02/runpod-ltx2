"""Görev kapsamı sınıflandırıcı — hangi iş deterministik, hangisi değil.

Amaç: deterministik uygulanabilen görevleri modele göndermemek; modele
bırakılamayacak kadar karmaşık görevleri ise belge/analiz kapsamına çevirmek.
"""

from __future__ import annotations

import re

_DETERMINISTIC = (
    r"dosyas[ıi]n[ıi]n sonuna",
    r"sonuna .*(ekle|yorum|satır)",
    r"başına .*(ekle|yorum)",
    r"(metni|satırı|değeri) .*(değiştir|düzelt|güncelle)",
    r"(ekle|yorum ekle)",
)

_COMPLEX = (
    r"(modül|servis|uygulama|oyun|motor|api)\w*.{0,24}(yaz|oluştur|geliştir|tasarla)",
    r"(mimari|tasarım|refactor|yeniden yaz|baştan yaz)",
    r"(test yaz|testleri yaz|suite)",
    r"(entegre et|bağla|kur)",
)


def classify(objective: str) -> str:
    """'deterministic' veya 'complex' döndürür."""

    text = (objective or "").strip().lower()
    if not text:
        return "complex"
    for pattern in _COMPLEX:
        if re.search(pattern, text):
            return "complex"
    for pattern in _DETERMINISTIC:
        if re.search(pattern, text):
            return "deterministic"
    return "complex" if len(text.split()) > 12 else "deterministic"


def as_document_objective(objective: str) -> str:
    """Karmaşık kod görevini belge/analiz görevine çevirir."""

    text = (objective or "").strip()
    return (
        f"Tasarım dokümanı üret: {text[:200]}. "
        "İçerik: amaç, kapsam, dosya yapısı, adım listesi, riskler."
    )


def should_document(objective: str) -> bool:
    return classify(objective) == "complex"
