"""Hukuk departmanı: isteği denetler, uyarır ve **yasal alternatif** sunar.

Kural: isteği engellemek değil; riski söylemek ve aynı amaca **hukuka uygun**
yoldan ulaşan bir çözüm önermek.

Risk alanları: telif/marka, kişisel veri (KVKK/GDPR), çocuk/güvenlik,
finansal/mali tavsiye, sağlık iddiası, kumar/bahis, izinsiz veri toplama.
"""

from __future__ import annotations

from dataclasses import dataclass, field

RULES = (
    {
        "key": "copyright",
        "risk": "orta",
        "words": ("telif", "kopyala", "birebir aynı", "klon", "çalıntı", "korsan", "repack"),
        "warning": "Başka bir eserin birebir kopyası telif ihlali olabilir.",
        "alternative": "Aynı oynanış zevkini veren özgün bir tasarım kurabiliriz: mekanikleri analiz edip kendi görsel/içerik setimizle yeniden yaparız.",
    },
    {
        "key": "trademark",
        "risk": "orta",
        "words": ("marka", "logo taklit", "isim hakkı", "nike", "disney", "pokemon", "peppa"),
        "warning": "Tescilli marka/isim kullanımı hukuki risk taşır.",
        "alternative": "Benzer türde ama özgün isim ve maskotla ilerleyelim; ilham aldığımız türü belirtip kendi markamızı oluştururuz.",
    },
    {
        "key": "personal_data",
        "risk": "yüksek",
        "words": ("kvkk", "gdpr", "kişisel veri", "telefon numarası", "e-posta topla", "adres", "tc kimlik"),
        "warning": "Kişisel veri toplama KVKK/GDPR kapsamında açık rıza ve aydınlatma gerektirir.",
        "alternative": "Veriyi cihazda tutan (sunucuya göndermeyen) bir tasarımla ilerleyelim; toplanacaksa onay ekranı + aydınlatma metni hazırlarız.",
    },
    {
        "key": "children",
        "risk": "yüksek",
        "words": ("çocuk verisi", "çocuklara reklam", "çocuktan veri", "coppa", "kid verisi", "çocukların verisi"),
        "warning": "Çocuklara yönelik içerikte reklam, veri toplama ve yaş uygunluğu konuları sıkı denetlenir (COPPA/Google Families).",
        "alternative": "Reklamsız, çevrimdışı, veri toplamayan sürümle ilerleyelim; seslendirme ve ödül mekaniklerini pedagojik denetimden geçiririz.",
    },
    {
        "key": "financial",
        "risk": "orta",
        "words": ("yatırım tavsiyesi", "hisse", "kripto", "getiri garantisi", "kazanç garantisi", "borsa"),
        "warning": "Yatırım/kazanç tavsiyesi düzenlemeye tabidir; garanti getiri ifadesi yasaktır.",
        "alternative": "Eğitim içeriği olarak hazırlayalım: risk açıklamalı, garanti iddiası olmayan bilgilendirme + kaynakça.",
    },
    {
        "key": "health",
        "risk": "yüksek",
        "words": ("teşhis", "tedavi", "ilaç", "hastalık tedavisi", "tıbbi tavsiye"),
        "warning": "Tıbbi teşhis/tedavi iddiası hekimlik meslek kanunu açısından risklidir.",
        "alternative": "Genel sağlık bilgilendirmesi + 'doktora danışın' uyarısıyla sınırlayalım; içerik kaynaklı olsun.",
    },
    {
        "key": "gambling",
        "risk": "yüksek",
        "words": ("kumar", "bahis", "şans oyunu", "rulet", "casino"),
        "warning": "Kumar/bahis içeriği Türkiye'de yasak kapsamındadır.",
        "alternative": "Şanssız, beceri temelli bir mini oyun (örn. hedef vurma, ritim) kuralım; para/ödül bağlantısı olmasın.",
    },
    {
        "key": "scraping",
        "risk": "orta",
        "words": ("scrape", "kazı", "bot ile çek", "otomatik indir", "izinsiz topla"),
        "warning": "Site şartlarına aykırı otomatik veri çekme, erişim engeli ve hukuki risk doğurur.",
        "alternative": "Resmî API/izinli kaynak kullanalım; veri yoksa açık lisanslı veri setiyle ilerleriz.",
    },
)


@dataclass
class LegalReview:
    risk: str = "yok"
    warnings: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_owner_confirmation(self) -> bool:
        return self.risk in {"orta", "yüksek"}

    def text(self) -> str:
        if not self.warnings:
            return ""
        lines = [f"⚖️ Hukuk uyarısı (risk: {self.risk})"]
        lines += [f"- {item}" for item in self.warnings]
        lines.append("Yasal alternatif:")
        lines += [f"- {item}" for item in self.alternatives]
        return "\n".join(lines)


_ORDER = {"yok": 0, "düşük": 1, "orta": 2, "yüksek": 3}


def review(text: str) -> LegalReview:
    """İsteği hukuk kurallarından geçirir."""

    low = text.casefold()
    warnings: list[str] = []
    alternatives: list[str] = []
    flags: list[str] = []
    risk = "yok"

    for rule in RULES:
        if not any(word in low for word in rule["words"]):
            continue
        flags.append(rule["key"])
        warnings.append(rule["warning"])
        alternatives.append(rule["alternative"])
        if _ORDER[rule["risk"]] > _ORDER[risk]:
            risk = rule["risk"]

    return LegalReview(
        risk=risk,
        warnings=tuple(warnings),
        alternatives=tuple(alternatives),
        flags=tuple(flags),
    )
