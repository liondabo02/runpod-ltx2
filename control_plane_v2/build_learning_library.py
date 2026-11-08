from pathlib import Path
import ast
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent / 'ajan_egitim_kutuphanesi_v1'
ROOT.mkdir(exist_ok=True)

# Original educational summaries. No third-party repository contents are bundled.
TOPICS = [
('programlama_temelleri', 'Programlama temelleri / programming fundamentals', 'Değişken, tür, koşul, döngü ve fonksiyon kavramlarını küçük örneklerle öğren.|Girdiyi, çıktıyı ve başarısızlık durumlarını koddan önce tanımla.|Saf fonksiyon aynı girdide aynı sonucu üretir; dış etkileri sınırda tut.|Boş veri, sıfır, negatif değer ve Unicode için sınır durumlarını dene.', 'Bir listedeki geçerli pozitif sayıların toplamını hesaplayan fonksiyon yaz.', 'Boş listede 0 dönmeli; geçersiz türlerin davranışı açıkça tanımlanmalı.'),
('algoritmalar', 'Algoritmalar ve karmaşıklık / algorithms complexity', 'Zaman ve bellek maliyetini girdi boyutuna göre değerlendir.|İkili arama sıralı veri ister; sıralama maliyetini hesaba kat.|Hash tablosu araması ortalama sabit zamanlı olabilir; en kötü durum garantisi değildir.|Ölçüm yapmadan mikro optimizasyon uygulama.', 'Sıralı listede ilk eşleşmenin indeksini bul.', 'Boş liste, yinelenen değerler, bulunamayan hedef ve uç elemanlar test edilmeli.'),
('veri_yapilari', 'Veri yapıları / data structures', 'Liste sıralı dolaşım, küme üyelik, sözlük anahtar-değer erişimi içindir.|Kuyrukta FIFO, yığında LIFO davranışını koru.|Graf dolaşımında ziyaret edilen düğümleri kaydet.|Değiştirilebilir ortak verinin sahipliğini açık tut.', 'Bir grafın başlangıç düğümünden erişilen düğümlerini BFS ile çıkar.', 'Döngülü graf sonsuza kadar çalışmamalı; kopuk düğümler çıktıya girmemeli.'),
('python', 'Python geliştirme', 'Ortam bağımlılıklarını proje bazında ayır ve sürümleri kaydet.|Dosya ve bağlantılar için context manager kullan.|Mutable varsayılan argüman yerine None kullan.|Beklenen istisnaları dar kapsamda yakala; hatayı sessizce yutma.', 'UTF-8 metin dosyasındaki boş olmayan satırları say.', 'Eksik dosya anlaşılır hata vermeli; kaynaklar kapanmalı; Türkçe karakterler korunmalı.'),
('javascript', 'JavaScript geliştirme', 'Tür dönüşümünü açık tut; eşitlikte çoğunlukla === kullan.|Promise hatalarını await ve try/catch ile yönet.|Event loop içinde uzun CPU işlerini böl veya worker kullan.|Kullanıcı metnini HTML olarak doğrudan enjekte etme.', 'Bir dizi nesneyi kimlik alanına göre tekilleştir.', 'Kimlik tipi ve eksik kimlik politikası tanımlı olmalı; giriş değişmemeli.'),
('typescript', 'TypeScript geliştirme', 'Dış JSON verisini çalışma zamanında doğrula; tür bildirimi doğrulama değildir.|unknown verisini daraltmadan kullanma.|Birbirini dışlayan durumları discriminated union ile modelle.|Derleyici sürümü ve strict ayarını projede sabitle.', 'Başarı ve hata sonuçları için ayrık birleşim tipi tasarla.', 'Tüm durumlar ele alınmalı; geçersiz dış veri reddedilmeli.'),
('c_cpp', 'C ve C++ bellek yönetimi', 'C dilinde ayırdığın belleğin sahipliğini ve serbest bırakılmasını izle.|C++ içinde RAII ve uygun standart kütüphane kapsayıcılarını tercih et.|Dizi sınırlarını ve tamsayı taşmasını değerlendir.|Sanitizer araçlarıyla bellek hatalarını araştır; derleyici uyarılarını incele.', 'Bir bayt tamponundan sınır kontrollü okuma fonksiyonu tasarla.', 'Sıfır uzunluk, sınır aşımı ve geçersiz giriş politikası test edilmeli.'),
('java_csharp', 'Java ve C# uygulamaları', 'Kaynak kapatmayı try-with-resources veya using ile yönet.|Paylaşılan değiştirilebilir durumu iş parçacıkları arasında koru.|Null olasılığını API sözleşmesinde belirt.|Veritabanı ve HTTP çağrılarında iptal ve zaman aşımı uygula.', 'İptal edilebilir bir servis çağrısı arayüzü tasarla.', 'İptal, zaman aşımı ve başarılı yanıt ayrı davranışlar olarak doğrulanmalı.'),
('go_rust', 'Go ve Rust sistem geliştirme', 'Go içinde context ile iptal ve süre bütçesini aktar.|Goroutine yaşam döngüsünü yönet; kapanmayan kanal ve görevleri incele.|Rust sahiplik ve ödünç alma kurallarını veri yaşam süresini açık kılmak için kullan.|Rust Result veya Go error değerlerini bağlam ekleyerek ilet.', 'Sınırlı eşzamanlılıkla çalışan bir iş kuyruğu tasarla.', 'İptal sonrası görev sızıntısı olmamalı; eşzamanlı iş sayısı sınırı aşmamalı.'),
('diger_diller', 'Ruby PHP Swift Kotlin R SQL Bash PowerShell', 'Her dilin paket yöneticisini ve çalışma ortamını proje belgelerinde belirt.|Swift ve Kotlin mobil yaşam döngüsü ile iptal davranışını gözetir.|R analizinde eksik veri ve rastgelelik tohumunu kaydet.|Shell komutlarında kullanıcı girdisini kodla birleştirme; argümanları güvenli aktar.', 'Aynı veri dönüştürme görevini iki dilde uygula.', 'Çıktı sözleşmesi eşit olmalı; locale ve Unicode farkları açıklanmalı.'),
('git', 'Git ve sürüm kontrolü', 'Değişiklikten önce durum ve diff incele.|Küçük, tek amaçlı commit oluştur.|Paylaşılan geçmişi yeniden yazmadan önce ekip politikasını kontrol et.|Çatışmayı çözerken iki tarafın amaçlarını anla ve sonucu doğrula.', 'İki dalın aynı fonksiyonda yaptığı değişiklikleri birleştir.', 'Çatışma işaretleri kalmamalı; her iki gereksinim de doğrulanmalı.'),
('test', 'Yazılım testi / testing', 'Testi uygulama ayrıntısına değil gözlenen davranışa bağla.|Birim, entegrasyon ve uçtan uca testleri riskle orantılı seç.|Zaman, ağ ve rastgelelik kaynaklarını kontrol edilebilir yap.|Bir hata düzeltmesinde mümkünse hatayı gösteren regresyon testi ekle.', 'Bir fiyat hesaplayıcısının indirim sınırlarını test et.', 'Yüzde 0 ve 100, yuvarlama ve geçersiz oran politikası kapsanmalı.'),
('debug', 'Hata ayıklama / debugging', 'Hatanın en küçük tekrarlanabilir örneğini çıkar.|Belirti, hipotez ve kanıtı birbirinden ayır.|Stack trace ve logları gizli veri sızdırmadan kullan.|Kök neden düzeldikten sonra ilgili davranışı tekrar çalıştır.', 'Aralıklı başarısız olan bir isteği korelasyon kimliğiyle izle.', 'Aynı istek boyunca iz kurulmalı; loglar parola veya token içermemeli.'),
('mimari', 'Yazılım mimarisi ve tasarım', 'Modül sınırlarını veri sahipliği ve değişim nedenlerine göre kur.|Bağımlılık yönlerini açık tut; döngüleri azalt.|Dağıtık sistem maliyetini haklı gereksinim olmadan ekleme.|Mimari kararlarda bağlamı, seçenekleri ve sonuçları kaydet.', 'Sipariş uygulaması için modül sınırları öner.', 'İş kuralları taşıma protokolünden bağımsız test edilebilmeli.'),
('http_api', 'HTTP REST API tasarımı', 'HTTP yöntemlerini ve durum kodlarını sözleşmeyle uyumlu kullan.|Girdi boyutu, türü ve erişim hakkını sunucuda doğrula.|Yazma tekrarlarında idempotency anahtarı ve sonuç saklama politikasını tanımla.|Sayfalama, zaman aşımı ve hata biçimini belgele.', 'Sipariş oluşturma uç noktası sözleşmesi yaz.', 'Aynı idempotency anahtarıyla tekrar çağrı ikinci sipariş üretmemeli.'),
('frontend', 'HTML CSS erişilebilirlik ve frontend', 'Semantik HTML ve klavye erişimini temel al.|Form alanlarını etiketlerle ilişkilendir; hata mesajını okunabilir ver.|Yükleniyor, boş, hata ve başarı durumlarını tasarla.|Ekran boyutu ve metin büyütme altında yerleşimi kontrol et.', 'Erişilebilir bir arama formu oluştur.', 'Klavye ile kullanılmalı; odak görünmeli; sonuç durumu anlaşılmalı.'),
('backend', 'Backend servis geliştirme', 'İş kurallarını HTTP işleyicisinden ayır.|İstek başına zaman ve kaynak bütçesi koy.|Yetkilendirmeyi her kaynak erişiminde kontrol et.|Dış servis hatalarını sınırlı retry ve uygun hata yanıtıyla yönet.', 'Kullanıcının yalnızca kendi kaydını okuyabildiği servis tasarla.', 'Başka kullanıcı kimliğiyle erişim engellenmeli; hata ayrıntısı gizli veri vermemeli.'),
('mobil_masaustu', 'Mobil masaüstü ve oyun geliştirme', 'UI iş parçacığını uzun işlemlerle engelleme.|Yerel veri ve ağ senkronizasyonunda çatışma politikasını tanımla.|Mobil uygulamada izinleri ihtiyaç anında iste.|Oyun döngüsünde simülasyon zamanı ve çizim zamanını bilinçli ayır.', 'Çevrimdışı düzenlenen notları senkronize et.', 'Yinelenen gönderim ve aynı notun iki cihazda düzenlenmesi ele alınmalı.'),
('sql', 'SQL ilişkisel veritabanları', 'Sorgu değerlerini parametrelerle aktar.|Benzersizlik ve referans bütünlüğünü uygun constraint ile koru.|İndeksi sorgu planı ve yazma maliyetiyle birlikte değerlendir.|İzolasyon seviyesini eşzamanlı iş kurallarına göre seç.', 'Stok azaltma işlemini eşzamanlı siparişlerde güvenli yap.', 'Stok negatif olmamalı; başarısız işlem kısmi değişiklik bırakmamalı.'),
('nosql_cache', 'NoSQL Redis önbellek ve arama', 'Veri modelini erişim kalıplarına göre seç.|TTL tek başına tüm tutarlılık sorunlarını çözmez.|Önbellek anahtarına kullanıcı veya tenant kapsamını ekle.|Cache stampede için sınırlı kilit veya istek birleştirme değerlendir.', 'Ürün detayları için cache-aside akışı kur.', 'Güncelleme sonrası eski veri süresi ve invalidation davranışı tanımlanmalı.'),
('linux_ag', 'Linux işletim sistemi ve ağlar', 'Dosya izinlerini en az yetkiyle ayarla.|DNS çözümleme, TCP bağlantı, TLS ve uygulama hatasını ayrı incele.|Disk, bellek, CPU ve dosya tanıtıcılarını birlikte izle.|Sinyal ve kapanış akışında kaynakları temizle.', 'Bir servise erişilememe sorununu katmanlara ayır.', 'Her hipotez ölçülebilir bir komut veya log kanıtıyla sınanmalı.'),
('docker_kubernetes', 'Docker konteyner Kubernetes', 'İmaj içine anahtar ve parola koyma.|Çalışma kullanıcısını ve gereken izinleri açık belirle.|Readiness trafik alabilmeyi; liveness yeniden başlatma ihtiyacını temsil eder.|Kaynak istekleri, limitler ve kapanış süresini gerçek yükte ölç.', 'Bir web servisi için konteyner dağıtımını tasarla.', 'Sağlıksız örnek trafik almamalı; kapanışta devam eden istekler yönetilmeli.'),
('cicd', 'CI CD ve sürümleme', 'Kontrolleri değişiklik riskiyle orantılı otomatikleştir.|Bağımlılık ve derleme çıktılarının kaynağını izlenebilir tut.|Üretim geçişinde sağlık kontrolü ve geri dönüş planı hazırla.|CI sırlarını log ve fork iş akışlarına sızdırma.', 'Test ve paket üretimi yapan bir pipeline tasarla.', 'Başarısız testte yayın yapılmamalı; paket commit ile ilişkilendirilmeli.'),
('dagitik_sistem', 'Dağıtık sistemler ve kuyruklar', 'Ağ hatası ve tekrar teslimini normal durum kabul et.|En az bir kez teslim edilen işleyiciyi idempotent yap.|Retry sayısı, jitter ve toplam süreyi sınırla.|Veritabanı ile mesaj yayını arasında outbox yaklaşımını değerlendir.', 'Aynı ödeme bildirimini iki kez alan tüketici tasarla.', 'Tek iş etkisi oluşmalı; kalıcı hata dead-letter veya inceleme akışına gitmeli.'),
('guvenlik', 'Güvenli yazılım geliştirme', 'Kimlik doğrulama ile yetkilendirmeyi ayrı kontrol et.|Sırları ortamın güvenli sır yönetiminde sakla.|Parolaları uygun parola hash yöntemiyle sakla; düz metin veya hızlı genel hash kullanma.|SQL injection, XSS, SSRF ve dosya yolu geçişlerini güven sınırlarında değerlendir.', 'Dosya indirme uç noktasında yol geçişini engelle.', 'Çözümlenen yol izinli kök içinde kalmalı; sembolik bağlantı politikası açıklanmalı.'),
('gozlemlenebilirlik', 'Log metrik tracing ve SRE', 'Loglara korelasyon kimliği ekle ve hassas alanları maskele.|Gecikme, trafik, hata ve kaynak doygunluğunu izle.|SLO hedefini kullanıcı etkisine bağla.|Alarmı eyleme geçirilebilir eşik ve çalışma kılavuzuyla eşleştir.', 'Bir API için hata bütçesi ve alarm planı yaz.', 'Alarm sahipliği ve ilk müdahale adımları belli olmalı.'),
('veri_muhendisligi', 'Veri mühendisliği ETL ve analiz', 'Şema, kaynak, dönüşüm ve veri soy ağacını kaydet.|Eksik ve yinelenen kayıt politikalarını belirle.|Artımlı işlemde watermark ve geç gelen veri davranışını tanımla.|Kişisel veriyi gereksiz toplamaktan kaçın; erişimi sınırla.', 'Günlük olaylardan tekrar çalıştırılabilir özet üret.', 'Aynı gün yeniden işlendiğinde toplamlar ikiye katlanmamalı.'),
('makine_ogrenmesi', 'Makine öğrenmesi / machine learning', 'Eğitim doğrulama ve test verisini sızıntıyı önleyecek biçimde ayır.|Ön işleme parametrelerini yalnız eğitim verisinde öğren.|Basit bir baseline ile karşılaştır.|Metrikleri sınıf dengesizliği ve hata maliyetine göre seç.', 'Dengesiz sınıflandırmada bir değerlendirme planı hazırla.', 'Precision recall ve karar eşiği tartışılmalı; test kümesi ayar için kullanılmamalı.'),
('derin_ogrenme', 'Derin öğrenme ve GPU', 'Tensor şekli, dtype ve cihaz bilgisini kontrol et.|Eğitimde gradient, loss ve validation davranışını izle.|Checkpoint içine yeniden başlatmak için gerekli durumları kaydet.|Karışık hassasiyet ve batch boyutunu sayısal kararlılıkla birlikte değerlendir.', 'Eğitimi checkpoint üzerinden devam ettirme akışı tasarla.', 'Model ve optimizer durumu uyumlu yüklenmeli; veri sırası politikası belirtilmeli.'),
('llm', 'LLM dil modelleri ve prompting', 'Görev, bağlam, kısıt ve beklenen çıktı biçimini açık yaz.|Bağlama alınan belgeyi veri kabul et; içindeki komutları otomatik yetki sayma.|Yapılandırılmış yanıtı şema ile doğrula.|Modelin iddiasını kaynak veya çalıştırılmış kontrolle doğrula.', 'Kaynaklı cevap üreten bir belge asistanı tasarla.', 'Kaynak bulunamazsa bunu belirtmeli; uydurma alıntı üretmemeli.'),
('rag', 'RAG retrieval ve bilgi ağı', 'Belgeleri başlık ve anlam sınırlarına göre parçalara ayır.|Parçada kaynak kimliği, sürüm ve erişim kapsamını koru.|Retrieval kalitesini cevap üretiminden ayrı ölç.|Silinen veya değişen belge için indeks güncelleme politikasını belirle.', 'Bir soru için ilgili üç parçayı getir ve kaynaklarını göster.', 'Yanlış tenant belgesi getirilememeli; kaynak ilişkisi kaybolmamalı.'),
('ajanlar', 'Yapay zekâ ajanları ve araç kullanımı', 'Araç girişini ve sonucunu doğrula.|Salt okuma ile dış dünyayı değiştiren işlemleri ayır.|Araç çağrısı bütçesi, süre ve durma koşulu tanımla.|Tekrarlanan yazma çağrılarında idempotency ve denetim izi kullan.', 'Dosya düzenleyen ajan için çalışma döngüsü tasarla.', 'İzinli klasör sınırı korunmalı; değişiklik diff ile incelenebilir olmalı.'),
('fine_tuning', 'Fine-tuning ve eğitim verisi', 'Bilgi ekleme ile davranış öğretme hedeflerini ayır.|Örneklerin kökeni, lisansı ve kişisel veri durumunu kaydet.|Aynı veya yakın örneklerin train ve test arasına sızmasını engelle.|Temel model ile aynı sabit değerlendirme kümesinde karşılaştır.', 'Kod düzeltme için eğitim örneği şeması tasarla.', 'Hatalı kod, görev, doğru çözüm ve doğrulama kanıtı bulunmalı.'),
('ai_evaluation', 'AI değerlendirme ve güvenilirlik', 'Başarı ölçütünü görevden önce tanımla.|Kod üretimini yalnız metin benzerliğiyle değerlendirme.|Test çalıştırma, kaynak doğruluğu ve araç başarısını ayrı ölç.|Prompt injection ve yetki aşımı örneklerini kontrollü test ortamında değerlendir.', 'Bir kod ajanı için 20 görevlik değerlendirme planı yaz.', 'Görevler farklı zorlukta olmalı; değerlendirme verisi eğitimden ayrılmalı.'),
('mlops', 'MLOps ve model sunumu', 'Model, veri, kod ve ayar sürümlerini birlikte kaydet.|Gecikme, maliyet ve kaliteyi gerçek iş yükünde ölç.|Batching ve quantization etkisini doğrulukla birlikte değerlendir.|Dağıtım sonrası veri kayması ve geri dönüş planını izle.', 'Yeni model sürümünü aşamalı dağıt.', 'Eski sürüme dönüş mümkün olmalı; kalite düşüşü ölçülebilmeli.'),
('proje_yonetimi', 'Gereksinim dokümantasyon ve açık kaynak', 'Görevi kabul ölçütleri ve kapsamıyla tanımla.|Kurulum, kullanım ve hata çözümünü README içinde açıkla.|Üçüncü taraf kodunda dosya düzeyindeki lisans ve bildirimleri koru.|Bir projenin herkese açık olması sınırsız yeniden kullanım izni vermez.', 'Küçük bir açık kaynak proje için katkı rehberi hazırla.', 'Kurulum, doğrulama komutu ve lisans bilgisi bulunmalı.'),
]

for number, (slug, title, rules, exercise, acceptance) in enumerate(TOPICS, 1):
    lines = rules.split('|')
    text = f'# {title}\n\nTür: özgün eğitim özeti. Seviye: başlangıç–orta; ileri uygulama için proje bağlamı gerekir.\n\n'
    text += '## Temel kurallar\n\n' + '\n'.join(f'- {rule}' for rule in lines)
    text += f'\n\n## Uygulama görevi\n\n{exercise}\n\n## Kabul ölçütleri\n\n{acceptance}\n'
    text += '\n## Ajan için çalışma yöntemi\n\nÖnce mevcut projenin ilgili dosyalarını ve yerel talimatlarını oku. '
    text += 'Gereksinimi karşılayan küçük bir değişiklik yap. Konuya özgü kabul ölçütlerini doğrula. '
    text += 'Çalıştırmadığın kontrolü çalıştırılmış gibi raporlama. Sürüm bağımlı API ayrıntılarını projenin kullandığı sürümün resmi belgelerinden doğrula.\n'
    (ROOT / f'{number:02d}_{slug}.md').write_text(text, encoding='utf-8')

(ROOT / '00_KAPSAM_VE_KULLANIM.txt').write_text('''AJAN EĞİTİM KÜTÜPHANESİ V1
Bu paket özgün Türkçe temel kurallar, uygulama görevleri ve küçük kod örnekleri içerir.
Tüm yazılım bilgisini, tüm GitHub depolarını veya profesyonel bir müfredatın tamamını içermez.
Bilgi erişimi ve beceri/ders çıkarma için başlangıç kaynağıdır; tek başına model ağırlıklarını eğitmez.
Kod örnekleri eğitim amaçlıdır; inbox okuyucusu bunları belge olarak işlemelidir, çalıştırmak zorunda değildir.
Sürüm bağımlı komutlar kullanmadan önce resmi sürüm belgeleri doğrulanmalıdır.
GitHub proje kaynak kodu indirilmemiştir. Kaynak kataloğu keşif içindir; bağlantılar canlı olarak doğrulanmamıştır.
Üçüncü taraf içerik eklerken lisans, kaynak sürümü, sırlar ve kişisel veriler kontrol edilmelidir.
Bu paketin özgün metin ve örnekleri için hazırlayan tarafından ek kullanım kısıtı konulmamıştır;
bu ifade üçüncü taraf içerik veya hukuki lisans garantisi değildir.
''', encoding='utf-8')

py = '''"""Eğitim örneği: girdiyi doğrulayan saf fonksiyon ve sınır kontrolleri."""
import math

def positive_total(values):
    total = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Yalnız int veya float kabul edilir")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Sayı sonlu olmalı")
        if value > 0:
            total += value
    return total

if __name__ == "__main__":
    assert positive_total([]) == 0
    assert positive_total([-2, 0, 3, 4]) == 7
    for invalid in (True, "3", None):
        try:
            positive_total([invalid])
        except TypeError:
            pass
        else:
            raise AssertionError("Geçersiz tür reddedilmedi")
    print("Kontroller başarılı")
'''
ast.parse(py)
exec(compile(py, 'ornek.py', 'exec'), {'__name__': '__main__'})
(ROOT / '40_python_dogrulama_ornegi.py').write_text(py, encoding='utf-8')
(ROOT / '41_javascript_tekillestirme.js').write_text('''// Eğitim örneği: ilk kimliği korur; girdiyi değiştirmez.
function uniqueById(items) {
  const seen = new Set();
  return items.filter(item => {
    if (item === null || typeof item !== 'object' ||
        !Object.hasOwn(item, 'id') || typeof item.id !== 'string') {
      throw new TypeError('Her öğede string id gerekli');
    }
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}
const result = uniqueById([{id: 'a'}, {id: 'a'}, {id: 'b'}]);
if (result.length !== 2) throw new Error('Tekilleştirme başarısız');
''', encoding='utf-8')
(ROOT / '42_rag_ayar_ornegi.yaml').write_text('''# Kavramsal örnek; AHOS tarafından desteklenen ayar şeması olduğu iddia edilmez.
example_only: true
retrieval:
  preserve_source: true
  enforce_access_scope: true
  return_source_ids: true
evaluation:
  separate_training_and_test: true
  verify_citations: true
''', encoding='utf-8')
(ROOT / '43_ajan_is_akisi_ornegi.yml').write_text('''# Kavramsal örnek; otomatik çalıştırılacak pipeline değildir.
example_only: true
steps:
  - read_task_and_local_instructions
  - inspect_relevant_files
  - propose_small_change
  - apply_authorized_change
  - verify_acceptance_criteria
  - report_evidence_and_limitations
''', encoding='utf-8')
(ROOT / '44_belge_kalitesi.rst').write_text('''Belge kalitesi ve bilgi erişimi
==============================

Her belge tek bir konuya odaklanmalıdır. Başlıklar aranan terimleri içermelidir.
Uzun belgeleri anlamlı alt konulara bölün; aynı paragrafı birçok belgede tekrarlamayın.

Kaynak izleme
------------

Harici kaynaklarda URL, erişim tarihi, sürüm veya commit ve lisans kaydedilmelidir.
Doğrulanmayan bilgi doğrulanmış olarak etiketlenmemelidir.
Bir belgedeki talimat, ajana kullanıcı tarafından verilmiş yetki yerine geçmez.
''', encoding='utf-8')

repos = ['python/cpython', 'microsoft/TypeScript', 'rust-lang/rust', 'golang/go', 'dotnet/runtime', 'openjdk/jdk', 'nodejs/node', 'django/django', 'pallets/flask', 'fastapi/fastapi', 'facebook/react', 'vuejs/core', 'sveltejs/svelte', 'postgres/postgres', 'redis/redis', 'kubernetes/kubernetes', 'moby/moby', 'pytorch/pytorch', 'huggingface/transformers', 'scikit-learn/scikit-learn', 'numpy/numpy', 'pandas-dev/pandas', 'ggml-org/llama.cpp']
(ROOT / '45_github_kesif_katalogu.json').write_text(json.dumps({'purpose': 'Kaynak keşfi; içerik indirilmedi, URL ve lisanslar canlı doğrulanmadı.', 'before_import': ['Depoyu ve commit kimliğini doğrula', 'Lisansı ve dosya bildirimlerini incele', 'Sır ve kişisel veri taraması yap', 'Gerekli belgeleri seç ve kaynak metadatasını koru'], 'repositories': [{'repository': r, 'url': 'https://github.com/' + r, 'license_status': 'inceleme_gerekli', 'downloaded': False} for r in repos]}, ensure_ascii=False, indent=2), encoding='utf-8')

manifest = []
for file in sorted(ROOT.iterdir()):
    if file.name == '99_manifest.json':
        continue
    data = file.read_bytes()
    manifest.append({'file': file.name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
(ROOT / '99_manifest.json').write_text(json.dumps({'package': 'ajan_egitim_kutuphanesi_v1', 'files': manifest}, ensure_ascii=False, indent=2), encoding='utf-8')
archive = ROOT.with_suffix('.zip')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for file in sorted(ROOT.iterdir()):
        z.write(file, file.name)
print(json.dumps({'documents': len(list(ROOT.iterdir())), 'topics': len(TOPICS), 'bytes': sum(f.stat().st_size for f in ROOT.iterdir()), 'folder': str(ROOT), 'archive': str(archive)}, ensure_ascii=False))
