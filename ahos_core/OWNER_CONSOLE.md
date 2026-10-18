# AHOS Sahip Konsolu (tek komut → departman + iş)

Bu modül, holdingin başındaki kişinin **tek satır yazarak** şirket/departman
kurdurmasını ve iş yaptırmasını sağlar. Model çağrısı yoktur, token maliyeti
yoktur; her adım deterministik ve test edilebilirdir.

```
"çizgi film departmanı kur"   -> departman + ekip + ajanlar + kuruluş görevi
"yazılım şirketi kur"         -> yazılım şirketi org şeması
"landing page yap"            -> uygun departmana yönlendirme + görev çalıştırma
"Mipiluna projesini oyun departmanına bağla" -> proje + denetim + entegrasyon planı
"durum"                       -> departman özeti
```

## Holding hiyerarşisi

```
Sahip (panel / CLI)
  └─ CEO (holding departmanı, `ceo-01`)
       └─ Departman müdürleri (`*-manager`)
            └─ Ekip liderleri ve uzmanlar
```

- `holding` departmanı her kurulumda otomatik eklenir ve CEO'yu taşır.
- `guvenlik` departmanı (Güvenlik ve Kaynak Koruma) 5 ajanlıdır; depo/GitHub
  risklerini sürekli tarar. `github kontrolü yap` komutu bu departmana gider.
- CEO yönlendirmesi deterministiktir: önce engellenen görevler, sonra 24 saattir
  ilerlemeyen bağlı projeler, sonra en az görev alan departman.

## Komutlar

```
"github kontrolü yap"            -> güvenlik taraması + aksiyon planı
"durum"                          -> departman özeti
python -m ahos.holding_office    -> CEO özeti
python -m ahos.holding_office --run  -> sıradaki yönlendirmeyi çalıştır
python -m ahos.github_guardian --repo <yol> --json
python -m ahos.growth_loop --ceo --interval 60
```

## Gerçek iş ve kanıt

Bir departmana proje bağlıysa (`projects.json`), o departmanın görevleri artık
`runtime/projects/<id>/` içinde **gerçekten dosya değiştirir**:

- **Analiz adımı** → `ASSET_REPORT.md` (HTML/CSS varlık referansları + çevrimdışı önbellek denetimi).
- **Üretim adımı** → `www/index.html` hijyeni (lang/charset/viewport/alt), eksik
  önbellek kayıtlarının eklenmesi ve `tools/check_offline.py` kalite kapısı;
  ardından `CHANGES.md` + `CHANGES.diff` (gerçek unified diff).
- **Kalite adımı** → `VERIFY.md`.

## Model yürütücüsü (opsiyonel)

`AHOS_EXECUTOR=model` + `AHOS_LLM_BASE_URL`, `AHOS_LLM_API_KEY`, `AHOS_LLM_MODEL`
verildiğinde proje departmanları modeli kullanır. Güvenlik zinciri:

1. **Yama modu**: `find`/`replace`; hedef tam 1 kez geçmezse uygulanmaz.
2. **Sahiplik**: proje kökü dışına yazma reddedilir; yalnız metin dosyaları.
3. **Onay kapısı**: 2'den fazla dosya, `risk>=medium`, dosyayı %40'tan fazla
   küçültme veya kodu yorum satırına alma → `APPROVAL_REQUIRED.md`, uygulanmaz.
4. **Maliyet tavanı**: `AHOS_LLM_MAX_USD` (varsayılan $0.05) + `model-spend.jsonl`.
5. **Doğrulama**: `node --check` → başsız tarayıcıda sayfa yükleme/DOM →
   `tools/check_offline.py`.
6. **Geri alma**: doğrulama düşerse değişiklikler otomatik geri alınır.

Değişiklikler panelde **Çıktılar → Değişiklik kanıtı (diff)** bağlantısıyla
okunur; dosya sistemi üzerinde de `runtime/artifacts/<görev>_produce/CHANGES.diff`
olarak durur.

## Proje bağlama

`attach_project` akışı:

1. Komuttaki proje adı (`Mipiluna`) ve hedef departman yönlendirmeden çıkarılır.
2. `AHOS_PROJECT_ROOTS` (varsayılan: `Downloads`, `Desktop`, `Documents`, `OneDrive`)
   içinde **en yeni sürüm** aranır (`Mipiluna-22-...` gibi) ve
   `ahos_core/runtime/projects/<id>/` altına açılır/kopyalanır.
3. Otomatik envanter çıkarılır: dosya sayısı, boyut, klasörler, web kökü
   (`www`), npm betikleri, giriş dosyaları, TODO sayısı.
4. `PROJECT_AUDIT.md` ve `INTEGRATION_PLAN.md` yazılır; plan 5 aşama,
   ekip eşlemesi, riskler, kabul kriterleri ve ilk 7 gün tablosunu içerir.
5. Onboarding görevi (denetim → plan → kalite) kuyruğa yazılıp çalıştırılır.

## Akış

```
sahip komutu (panel / CLI)
  -> parse_owner_command()        niyet: create_department | task | status
  -> DepartmentBook               kalıcı departman defteri (JSON)
  -> synthesize_department()      domain şablonu -> doğrulanmış org şeması
  -> DepartmentRoutingEngine      mevcut departmanlara puanlama
  -> PersistentMissionQueue       company-service.db kuyruğuna yazılır
  -> MultiWorkerMissionOrchestrator  yönetici -> işçi -> QA
  -> queue.complete() / queue.block()  sonuç panelde görünür
  -> artifacts/                   her adım için deliverable.md
```

Her departman aynı zamanda mevcut `BusinessUnitBlueprint` modeline çevrilir
(`DepartmentSpec.to_business_unit_blueprint()`), yani hiyerarşi kuralları tek bir
yerde (`business_units.validate`) kalır.

Eşleşen departman yoksa komut **önce departmanı kurar**, sonra işi çalıştırır.
Zaten var olan bir seed departmanı (ör. `software`) hedeflenirse departman
silinmez; yerinde büyütülür (2 ajan → 13 ajan).

## Dosyalar

| Dosya | Görev |
| --- | --- |
| `ahos/departments.py` | `DepartmentSpec`, `WorkerSpec`, `CapabilitySpec`, `DepartmentBook` (JSON kalıcı) |
| `ahos/org_synthesis.py` | TR/EN domain şablonları → org şeması üretimi |
| `ahos/owner_console.py` | niyet ayrıştırma, yönlendirme, görev yürütme, kuyruk kaydı, artefakt üretimi |
| `ahos/owner_cli.py` | `python -m ahos.owner_cli "komut"` |
| `ahos/office_view.py` | canlı ofis görünümü: departman odaları, ajan durumları, son hareketler |
| `ahos/projects.py` | gerçek proje klasörlerini departmana bağlar, denetim + entegrasyon planı üretir |
| `ahos/holding_office.py` | CEO katmanı: departman müdürlerini yönetir, öncelik/yönlendirme üretir |
| `ahos/github_guardian.py` | offline depo güvenlik taraması: sır, .env, bağımlılık, CI, yedek |
| `ahos/code_work.py` | bağlı projede **gerçek dosya değiştirir**; varlık/önbellek denetimi, hijyen düzeltmesi, kalite kapısı ve diff kanıtı |
| `ahos/llm_executor.py` | model tabanlı yürütücü: yama modu, maliyet tavanı, onay kapısı, doğrulama, geri alma |
| `ahos/browser_check.py` | başsız tarayıcıda gerçek sayfa yükleme + DOM doğrulaması + ekran görüntüsü |
| `ahos/outputs.py` | çıktı indeksi + markdown görüntüleyici (`/outputs`) |
| `ahos/growth_loop.py` | sürekli gelişim döngüsü: her turda en az iş almış departmana görev |
| `ahos/control_center.py` | panel: komut kutusu, departmanlar, ofis bağlantısı, döngü düğmeleri |

## Çalıştırma

Panel (varsayılan `http://127.0.0.1:8765`):

```powershell
.\control_plane_v2\Start-AHOS-Owner-Console.ps1
```

CLI:

```powershell
$env:PYTHONPATH = "$PWD\ahos_core"
python -m ahos.owner_cli --runtime-dir "$PWD\ahos_core\runtime" "çizgi film departmanı kur"
python -m ahos.growth_loop --runtime-dir "$PWD\ahos_core\runtime" --interval 60 --ticks 3
```

Ofis görünümü panelden **"Ofis görünümü →"** bağlantısıyla veya doğrudan
`http://127.0.0.1:8765/office` adresinden açılır; 3 saniyede bir yenilenir.
Ajanların durumu (çalışıyor / bekliyor / engellendi) gerçek görev geçmişinden
(`company-service.db` içindeki `result_json`) gelir.

Testler:

```powershell
cd ahos_core; python -m pytest tests -q
```

## Durum / sınırlar

- Durum dosyaları: `ahos_core/runtime/departments.json`,
  `ahos_core/runtime/owner-commands.jsonl`, `ahos_core/runtime/artifacts/`.
- Varsayılan yürütücü **offline**'dır: her adım için markdown teslim üretir
  (`make_artifact_executor`). Gerçek üretim için `OwnerConsole(...,
  executors={"*": OpenHandsWorkerAdapter(...)})` ile OpenHands/miniverse
  yürütücüsü takılır; konsolun geri kalanı değişmez.
- Gelişim döngüsü panelde **"Gelişim Döngüsü Başlat"** ile 30 sn aralıkla
  çalışır; "Döngüyü Durdur" `growth-loop.stop` dosyasını yazar ve döngü en
  geç 0.25 sn içinde durur. CLI'da `--interval`, `--per-tick`, `--ticks`,
  `--department` seçenekleri vardır.
- Panel `127.0.0.1`'e bağlıdır ve kimlik doğrulaması yoktur; yalnız yerel kullanım
  içindir.


## 17 Ekim 2026 — doğruluk ve kabul kapıları

- Projeye bağlı üretim yürütücüsü yoksa `produce` adımı engellenir. Markdown
  metadata kaydı ürün teslimi veya çalışan stüdyo anlamına gelmez.
- Web denetimi eksik dosyaları raporlayabilir; üretim ve son denetim ise eksik
  varlık varken başarılı olmaz.
- Modelin önerdiği `verification` komutu host üzerinde yürütülmez. Önceden
  güvenilen `verify_command` veya proje kalite kapısı gerekir. Yalnız sözdizimi
  kontrolü ve sayfanın açılması, kabul komutu yokken yeterli değildir.
- Bu kapılar, proje içindeki kalite kapısının güvenilir olduğunu tek başına
  kanıtlamaz. `local_pass_qa` halen başlangıç denetimidir; bağımsız semantik
  ürün doğrulaması olarak sunulmamalıdır.
- İlgili 96 regresyon ve iki davranış kabul testi kurulu kaynaklarla geçti.
  Model çağrısı yapılmadı; model kalitesi bu testlerin kapsamında değildir.
- Kaynak güncellemesi çalışan Python süreçlerini kendiliğinden yenilemez.
  Bu çalışmada servisler durdurulmadı, kuyruklar ve kullanıcı projeleri korunmuştur.


## Bağımsız statik web QA — 17 Ekim 2026

Bağlı web projelerinin varsayılan QA yolu artık `project_qa.make_project_qa` kullanır.
İşçinin başarı özetinden bağımsız olarak varlıkları, kanıt dosyalarını ve kaynak
izlerini kontrol eder. Üretici QA atamasından hariç tutulur; son inceleme için
`static-web-verifier` kimliği gerçek deterministik QA callable ile kaydedilir.
Bu kimlik kalıcı departman kadrosuna eklenmez, yürütme süresinde bağlanır.
Tarama sınırları 20 000 girdi, 4 096 dosya ve 256 MiB; hash okuması 64 KiB parçalar kullanır; model çağrısı yoktur.
Bu statik denetim uygulama davranışını veya medya/karakter uygunluğunu kanıtlamaz.
Özel olarak enjekte edilen QA ve yürütücüler otomatik değiştirilmez.
Departman defteri kaydı benzersiz geçici dosya kullanır; PermissionError için
en fazla beş yenileme denemesi yapar. Kalıcı hatada eski kayıt korunur.
128 ilgili regresyon/kabul testi kurulu kaynaklarla geçti. Servisler yeniden
başlatılmadı; çalışan süreçlerin yeni kaynakları yüklemesi ayrıca doğrulanmalıdır.


## Kalıcı gelişim sınırı ve ana panel — 18 Ekim 2026

Gelişim döngüsü growth-budget.sqlite3 ile kayan 24 saatte sekiz otomatik görevle
sınırlıdır. Aynı departman/hedef bir saat bekler; başarısızlık veya çökme
rezervasyonu sıfırlamaz. 4096 geçmiş kayıtta yönetici incelemesi için durur.
Manuel görevler bu otomatik görev bütçesinden bağımsızdır. Döngü kurulumla
kendiliğinden başlatılmaz.

Departman API ve paneli artık kayıt durumunu gerçek yürütme kapsamından ayırır.
Foundry 3100/holding sayfası 8765 sahibin konsolunu salt okunur bağlar; iki
kuyruk ayrı kalır. Üretim yürütücüsü olmayan departmanlar açıkça belirtilir.
141 AHOS testi ve Foundry tarafında 20 köprü/arayüz/proxy testi geçti.
