"""Curated ECC ideas, expressed for AHOS; data only, no hooks or API calls.

Sources reviewed 2026-11-07. ECC: https://github.com/affaan-m/ECC (MIT).
These notes do not install ECC, train a model, or confer verified competence.
"""

REFERENCES = (
    {
        "name": "ECC / AHOS: kanıtlı doğrulama",
        "path": "https://github.com/affaan-m/ECC/blob/main/skills/verification-loop/SKILL.md",
        "keywords": ["test", "pytest", "kabul", "dogrulama", "kalite", "verification", "qa"],
        "text": "Test ve kabul doğrulaması: Derleme, tür/lint, test, güvenlik ve diff incelemesini ayrı sonuçlarla kaydet. "
                "AHOS'ta her denetimin komutunu, çalışma dizinini, ham çıktısını, çıkış kodunu ve zamanını sakla. "
                "İzole test başarısı canlı kabul değildir; canlı kontrol yapılmadıysa bunu açıkça belirt. "
                "Ölçülmeyen kapsamı başarılı sayma. Mevcut güven kapısını değiştirme; yanlış veya boş teslimi reddet.",
    },
    {
        "name": "ECC / AHOS: proje bazlı öğrenme",
        "path": "https://github.com/affaan-m/ECC/blob/main/skills/continuous-learning-v2/SKILL.md",
        "keywords": ["ogrenme", "ogren", "hafiza", "deneyim", "learning", "memory", "ders"],
        "text": "Öğrenme ve hafıza: Her ders tek bir gözlem ve öneri içersin; proje, departman, kaynak ve doğrulama kanıtı ile saklansın. "
                "Bir projedeki kuralı başka projelere otomatik yayma. Güven puanı doğruluk kanıtı değildir. "
                "AHOS'ta yalnız bağımsız kabulden geçen görev sonucu doğrulanmış deneyim sayılır. "
                "Sohbet metni veya işçi beyanı tek başına başarı değildir. Eski dersleri yeni test sonuçlarıyla yeniden değerlendir. "
                "Bu yaklaşım model ağırlıklarını eğitmez; görev sırasında başvurulan kayıtları iyileştirir.",
    },
)


def reference_rows():
    """Fresh dictionaries prevent callers from mutating shared reference data."""
    return [{**row, "keywords": list(row["keywords"])} for row in REFERENCES]
