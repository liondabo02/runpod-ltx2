# AHOS 3D Operasyon Merkezi — V2

## Canlı ofis

Gerçek kaynak: GET /api/agent-office. Odalar 17 departmanı ve CEO alanını; avatarlar
81 kayıtlı işçiyi temsil eder. Çalışma halkası ve oda ışığı yalnızca
activity_verified=true olduğunda aktif görünür. Bekleyen/iptal edilen görevler
başarılı teslimat kabul edilmez.

## Yeni kontroller

- Genel görünüm: bütün holding kampüsünü gösterir (klavye: 1).
- CEO odası: altın vurgulu Harun yönetim odasını merkeze alır (klavye: 2).
- Üstten bakış: tesis haritası ve departmanların tam yerleşimi (klavye: 3).
- Kat planı: haritadaki gerçek departman noktasına tıklayarak odaklanma; ok tuşları
  ve Enter ile klavyeden gezinme.
- Çalışan/departman araması: isim veya kimlik parçasını yazıp Enter.
  Arama kısayolu: /.
- Çalışan kartı: adı, rolü, yetenekleri, son görev kaydı, ölçülen çalışma sayısı,
  başarı oranı (kanıt yoksa açıkça belirtilir) ve doğrulanmış aktiflik.
- Operasyon radarı: yalnızca /api/agent-office feed olaylarından beslenen güvenli
  metin akışı; başka görev veya başarı üretmez.
- Performans modu: gölge ve görüntü piksel yoğunluğunu azaltır.
- Hareketi azalt: işletim sistemindeki reduced-motion tercihini varsayılan olarak
  dikkate alır, istenirse el ile değiştirilir.
- Oda ve çalışan isim etiketleri isteğe göre kapatılabilir.

## Güvenlik ve uygulama

Dinamik metinler innerHTML ile değil textContent ve DOM düğümleriyle gösterilir.
Ofis bilgileri gerçek işçi/görev API verileriyle eşleşmelidir. Sohbet endpoint'i
403 döndürürse sahip oturumu gerektiği açıkça belirtilir.
Bu özellikler görev üretmez, izin yükseltmez, ücretli API çağrısı yapmaz.

3D işçi animasyonları dekoratiftir; hiçbir animasyon doğrulanmış çalışma ya da
insan bilinci kanıtı değildir. Yapay zekâ modüllerinin mevcut yetki ve QA
sınırları aynen korunur.

## Doğrulama

cd ahos_core
python -m pytest -q tests/test_office_3d.py tests/test_office_3d_operations.py
python -m pytest -q tests

Canlı yol: http://127.0.0.1:8766/agent-office
HTML JavaScript modülü Node --check ile doğrulanır. Gerçek görüntü WebGL ve
three.js CDN erişimine bağlıdır.

## Sonraki görsel faz

Üç boyutlu kat geçişi, karakter kişiselleştirme, ekran içi bilgi panoları,
3D proje sunum odaları, erişilebilir dolaşım, VR denemesi ve işçi avatarlarına
özgün sesler ayrı test ve performans bütçesi ile geliştirilebilir. Ancak mevcut
kaynaklar izin vermiyorsa bu özellikler canlıda yapılmış gibi raporlanmamalıdır.
