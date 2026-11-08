"""İstek analizi: sahibin mesajını en ince ayrıntısına kadar çöz.

Amaç: görev dağıtımı **tahminle** değil, isteğin yapısına göre yapılsın.

Çıktı:
- `intent`      : ne isteniyor (özellik, düzeltme, içerik, araştırma, analiz…)
- `deliverables`: beklenen somut çıktılar (dosya, belge, video, rapor…)
- `example`     : "şu gibi / örnek / benzer" varsa örnek kaynağı (URL veya dosya)
- `targets`     : istekte geçen dosya/ürün adları
- `departments` : isteğe en uygun departmanlar (puanlı)
- `constraints`: süre, bütçe, platform, dil gibi kısıtlar

Deterministik; model çağrısı yok.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

URL_PATTERN = re.compile(r"https?://[^\s)\]\"']+")
FILE_PATTERN = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:js|css|html|py|json|md|png|jpg|mp4|apk|pdf)\b"
)

INTENT_WORDS = {
    "feature": ("ekle", "yap", "geliştir", "koy", "tasarım", "özellik", "bölüm"),
    "fix": ("düzelt", "hata", "bozuk", "çalışmıyor", "onar", "bug"),
    "content": ("yaz", "metin", "senaryo", "makale", "rapor", "içerik"),
    "research": ("araştır", "incele", "analiz", "benchmark", "karşılaştır"),
    "media": ("video", "ses", "jenerik", "dublaj", "animasyon", "müzik"),
    "ops": ("kur", "deploy", "sunucu", "yedek", "güncelle", "yayınla"),
}

DELIVERABLE_WORDS = {
    "dosya/kod": ("dosya", "kod", "sayfa", "html", "css", "js", "apk"),
    "belge": ("rapor", "plan", "metin", "makale", "doküman", "sözleşme"),
    "video": ("video", "jenerik", "klip", "film"),
    "ses": ("ses", "dublaj", "voice", "mp3"),
    "görsel": ("görsel", "resim", "logo", "ikon", "tasarım"),
    "veri": ("veri", "istatistik", "analiz", "grafik", "tablo"),
}

DEPARTMENTS = {
    "oyun": ("oyun", "mipiluna", "level", "sokak", "bölüm", "karakter"),
    "software": ("kod", "yazılım", "api", "hata", "bug", "sayfa", "uygulama", "apk"),
    "creative": ("video", "jenerik", "ses", "dublaj", "animasyon", "tasarım", "görsel"),
    "data": ("veri", "rapor", "analiz", "istatistik", "metrik"),
    "finance": ("bütçe", "maliyet", "fatura", "fiyat", "gelir"),
    "guvenlik": ("güvenlik", "denetim", "sızma", "şifre", "kilit"),
    "quality": ("test", "kalite", "kabul", "doğrulama"),
    "marketing": ("pazarlama", "tanıtım", "reklam", "sosyal medya", "kampanya"),
    "research": ("araştır", "incele", "benchmark", "rakip"),
    "hukuk": ("sözleşme", "telif", "lisans", "kvkk", "gdpr", "marka", "hukuk"),
    "support": ("destek", "müşteri", "talep", "şikayet"),
    "operations": ("operasyon", "süreç", "akış", "plan"),
}

CONSTRAINT_WORDS = {
    "süre": ("bugün", "yarın", "hafta", "acil", "hemen"),
    "bütçe": ("bütçe", "ücretsiz", "para", "usd", "tl", "maliyet"),
    "platform": ("android", "ios", "web", "windows", "play store"),
    "dil": ("türkçe", "ingilizce", "almanca"),
}


@dataclass
class Intent:
    intent: str
    deliverables: tuple[str, ...] = ()
    example: str = ""
    example_kind: str = ""
    targets: tuple[str, ...] = ()
    departments: tuple[tuple[str, int], ...] = ()
    constraints: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        parts = [f"niyet={self.intent}"]
        if self.deliverables:
            parts.append("çıktı=" + ", ".join(self.deliverables))
        if self.example:
            parts.append(f"örnek={self.example_kind}:{self.example[:60]}")
        if self.targets:
            parts.append("hedef=" + ", ".join(self.targets[:3]))
        if self.departments:
            parts.append("departmanlar=" + ", ".join(f"{d}({s})" for d, s in self.departments[:3]))
        if self.constraints:
            parts.append("kısıt=" + ", ".join(f"{k}:{v}" for k, v in self.constraints.items()))
        return " | ".join(parts)


def analyze(text: str, *, limit: int = 3) -> Intent:
    """İsteği ayrıştırır; departman puanlarını hesaplar."""

    low = text.casefold()
    intent = "genel"
    best = 0
    for name, words in INTENT_WORDS.items():
        score = sum(1 for word in words if word in low)
        if score > best:
            best, intent = score, name

    deliverables = tuple(
        name for name, words in DELIVERABLE_WORDS.items() if any(w in low for w in words)
    )

    url = URL_PATTERN.search(text)
    file_match = FILE_PATTERN.search(text)
    example = ""
    example_kind = ""
    if any(token in low for token in ("gibi", "örnek", "ornek", "benzer", "tarzında", "tarzinda")):
        if url:
            example, example_kind = url.group(0), "url"
        elif file_match:
            example, example_kind = file_match.group(0), "dosya"
        else:
            example, example_kind = "metinsel referans", "metin"

    targets = tuple(sorted({match.group(0) for match in FILE_PATTERN.finditer(text)}))

    scores: list[tuple[int, str]] = []
    for department, words in DEPARTMENTS.items():
        score = sum(2 if word in low else 0 for word in words)
        if example and department in {"research", "software", "creative"}:
            score += 1
        if score:
            scores.append((score, department))
    scores.sort(key=lambda pair: (-pair[0], pair[1]))

    constraints = {
        name: next((word for word in words if word in low), "")
        for name, words in CONSTRAINT_WORDS.items()
    }
    constraints = {key: value for key, value in constraints.items() if value}

    return Intent(
        intent=intent,
        deliverables=deliverables,
        example=example,
        example_kind=example_kind,
        targets=targets,
        departments=tuple((department, score) for score, department in scores[:limit]),
        constraints=constraints,
    )
