from __future__ import annotations

from dataclasses import dataclass, replace

from .departments import (
    CapabilitySpec,
    DepartmentBookError,
    DepartmentSpec,
    WorkerSpec,
    ascii_fold,
    slugify,
    utc_now,
)

MANAGER_ROLE = "department_manager"
_MANAGER_CAPABILITIES = frozenset(
    {"planning", "task_decomposition", "routing", "quality_oversight"}
)


@dataclass(frozen=True, slots=True)
class TeamTemplate:
    team_id: str
    name: str
    mission: str
    capabilities: tuple[str, ...]
    lead_role: str
    specialist_role: str = "operations_specialist"


@dataclass(frozen=True, slots=True)
class DomainTemplate:
    """Deterministic recipe for turning an owner phrase into an org chart.

    No model call is required: the template supplies the department shape and
    the domain keywords drive routing. This keeps department creation free of
    token accounting while remaining a valid Hook for a future LLM planner.
    """

    domain_id: str
    name: str
    mission: str
    keywords: tuple[str, ...]
    teams: tuple[TeamTemplate, ...]
    seed_department_id: str | None = None


_ANIMATION = DomainTemplate(
    domain_id="cizgi-film",
    name="Çizgi Film Stüdyosu",
    mission=(
        "Özgün çizgi film bölümleri üretmek: senaryo, karakter, animasyon, ses, "
        "yerelleştirme ve yayın hazırlığı."
    ),
    keywords=(
        "cizgi film",
        "animasyon",
        "cartoon",
        "animation",
        "anime",
        "bolum",
        "karakter tasarimi",
        "seslendirme",
    ),
    teams=(
        TeamTemplate(
            team_id="story",
            name="Senaryo Ekibi",
            mission="Bölüm fikri, senaryo ve diyalog üretimi.",
            capabilities=("story", "screenplay", "dialogue", "storyboard"),
            lead_role="researcher",
            specialist_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="art",
            name="Sanat Ekibi",
            mission="Karakter tasarımı, mekân ve görsel dil.",
            capabilities=("character_design", "concept_art", "background_art"),
            lead_role="designer",
            specialist_role="designer",
        ),
        TeamTemplate(
            team_id="animation",
            name="Animasyon Ekibi",
            mission="Rigging, animasyon ve sahne render üretimi.",
            capabilities=("animation", "rigging", "rendering", "compositing"),
            lead_role="designer",
            specialist_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="audio",
            name="Ses Ekibi",
            mission="Seslendirme, müzik ve miksaj.",
            capabilities=("voice_over", "music", "sound_design", "mixing"),
            lead_role="operations_specialist",
            specialist_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="localization",
            name="Yerelleştirme Ekibi",
            mission="Çok dilli altyazı ve dublaj hazırlığı.",
            capabilities=("translation", "subtitling", "dubbing"),
            lead_role="researcher",
            specialist_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="growth",
            name="Büyüme Ekibi",
            mission="Satış, pazarlama ve yayın ortaklıkları.",
            capabilities=("marketing", "sales", "distribution", "audience_growth"),
            lead_role="marketing_specialist",
            specialist_role="sales_specialist",
        ),
        TeamTemplate(
            team_id="quality",
            name="Kalite Ekibi",
            mission="Bölüm kontrolü, süreklilik ve yayın onayı öncesi denetim.",
            capabilities=("qa", "continuity", "verification"),
            lead_role="qa_engineer",
            specialist_role="qa_engineer",
        ),
    ),
)

_SOFTWARE = DomainTemplate(
    domain_id="yazilim",
    name="Yazılım Şirketi",
    mission=(
        "Sahibin istediği yazılım ürünlerini tasarlamak, geliştirmek, test etmek "
        "ve yayına hazır hale getirmek."
    ),
    keywords=(
        "yazilim",
        "software",
        "uygulama",
        "app",
        "web sitesi",
        "website",
        "landing page",
        "landing",
        "site",
        "sayfa",
        "web",
        "backend",
        "frontend",
        "api",
        "saas",
        "mobil",
    ),
    teams=(
        TeamTemplate(
            team_id="product",
            name="Ürün Ekibi",
            mission="Gereksinim analizi, ürün kapsamı ve yol haritası.",
            capabilities=("product_discovery", "requirements", "roadmap"),
            lead_role="researcher",
        ),
        TeamTemplate(
            team_id="engineering",
            name="Mühendislik Ekibi",
            mission="Kod yazımı, entegrasyon ve teknik borç yönetimi.",
            capabilities=("python", "backend", "frontend", "api", "automation"),
            lead_role="software_engineer",
            specialist_role="software_engineer",
        ),
        TeamTemplate(
            team_id="platform",
            name="Platform Ekibi",
            mission="CI/CD, dağıtım ve izleme.",
            capabilities=("ci", "deployment", "monitoring", "devops"),
            lead_role="devops_engineer",
            specialist_role="devops_engineer",
        ),
        TeamTemplate(
            team_id="quality",
            name="Kalite Ekibi",
            mission="Otomatik testler, regresyon ve sürüm kontrolü.",
            capabilities=("testing", "regression", "verification", "qa"),
            lead_role="qa_engineer",
            specialist_role="qa_engineer",
        ),
        TeamTemplate(
            team_id="growth",
            name="Büyüme Ekibi",
            mission="Konumlandırma, satış ve müşteri kazanımı.",
            capabilities=("marketing", "sales", "seo", "crm"),
            lead_role="marketing_specialist",
            specialist_role="sales_specialist",
        ),
        TeamTemplate(
            team_id="operations",
            name="Operasyon Ekibi",
            mission="Bütçe, planlama ve teslim koordinasyonu.",
            capabilities=("finance", "budgeting", "scheduling", "coordination"),
            lead_role="finance_specialist",
            specialist_role="operations_specialist",
        ),
    ),
)

_MARKETING = DomainTemplate(
    domain_id="pazarlama",
    name="Pazarlama Ajansı",
    mission="Marka, kampanya ve kanal büyümesi üretmek.",
    keywords=("pazarlama", "marketing", "reklam", "kampanya", "sosyal medya", "seo"),
    teams=(
        TeamTemplate(
            team_id="strategy",
            name="Strateji Ekibi",
            mission="Marka konumlandırma ve hedef kitle analizi.",
            capabilities=("positioning", "audience_research", "messaging"),
            lead_role="marketing_specialist",
        ),
        TeamTemplate(
            team_id="content",
            name="İçerik Ekibi",
            mission="Metin, görsel ve video içerik üretimi.",
            capabilities=("copywriting", "content", "design", "video"),
            lead_role="designer",
        ),
        TeamTemplate(
            team_id="performance",
            name="Performans Ekibi",
            mission="Reklam yönetimi ve dönüşüm optimizasyonu.",
            capabilities=("ads", "analytics", "conversion"),
            lead_role="data_analyst",
        ),
        TeamTemplate(
            team_id="sales",
            name="Satış Ekibi",
            mission="Teklif, müşteri ilişkileri ve kapanış.",
            capabilities=("sales", "proposal_drafting", "crm"),
            lead_role="sales_specialist",
            specialist_role="sales_specialist",
        ),
    ),
)

_ECOMMERCE = DomainTemplate(
    domain_id="e-ticaret",
    name="E-Ticaret Departmanı",
    mission="Ürün kataloğu, mağaza operasyonu ve satış büyümesi.",
    keywords=("e-ticaret", "eticaret", "magaza", "urun", "sepet", "shopify"),
    teams=(
        TeamTemplate(
            team_id="catalog",
            name="Katalog Ekibi",
            mission="Ürün verisi, görseller ve fiyatlandırma.",
            capabilities=("product_data", "pricing", "content"),
            lead_role="data_analyst",
        ),
        TeamTemplate(
            team_id="storefront",
            name="Mağaza Ekibi",
            mission="Vitrin, kampanya ve kullanıcı deneyimi.",
            capabilities=("merchandising", "ux", "campaigns"),
            lead_role="designer",
        ),
        TeamTemplate(
            team_id="growth",
            name="Büyüme Ekibi",
            mission="Trafik, dönüşüm ve elde tutma.",
            capabilities=("marketing", "analytics", "retention"),
            lead_role="marketing_specialist",
        ),
        TeamTemplate(
            team_id="support",
            name="Destek Ekibi",
            mission="Sipariş ve müşteri desteği.",
            capabilities=("support", "ticket_triage", "logistics"),
            lead_role="customer_support",
            specialist_role="customer_support",
        ),
    ),
)

_VIDEO = DomainTemplate(
    domain_id="video",
    name="Video Prodüksiyon Departmanı",
    mission="Senaryodan kurguya video üretimi ve dağıtımı.",
    keywords=("video", "prodüksiyon", "reels", "youtube", "kurgu", "film"),
    teams=(
        TeamTemplate(
            team_id="preproduction",
            name="Ön Hazırlık Ekibi",
            mission="Senaryo, çekim planı ve bütçe.",
            capabilities=("screenplay", "storyboard", "planning"),
            lead_role="researcher",
        ),
        TeamTemplate(
            team_id="production",
            name="Çekim Ekibi",
            mission="Çekim ve saha yönetimi.",
            capabilities=("filming", "lighting", "direction"),
            lead_role="designer",
        ),
        TeamTemplate(
            team_id="post",
            name="Post Prodüksiyon Ekibi",
            mission="Kurgu, renk ve ses.",
            capabilities=("editing", "color_grading", "sound_design"),
            lead_role="designer",
        ),
        TeamTemplate(
            team_id="growth",
            name="Dağıtım Ekibi",
            mission="Yayın planı ve izlenme büyümesi.",
            capabilities=("distribution", "marketing", "analytics"),
            lead_role="marketing_specialist",
        ),
    ),
)

_MUSIC = DomainTemplate(
    domain_id="muzik",
    name="Müzik Prodüksiyon Departmanı",
    mission="Şarkı, düzenleme ve yayın üretimi.",
    keywords=("muzik", "music", "sarki", "album", "beat", "mix"),
    teams=(
        TeamTemplate(
            team_id="composition",
            name="Kompozisyon Ekibi",
            mission="Melodi, söz ve düzenleme.",
            capabilities=("composition", "lyrics", "arrangement"),
            lead_role="researcher",
        ),
        TeamTemplate(
            team_id="production",
            name="Prodüksiyon Ekibi",
            mission="Kayıt, miks ve mastering.",
            capabilities=("recording", "mixing", "mastering"),
            lead_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="release",
            name="Yayın Ekibi",
            mission="Dağıtım, kapak ve tanıtım.",
            capabilities=("distribution", "marketing", "design"),
            lead_role="marketing_specialist",
        ),
    ),
)

_GAME = DomainTemplate(
    domain_id="oyun",
    name="Oyun Geliştirme Departmanı",
    mission=(
        "Oyunları tasarlamak, geliştirmek, paketlemek ve canlı servis olarak "
        "büyütmek: oynanış, mühendislik, sanat, ses, kalite ve gelir."
    ),
    keywords=(
        "oyun",
        "game",
        "unity",
        "unreal",
        "mobil oyun",
        "level",
        "oynanis",
        "mipiluna",
        "pixel",
        "steam",
    ),
    teams=(
        TeamTemplate(
            team_id="design",
            name="Oynanış Tasarımı",
            mission="Mekanik, seviye, denge ve oyun ekonomisi tasarımı.",
            capabilities=("game_design", "level_design", "balancing", "economy"),
            lead_role="researcher",
        ),
        TeamTemplate(
            team_id="engineering",
            name="Oyun Mühendisliği",
            mission="Oynanış kodu, fizik, kayıt sistemi ve araç geliştirme.",
            capabilities=(
                "javascript",
                "html5",
                "gameplay",
                "physics",
                "save_system",
            ),
            lead_role="software_engineer",
            specialist_role="software_engineer",
        ),
        TeamTemplate(
            team_id="platform",
            name="Platform ve Paketleme",
            mission="Web, masaüstü ve Android paketlerinin build ve dağıtımı.",
            capabilities=("capacitor", "android", "build_pipeline", "release"),
            lead_role="devops_engineer",
            specialist_role="devops_engineer",
        ),
        TeamTemplate(
            team_id="art",
            name="Sanat ve Animasyon",
            mission="Karakter, çevre, arayüz ve animasyon üretimi.",
            capabilities=("character_design", "animation", "ui", "asset_pipeline"),
            lead_role="designer",
            specialist_role="designer",
        ),
        TeamTemplate(
            team_id="audio",
            name="Ses ve Müzik",
            mission="Seslendirme, müzik, efekt ve miksaj.",
            capabilities=("voice_over", "music", "sound_design", "mixing"),
            lead_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="quality",
            name="Kalite ve Güvenlik",
            mission="Regresyon, performans ve çocuk güvenliği denetimi.",
            capabilities=("testing", "regression", "performance", "child_safety"),
            lead_role="qa_engineer",
            specialist_role="qa_engineer",
        ),
        TeamTemplate(
            team_id="growth",
            name="Canlı Servis ve Büyüme",
            mission="Yayın takvimi, mağaza listesi, topluluk ve gelir modeli.",
            capabilities=("live_ops", "monetization", "store_listing", "community"),
            lead_role="marketing_specialist",
            specialist_role="sales_specialist",
        ),
    ),
)

_EDUCATION = DomainTemplate(
    domain_id="egitim",
    name="Eğitim Departmanı",
    mission="Müfredat, içerik ve öğrenme deneyimi üretimi.",
    keywords=("egitim", "kurs", "education", "mufredat", "ogrenci", "training"),
    teams=(
        TeamTemplate(
            team_id="curriculum",
            name="Müfredat Ekibi",
            mission="Program tasarımı ve öğrenme hedefleri.",
            capabilities=("curriculum", "research", "assessment"),
            lead_role="researcher",
        ),
        TeamTemplate(
            team_id="content",
            name="İçerik Ekibi",
            mission="Ders materyali ve video üretimi.",
            capabilities=("content", "video", "design"),
            lead_role="designer",
        ),
        TeamTemplate(
            team_id="delivery",
            name="Teslim Ekibi",
            mission="Platform kurulumu ve öğrenci desteği.",
            capabilities=("operations", "support", "reporting"),
            lead_role="operations_specialist",
        ),
    ),
)

_GENERIC = DomainTemplate(
    domain_id="genel",
    name="Genel İş Departmanı",
    mission="Sahibin verdiği görevleri planlayıp üretmek.",
    keywords=(),
    teams=(
        TeamTemplate(
            team_id="delivery",
            name="Üretim Ekibi",
            mission="Görevi analiz edip çıktıyı üretmek.",
            capabilities=("analysis", "production", "documentation"),
            lead_role="operations_specialist",
        ),
        TeamTemplate(
            team_id="quality",
            name="Kalite Ekibi",
            mission="Çıktıyı kontrol etmek.",
            capabilities=("qa", "verification"),
            lead_role="qa_engineer",
            specialist_role="qa_engineer",
        ),
        TeamTemplate(
            team_id="growth",
            name="Büyüme Ekibi",
            mission="Müşteri ve pazar tarafı.",
            capabilities=("marketing", "sales"),
            lead_role="marketing_specialist",
            specialist_role="sales_specialist",
        ),
    ),
)

_SEED_LINKS: dict[str, str] = {
    "cizgi-film": "creative",
    "yazilim": "software",
    "pazarlama": "marketing",
}

DOMAIN_TEMPLATES: tuple[DomainTemplate, ...] = tuple(
    replace(template, seed_department_id=_SEED_LINKS.get(template.domain_id))
    for template in (
        _ANIMATION,
        _SOFTWARE,
        _MARKETING,
        _ECOMMERCE,
        _VIDEO,
        _MUSIC,
        _GAME,
        _EDUCATION,
    )
)


def match_domain(text: str) -> DomainTemplate | None:
    """Return the most specific known domain mentioned in ``text``."""

    folded = ascii_fold(text)
    best: tuple[int, int, DomainTemplate] | None = None

    for index, template in enumerate(DOMAIN_TEMPLATES):
        score = 0
        for keyword in template.keywords:
            folded_keyword = ascii_fold(keyword)
            if " " in folded_keyword:
                if folded_keyword in folded:
                    score += max(10, len(folded_keyword))
            elif _contains_word(folded, folded_keyword):
                score += 10
        if score and (best is None or (score, -index) > (best[0], -best[1])):
            best = (score, index, template)

    return best[2] if best else None


def _contains_word(haystack: str, needle: str) -> bool:
    return f" {needle} " in f" {haystack} "


def synthesize_department(
    owner_text: str,
    *,
    domain: DomainTemplate | None = None,
    department_id: str | None = None,
    created_at: str | None = None,
) -> DepartmentSpec:
    """Build a validated department from a natural-language owner request.

    The result always contains a manager, one lead plus one specialist per team,
    a capability catalogue and routing keywords, so it can be registered and
    staffed immediately.
    """

    template = domain or match_domain(owner_text) or _GENERIC
    resolved_id = department_id or _unique_department_id(template, owner_text)
    folded_keywords = tuple(ascii_fold(keyword) for keyword in template.keywords)

    manager_capabilities = set(_MANAGER_CAPABILITIES)
    manager_capabilities.add(f"{template.domain_id}_oversight")

    workers: list[WorkerSpec] = [
        WorkerSpec(
            worker_id=f"{resolved_id}-manager",
            name=f"{template.name} Müdürü",
            role=MANAGER_ROLE,
            team_id=f"{resolved_id}-leadership",
            capabilities=frozenset(manager_capabilities),
            reports_to=None,
            authority_level="A",
        )
    ]

    capabilities: list[CapabilitySpec] = [
        CapabilitySpec(
            name=f"{template.domain_id}.{skill}",
            description=(
                f"{template.domain_id} {skill} capability. "
                f"Keywords: {' '.join(folded_keywords)}."
            ),
            authority="A" if skill in {"planning", "routing", "task_decomposition"} else "B",
        )
        for skill in sorted(manager_capabilities)
    ]
    seen_capabilities = {capability.name for capability in capabilities}

    for team in template.teams:
        lead_id = f"{resolved_id}-{team.team_id}-lead"
        specialist_id = f"{resolved_id}-{team.team_id}-specialist"

        workers.append(
            WorkerSpec(
                worker_id=lead_id,
                name=f"{team.name} Lideri",
                role=team.lead_role,
                team_id=f"{resolved_id}-{team.team_id}",
                capabilities=frozenset(team.capabilities),
                reports_to=f"{resolved_id}-manager",
                authority_level="B",
            )
        )
        workers.append(
            WorkerSpec(
                worker_id=specialist_id,
                name=f"{team.name} Uzmanı",
                role=team.specialist_role,
                team_id=f"{resolved_id}-{team.team_id}",
                capabilities=frozenset(team.capabilities),
                reports_to=lead_id,
                authority_level="C",
            )
        )

        for skill in team.capabilities:
            name = f"{template.domain_id}.{skill}"
            if name in seen_capabilities:
                continue
            seen_capabilities.add(name)
            capabilities.append(
                CapabilitySpec(
                    name=name,
                    description=(
                        f"{template.domain_id} {skill} capability. "
                        f"Keywords: {' '.join(folded_keywords)} "
                        f"Team mission: {team.mission}"
                    ),
                    authority="B",
                )
            )

    return DepartmentSpec(
        department_id=resolved_id,
        name=template.name,
        mission=f"{template.name}: {template.mission}",
        capabilities=tuple(capabilities),
        workers=tuple(workers),
        keywords=folded_keywords,
        created_at=created_at or utc_now(),
        source="owner-command",
        status="active",
    )


def _unique_department_id(template: DomainTemplate, owner_text: str) -> str:
    """Derive a stable id; the console disambiguates when the id is taken."""

    if template.seed_department_id:
        return template.seed_department_id
    return template.domain_id


def next_available_id(book, base_id: str) -> str:
    """Return ``base_id`` or the first free ``base_id-N`` in the book."""

    if not book.has(base_id):
        return base_id
    for index in range(2, 1000):
        candidate = f"{base_id}-{index}"
        if not book.has(candidate):
            return candidate
    raise DepartmentBookError(f"no free department id for {base_id!r}")
