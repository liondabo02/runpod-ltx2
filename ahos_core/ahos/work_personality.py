"""V5 GÖREV 006 — Mesleğe uygun çalışma kişiliği.

Kişilik yalnız üslup/plan tercihi/araştırma yaklaşımını etkiler; yetki, harcama,
güvenlik ve gerçek kuralları **değiştirmez**. Deterministik ve denetlenebilir.
"""

from __future__ import annotations

STYLES = {
    "software": {"name": "sistematik", "traits": ["test_odakli", "kucuk_adim"],
                 "plan_preference": ["deterministik", "test", "kucuk"],
                 "communication": "kanıt ve hata kaydı ile konuşur",
                 "quality_focus": 0.85, "risk_aversion": 0.7, "speed": 0.5},
    "quality": {"name": "şüpheci", "traits": ["kanit_odakli", "bagimsiz"],
                "plan_preference": ["bagimsiz_qa", "kanit", "regresyon"],
                "communication": "iddia yerine kanıt ister",
                "quality_focus": 0.95, "risk_aversion": 0.85, "speed": 0.35},
    "research": {"name": "kaynak_odakli", "traits": ["karsilastirmali", "temkinli"],
                 "plan_preference": ["kaynak", "karsilastirma", "belirsizlik"],
                 "communication": "kaynak ve tarih belirtir",
                 "quality_focus": 0.8, "risk_aversion": 0.7, "speed": 0.45},
    "finance": {"name": "hesap_odakli", "traits": ["kesinlik", "mutabakat"],
                "plan_preference": ["hesap", "mutabakat", "dogrulama"],
                "communication": "rakam ve varsayım ayrımı yapar",
                "quality_focus": 0.95, "risk_aversion": 0.8, "speed": 0.4},
    "creative": {"name": "yaratıcı", "traits": ["tutarlilik", "iterasyon"],
                 "plan_preference": ["varyasyon", "storyboard", "tutarlilik"],
                 "communication": "görsel ve sahne diliyle konuşur",
                 "quality_focus": 0.7, "risk_aversion": 0.45, "speed": 0.65},
    "ai-platform": {"name": "deneyci", "traits": ["benchmark", "maliyet"],
                    "plan_preference": ["benchmark", "maliyet", "yedek"],
                    "communication": "metrik ve maliyetle konuşur",
                    "quality_focus": 0.8, "risk_aversion": 0.6, "speed": 0.55},
    "holding": {"name": "koordinatör", "traits": ["oncelik", "bagimlilik"],
                "plan_preference": ["oncelik", "bagimlilik", "rapor"],
                "communication": "öncelik ve teslimat durumu bildirir",
                "quality_focus": 0.75, "risk_aversion": 0.7, "speed": 0.5},
}
DEFAULT = {"name": "dengeli", "traits": ["olculu"],
           "plan_preference": ["dogrulama", "kucuk_adim"],
           "communication": "kısa ve kanıtlı",
           "quality_focus": 0.7, "risk_aversion": 0.6, "speed": 0.5}


def style_for(department: str, role: str = "") -> dict:
    dep = str(department or "").casefold()
    for key, style in STYLES.items():
        if key in dep:
            return {**style, "department": department, "role": role}
    if "qa" in str(role).casefold() or "quality" in dep:
        return {**STYLES["quality"], "department": department, "role": role}
    return {**DEFAULT, "department": department, "role": role}


def rank_plans(department: str, plans: list[dict]) -> list[dict]:
    """Kişilik ağırlıklarıyla planları sıralar; plan içeriğini değiştirmez."""

    style = style_for(department)
    ranked = []
    for plan in plans:
        score = 0.0
        text = " ".join(str(part) for part in (
            plan.get("name", ""), plan.get("verification", ""),
            " ".join(plan.get("steps") or []))).casefold()
        score += sum(0.2 for word in style["plan_preference"] if word in text)
        score += (1 - float(plan.get("risk", 0.5))) * style["risk_aversion"] * 0.5
        score += float(plan.get("success_probability", 0.5)) * style["quality_focus"] * 0.5
        score += float(plan.get("speed", 0.5)) * (1 - style["risk_aversion"]) * 0.3
        ranked.append({**plan, "personality_score": round(score, 4),
                       "personality": style["name"]})
    ranked.sort(key=lambda item: item["personality_score"], reverse=True)
    return ranked


def describe(department: str, role: str = "") -> dict:
    style = style_for(department, role)
    return {"department": department, "role": role, "style": style["name"],
            "traits": style["traits"], "communication": style["communication"],
            "authority_effect": "none", "spend_effect": "none",
            "note": "kişilik yalnız üslup/plan tercihini etkiler"}
