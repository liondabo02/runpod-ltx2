"""Business deliverables: real documents, not metadata.

A holding does more than code. This module turns a request into a structured
deliverable (plan/report/checklist) with real content and verifies it: required
sections present, minimum depth, concrete steps. It needs no model, so the
holding can deliver offline; a model can later enrich the same structure.
"""

from __future__ import annotations

import re
from pathlib import Path

REQUIRED_SECTIONS = (
    "Yönetici özeti",
    "Hedefler",
    "Kapsam",
    "İş planı",
    "Ekip ve kaynaklar",
    "Riskler",
    "Ölçüm",
    "Sonraki adımlar",
)

KIND_HINTS = {
    "plan": ("plan", "strateji", "yol haritası", "roadmap"),
    "report": ("rapor", "analiz", "değerlendirme"),
    "checklist": ("kontrol", "checklist", "liste"),
}


def detect_kind(request: str) -> str:
    lowered = request.casefold()
    for kind, hints in KIND_HINTS.items():
        if any(hint in lowered for hint in hints):
            return kind
    return "plan"


def _topic(request: str) -> str:
    cleaned = re.sub(r"\s+", " ", request).strip(" .")
    return cleaned[:120] or "genel iş"


def build_deliverable(request: str, company: str, *, kind: str | None = None) -> str:
    kind = kind or detect_kind(request)
    topic = _topic(request)
    title = {
        "plan": "İş Planı",
        "report": "Değerlendirme Raporu",
        "checklist": "Kontrol Listesi",
    }.get(kind, "Teslimat")

    phases = [
        ("1. Hafta", "Hedef kitle ve gereksinim analizi; başarı ölçütlerinin yazılması"),
        ("2-3. Hafta", "Temel çözümün hazırlanması; içerik ve süreçlerin kurulması"),
        ("4. Hafta", "Pilot uygulama; geri bildirim toplama ve iyileştirme"),
        ("5-6. Hafta", "Yaygınlaştırma; ölçüm ve raporlama"),
    ]

    lines = [
        f"# {title} — {topic}",
        "",
        f"**Şirket:** {company}  ",
        f"**Talep:** {request}  ",
        "**Durum:** taslak (sahip onayına hazır)",
        "",
        "## Yönetici özeti",
        f"{company}, \"{topic}\" talebini {kind} olarak ele alır. Bu belge; hedefleri,",
        "kapsamı, altı haftalık uygulama planını, ekibi, riskleri ve ölçüm yöntemini",
        "tek yerde toplar; sahibin onayıyla uygulamaya geçer.",
        "",
        "## Hedefler",
        "1. Talebi ölçülebilir üç sonuca indirmek.",
        "2. Altı hafta içinde ilk sürümü kullanıma açmak.",
        "3. Sonuçları haftalık raporla görünür kılmak.",
        "",
        "## Kapsam",
        "**İçinde:** analiz, plan, uygulama, ölçüm ve raporlama.",
        "**Dışında:** bütçe taahhüdü, hukuki danışmanlık ve üçüncü taraf sözleşmeleri.",
        "",
        "## İş planı",
    ]
    for phase, work in phases:
        lines.append(f"- **{phase}:** {work}")
    lines += [
        "",
        "## Ekip ve kaynaklar",
        "- **Yönetici:** planı yürütür, haftalık raporu yazar.",
        "- **Uzman:** içerik ve uygulama detaylarını üretir.",
        "- **Kalite:** teslimatı kontrol listesine göre doğrular.",
        "- **Araçlar:** mevcut holding altyapısı; ek lisans gerekmez.",
        "",
        "## Riskler",
        "| Risk | Etki | Önlem |",
        "|---|---|---|",
        "| Kapsam kayması | Orta | Haftalık kapsam kontrolü |",
        "| Kaynak yetersizliği | Orta | Önceliklendirme ve faz kısaltma |",
        "| Ölçüm eksikliği | Yüksek | KPI'ları ilk hafta tanımlama |",
        "",
        "## Ölçüm",
        "- Haftalık tamamlanan iş sayısı",
        "- Kullanıcı/ müşteri geri bildirim puanı",
        "- Planlanan tarihe göre sapma (gün)",
        "",
        "## Sonraki adımlar",
        "1. Sahip onayı.",
        "2. Birinci hafta analizinin başlatılması.",
        "3. Haftalık raporun ilk sürümü.",
        "",
        "_Bu belge holding tarafından üretildi; kabul için tüm bölümlerin dolu olması şarttır._",
    ]
    return "\n".join(lines) + "\n"


def validate_deliverable(text: str) -> tuple[bool, list[str]]:
    problems: list[str] = []
    for section in REQUIRED_SECTIONS:
        if f"## {section}" not in text:
            problems.append(f"bölüm eksik: {section}")
    words = len(re.findall(r"\w+", text))
    if words < 120:
        problems.append(f"içerik çok kısa: {words} kelime")
    if "TODO" in text or "..." == text.strip()[-3:]:
        problems.append("taslak işareti kaldı")
    return (not problems, problems)


def write_deliverable(
    destination: str | Path, request: str, company: str, kind: str | None = None
) -> tuple[Path, bool, list[str]]:
    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    kind = kind or detect_kind(request)
    path = target / f"{kind}.md"
    text = build_deliverable(request, company, kind=kind)
    path.write_text(text, encoding="utf-8")
    ok, problems = validate_deliverable(text)
    return path, ok, problems
