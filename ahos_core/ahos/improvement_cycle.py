"""Sürekli gelişim döngüsü: departmanlar asla boş durmasın.

Her turda, bekleyen işi olmayan departmanlara **küçük ve doğrulanabilir** bir
gelişim görevi verilir. Görevler döner (rotasyon), böylece aynı iş tekrar tekrar
kuyruğa girmez ve her departman zamanla farklı konularda olgunlaşır.

Tasarım kuralları:
* Aynı departmana bekleyen iş varken yeni iş verilmez (kuyruk şişmez).
* Tur başına en fazla ``limit`` görev (maliyet ve RAM koruması).
* Görev kimlikleri zaman damgalıdır; geçmiş kayıtlar ezilmez.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

OBJECTIVES: dict[str, tuple[str, ...]] = {
    "oyun": (
        "Oyun için 3 yeni bölüm fikri yaz: ad, öğrenme hedefi, süre (dakika)",
        "Oyunun ilk 60 saniyesini çocuk gözüyle incele: 3 iyileştirme öner",
    ),
    "creative": (
        "Mipiluna için 20 saniyelik jenerik planı yaz: sahne, ses, süre",
        "Stüdyo için 3 karakter taslağı çıkar: ad, ses tonu, kişilik",
    ),
    "software": (
        "Oyun kodunda en yavaş 3 fonksiyonu tespit et ve hızlandırma önerisi yaz",
        "Hata günlüğünden en sık 3 hatayı çıkar ve düzeltme planı yaz",
    ),
    "data": (
        "Kuyruk durum raporu üret: status sayıları ve departman dağılımı (JSON)",
        "Son 7 günün teslim oranı raporunu üret (markdown tablo)",
    ),
    "finance": (
        "Model harcama özetini CSV olarak yaz: model, çağrı, USD",
        "Aylık bütçe önerisi yaz: ücretsiz araçlarla maliyet 0 varsayımı",
    ),
    "guvenlik": (
        "Son 24 saatte ücretli model çağrısı var mı denetle ve raporla",
        "Proje kilitlerinin sahiplerini listele; sahipsiz kilit var mı raporla",
    ),
    "quality": (
        "Son 10 tamamlanan görevin kabul kapısı sonuçlarını listele",
        "Kabul kapısına 3 yeni kontrol önerisi yaz (neden gerekli)",
    ),
    "research": (
        "Mipiluna oyunu için 3 geliştirme önerisi yaz (kısa, gerekçeli)",
        "Okul öncesi çocuk oyunlarında 3 kanıta dayalı tasarım ilkesi yaz",
    ),
    "marketing": (
        "Mipiluna için veliye yönelik 3 cümlelik tanıtım metni yaz",
        "Okul öncesi öğretmenlerine yönelik 1 e-posta taslağı yaz",
    ),
    "sales": (
        "Mipiluna için 3 paket önerisi yaz: içerik, fiyat, hedef kitle",
        "Okul öncesi kurumlara satış için 5 soruluk ihtiyaç listesi çıkar",
    ),
    "support": (
        "Velilerden gelebilecek 5 soru ve kısa yanıtlarını yaz",
        "Oyun içi yardım metni taslağı yaz (çocuk diliyle, 5 madde)",
    ),
    "operations": (
        "Günlük işletim kontrol listesi yaz: 8 madde, sorumlu, sıklık",
        "Kuyruk gecikmeleri için 3 önlem yaz (ölçülebilir)",
    ),
    "infrastructure": (
        "Disk/RAM/CPU için 3 eşik ve uyarı planı yaz",
        "Yedekleme planı yaz: sıklık, saklama, geri yükleme testi",
    ),
    "arge": (
        "Son 10 görevin hata dağılımını çıkar; en sık 3 neden ve çözüm önerisi yaz",
        "İki zayıf departman seç; her biri için 1 haftalık ölçülebilir iyileştirme planı yaz",
    ),
    "holding": (
        "Holdingin haftalık özetini yaz: departman, teslim, engel, öneri",
        "3 departman için 1 haftalık hedef belirle (ölçülebilir)",
    ),
}


@dataclass(frozen=True)
class CycleResult:
    created: tuple[str, ...]
    skipped: tuple[str, ...]


def _has_pending(queue, department: str) -> bool:
    try:
        from .autonomous_company import QueueStatus

        for mission in queue.list(statuses=(QueueStatus.PENDING,)):
            if getattr(mission, "primary_department", "") == department:
                return True
    except Exception:  # noqa: BLE001 - kuyruk okunamazsa temkinli davran
        return True
    return False


def run_cycle(queue, departments: Iterable[str], *, limit: int = 4, stamp: str | None = None) -> CycleResult:
    """Bekleyen işi olmayan departmanlara rotasyonlu gelişim görevi ekler."""

    token = stamp or time.strftime("%Y%m%d%H%M%S")
    created: list[str] = []
    skipped: list[str] = []

    for department in departments:
        if len(created) >= limit:
            break
        options = OBJECTIVES.get(department)
        if not options:
            skipped.append(department)
            continue
        if _has_pending(queue, department):
            skipped.append(department)
            continue
        objective = options[len(token) % len(options)]
        mission_id = f"CMD-{department}-gelisim-{token}"
        try:
            queue.enqueue(
                mission_id=mission_id,
                objective=objective,
                primary_department=department,
                max_attempts=1,
                replace_existing=False,
            )
            created.append(mission_id)
        except Exception:  # noqa: BLE001 - aynı kimlik varsa atla
            skipped.append(department)

    return CycleResult(created=tuple(created), skipped=tuple(skipped))
