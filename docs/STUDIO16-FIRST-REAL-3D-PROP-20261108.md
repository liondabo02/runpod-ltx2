# AHOS Studio-16 — ilk doğrulanmış 3D aksesuar (2026-11-08)

**Durum:** `PROPOSED_3D_PROP_QA` / **sahip onayı yok** / maliyet **0 EUR**.

## Gerçek çalışan araç
Kahta bilgisayarındaki resmi, ücretsiz **Blender 5.2.3 LTS Windows x64 portable** sürümü:
`C:\actions-runner\_work\AHOS_TOOLS\Blender52\blender-5.2.3-windows-x64\blender.exe`.

Yayıncı SHA-256 kontrol dosyasıyla karşılaştırılarak arşiv doğrulandı:
`723f08a4401502561eb763cdeacf8745b31e5f3f154d287d3830d97cf75dc2fb`.

Blender `--background --factory-startup --version` komutuyla açıldı (exit 0).
Mevcut sistem programları ve servisleri değiştirilmedi.

## Gerçek üretilen ve kanıtlanan varlık
Asset ID: `kite-six-strip-tail`.

Özel medya konumu:
`control_plane_v2/runtime/private/animation-studio/assets/kite-six-strip-proof-20261108/`

- `kite-six-strip-PROPOSED.blend`: Blender'da **yeniden açılarak** doğrulandı; 9 gerçek mesh nesnesi.
- `kite-six-strip-PROPOSED.glb`: glTF 2.0, 9 düğüm/mesh ve altı ayrı renkli şerit.
- `kite-six-strip-preview.png`: 512×512, CPU Cycles ile gerçek modelden render.
- `prop-proof.json`: SHA-256 ve boyutlar, onaysız statü.
- Kod: `tools/build_kite_prop_blender.py`
- Standart Python QA: `tools/validate_kite_prop.py`.
- Takip indeksi: `studio/production/asset-proofs/kite-six-strip-20261108.json`.

Şeritler **kırmızı, sarı, mavi, yeşil, turuncu, mor**; ayrı mesh.
S01E001 kanonundaki iniş alanları obje metadatasına işlendi: ilk üç piknik
örtüsü; yeşil/turuncu çimen; mor alçak çalı.

## Gerçek QA
Blender'dan alınan sahne baştan açıldı. Ortam:
`Blender 5.2.3 LTS`, Windows, **CPU**, ücretsiz.

`AHOS_KITE_PROP_SUCCESS`: `mesh_count=9`, `strip_count=6`.
`python tools/validate_kite_prop.py --output-dir <private-asset-dir>`:
`ok=true`, `issues=[]`, `mesh_nodes=9`, `owner_approved=false`.

İlk koşuda Blender'ın sıkıştırılmış `.blend` biçimi eski ham dosya başlığı
kontrolünden geçmedi. Dosyaların üzerine yazılmadı. Kod gerçek Blender yeniden
açma kontrolüyle düzeltildi; eski dosyalar `--verify-existing` ile yeniden
değerlendirilip manifest başarıyla üretildi.

## Sınırlar — bunlar tamamlanmadı
- Uçurtma **teknik prototip**, henüz sanat yönetmeni/sahip onayından geçmedi.
- Boyutlar, renk paleti ve ışık nihai karakter/episode görsel diliyle onaylanmadı.
- Bu bir prop; **16 karakterin 3D mesh ve rig'i hâlâ yok**.
- Gerçek 30 saniyelik animasyon veya 480 saniyelik bölüm henüz üretilmedi.
- Özel `.blend/.glb/.png` dosyaları GitHub'a commit edilmedi; yalnız kod, test ve
  güvenli QA metadata'sı commit için hazırlandı.

## Tekrar üretim
Yeni ve boş bir özel çıktı dizini ile:

```powershell
blender.exe --background --factory-startup --python tools/build_kite_prop_blender.py -- --output-dir <NEW_PRIVATE_DIR>
python tools/validate_kite_prop.py --output-dir <NEW_PRIVATE_DIR>
```

Mevcut çıktılar üzerine yazma yasak. Kısmi üretim kontrolü için:
`--verify-existing` kullanılabilir, ancak mevcut `prop-proof.json` üzerine
tekrar yazılmasına izin verilmez.

## Sonraki gerçek hedef
Aynı Blender ortamında önce basit **hareket edebilen gerçek rig/mesh kanıtı**,
sonra kanonik karakterin görsel onaylı modelleme süreci. Geçici model yüzü
sahibin onayı olmadan kesin karaktere dönüştürülmez.
