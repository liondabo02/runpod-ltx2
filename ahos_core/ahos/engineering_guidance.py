"""Reviewed adaptations, not executable upstream agents or extra permissions."""
SOURCES = (
    'https://code.claude.com/docs/en/best-practices',
    'https://code.claude.com/docs/en/hooks',
    'https://github.com/anthropics/claude-plugins-official/tree/main/plugins/feature-dev',
    'https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-manager-senior.md',
    'https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md',
)


def engineering_guidance():
    return (
        'Mühendislik çalışma sözleşmesi (Agency Agents yöntemlerinden uyarlama):\n'
        '- Hedefteki gerçek gereksinimi esas al; kapsamı gereksiz büyütme.\n'
        '- Önce ilgili kaynakları ve bağımlılıkları incele. Eksik bağlamı uydurma.\n'
        '- Keşif sonucunu kısa planla ilişkilendir; mevcut mimariyi genişlet.\n'
        '- Onarımdan sonra bütün aday dosyaları gözden geçir; son dosyayla yetinme.\n'
        '- Her değişikliği gereksinim ve ölçülebilir kabul koşuluyla ilişkilendir.\n'
        '- İşçi özeti, test yapıldığına veya ürünün çalıştığına kanıt değildir.\n'
        '- Test edilmemiş davranışı ve kalan engelleri açıkça belirt.\n'
        '- Arayüz için kullanıcı yolculuğu, hata durumları ve görsel inceleme ayrıdır.\n'
        '- Bu rehber yürütme izni vermez; kaynak aktarımı, bütçe, sandbox ve onay sınırları geçerlidir.\n'
    )
