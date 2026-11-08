# P7 portre hattı — kullanım ve gerçek sınırlar

Bu hat model çağırmaz, ücretli iş başlatmaz, model indirmez. Kaynak talimatlar
`studio/canon/p7-owner-constraints.json`; yaş/ailenin kanonik kaynağı
`cast-manifest.json` ve `family-relations.json` dosyalarıdır.
Yüz/geometri/paletin kullanıcı tarafından belirtilmemiş ayrıntıları sanat yönetimi
ÖNERİSİDİR; tasarım talimatı görsel onayı değildir. `story-timeline.json` Esma'nın
5 aylık hamileliğini yalnız s01e001 dönemi için taşır.

## Çalışan giriş

Her karakterin `portrait-design.json` dosyasındaki prompt, negative_prompt,
seed ve version ile yalnız bir ana aday üretilir. Üretim modeli/sürümü/ayarları da
kaydedilmelidir; seed tek başına aynı görüntüyü garanti etmez.

```powershell
python tools/p7_portraits.py import --character esma --image aday.png --source yerel-uretici --model MODEL-SURUMU --prompt "GERCEK KULLANILAN ISTEM" --seed 7004 --license-status UNVERIFIED
```

PNG/JPEG özgün baytları saklanır; SHA-256, normalize piksel hash'i, model, kaynak,
istem, seed, tasarım sürümü/hash'i ve DNA hash'i kayda girer. Eksik bilgiler
UNKNOWN/UNVERIFIED kalır. Tüm adaylar CANDIDATE_PENDING_REVIEW kalır.
Eski `candidate_import.py` P7 tasarımı bulunan karakterlerde bu hatta yönlenir;
eski çağrı model/istem vermiyorsa bunları UNKNOWN olarak kaydeder.

## İnsan QA

Aynı dosya veya aynı pikseller, ikizler dahil iki kimliğe kaydedilemez. dHash
mesafesi <=8 yalnız inceleme bayrağıdır; yüz tanıma değildir. Farklı arka plan,
poz ve kırpma yanlış negatif/pozitif üretebilir. Her aday, bayrak olmasa bile,
yaş, yüz, saç, göz, kıyafet, işaretler ve diğer 15 kimlikle insan tarafından
karşılaştırılmalıdır. Aile ilişkileri yalnız family-relations'tan alınır.

`studio/production/approvals.json` mevcut approvals dizisine, açık kullanıcı
onayından SONRA, character_id, status=APPROVED, sha256, design_sha256,
approved_by, approved_at, canon_review_passed=true, similarity_review_passed=true
alanlarını taşıyan kayıt eklenir. Bu işlem otomatik yapılmaz. Ticari lisans
ayrıca doğrulanıp aday kaydında VERIFIED_COMMERCIAL olmalıdır. Onay kaydı her
karakter için tek olmalı; dosya veya tasarım/DNA değişirse çıktı kapısı kapanır.
Bu yerel onay kayıtları güvenilir operatör alanıdır; kriptografik imza veya
çok kullanıcılı yetkilendirme sistemi oldukları iddia edilmez.

```powershell
python tools/identity_lock.py --verify
python tools/p7_portraits.py poster --output aile-posteri.png
python tools/p7_portraits.py export --output onayli-openmontage-paketi
```

Poster 16 ayrı onaylı portreyi birleştirir; yeni yüz üretmez. Export ayrı
public/portraits ve props.json oluşturur. Kurulu OpenMontage remotion-composer
Explainer'ın image/source/in_seconds/out_seconds biçimine uyar. Paketin public
alanı renderer'ın --public-dir seçeneğine, props.json --props seçeneğine verilir.
Paylaşılan kurulum dosyaları değiştirilmez. Bu portre galerisi animasyon veya
3D model değildir. OpenMontage/Remotion'ın kendi lisans şartları ayrıca geçerlidir.

Eski build_studio_cast tekrar çalıştırılarak P7 kanonu ezilemez; hedefli
düzeltme ve identity_lock --change kullanılmalıdır. Future-cast dosyası mevcut
16 kişiden ayrıdır. Yeni portre tasarımları mevcut bileşik kimlik hash'ine dahildir.

## Gerçek engel

Bu oturumda ComfyUI 127.0.0.1:8188 bağlantıyı reddetti; Blender bulunamadı.
Ücretsiz çalışacağı doğrulanmış başka bir üretici kullanılmadı. Gerçek portre
üretilmedi; onay yok. Testlerdeki renkli geometrik görseller yalnız tmp_path
fixtures'ıdır, kullanıcı karakteri değildir. Onaylı gerçek portre gelmeden
nihai poster, oyuncak referansı, 3D rig ve karakter animasyonu tamamlanmış sayılmaz.
