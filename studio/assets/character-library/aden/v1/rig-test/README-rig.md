# Aden — technical rig test (v1)

Durum: **RIG_TEST_COMPLETE** · kimlik: **PENDING_IDENTITY_REVIEW** (bu bir teknik rig testidir, kimlik onayı değildir)

Kaynak model: `../aden-character-v1.blend` (salt okunur kullanıldı, SHA-256 değişmedi)
Blender: 4.5.16 LTS · Render: CPU Workbench (GPU/ücretli eklenti yok)

## Üretilen dosyalar

| Dosya | Açıklama |
|---|---|
| `aden-character-rigged.blend` | 24 kemikli armature + skinning + 5 shape key + 3 aksiyon |
| `aden-character-rigged.glb` | glTF 2.0, 1 skin (24 joint), 3 animasyon, 5 morph target |
| `rig-manifest.json` | kemik listesi, ağırlık stratejisi, aksiyonlar, SHA-256 |
| `validation.json` | yeniden açma doğrulaması, hareket/kopma/ayak ölçümleri |
| `previews/*.png, *.mp4` | 00-rig-test-pose + her aksiyon için 3 kare + MP4 |
| `previews/qa/*.png` | blink/gülümseme/omuz/yürüyüş yakın plan QA kareleri |
| `backups/` | önceki denemeler ve kaynak .blend yedeği (silinmedi) |
| `tools/*.py` | inspect / build / validate scriptleri |
| `logs/*.log` | her adımın tam Blender çıktısı |

## İskelet (24 kemik)

root, hips, spine, neck, head, jaw · shoulder/upper_arm/forearm/hand · thigh/shin/foot · eye/eyelid (L/R)

`L = -X`, `R = +X` (kaynak objelerin adlandırmasıyla aynı; karakter -Y yönüne bakıyor).
`root` deform etmez; `walk_cycle` ileri hareketi root'tan taşır.

## Ağırlıklandırma

- **47 obje tek kemiğe %100** (saç, göz, kapak, diş, ayakkabı, eldiven, kulak, benler).
  `Sleeve_L/R` otomatik ağırlıkta yırtıldığı için `upper_arm.*`'a sabitlendi.
- **12 obje otomatik ağırlık** (bone heat): torso, boyun, şort, kol, bacak, kalça.
  Otomatik ağırlığın ulaşamadığı **36 vertex** en yakın kemiğe elle atandı; yetim vertex: **0**.
- **Ağız**: dikey gradyan ile üst dudak `head`, alt dudak `jaw`.

## Shape key (5)

`blink.L`, `blink.R` (göz kapağı mesh'lerinde) · `smile`, `mouth_open` (`Mouth`) · `brow_up` (iki kaşta).
Blender shape key'leri mesh başına olduğu için anahtarlar geometriyi taşıyan mesh'lere dağıtıldı.

## Aksiyonlar

| Aksiyon | Kare | Açıklama |
|---|---|---|
| `idle_wave` | 1–48 | Sağ kol kalkar, el sallar, baş hafifçe takip eder |
| `blink_smile` | 1–24 | İki göz kırpar, güler, çene hafif açılır (shape key + kemik birlikte) |
| `walk_cycle` | 1–32 | 2-bone analitik bacak IK, kollar karşılıklı sallanır, 0.24 m root motion |

`walk_cycle` **root motion** içerir (kare başına sabit hız, -Y); planted ayak dünya uzayında sabit
kaldığı için ayak kayması ölçümü **0.0 m**. Yerinde (in-place) döngü gerekiyorsa `root` kanalının
location eğrileri silinmelidir.

## Ölçülen kalite

- Yeniden açma: armature + 24 kemik + 3 aksiyon + 5 shape key yüklendi (`reopen_ok: true`)
- En kötü kenar uzama oranı: **x1.28** (kopma eşiği x2.5) — yırtılma yok
- Ayak kayması (walk): **0.0 m** · zemine gömülme: yok
- blink değeri f8'de **1.0**; ağız genişliği 0.1239 → 0.1606 m (gülümseme)
- GLB: 3 animasyon, 1 skin/24 joint, 5 morph target, 60 mesh

## Bilinen sınırlar

- Modelde gerçek göz kapağı geometrisi yok; blink, kapak mesh'ini öne/ayağıya uzatarak yapılıyor —
  kapalı gözler iri ve hafif dışa bombeli görünüyor (stilize kabul).
- Göz/kaş/ağız ayrı mesh'ler; shape key'ler tek objede birleşmiyor (glTF'te 5 morph target).
- Eller/bacaklar düşük poligonlu silindirler: dirsek/diz bükülmesi sınırlı ölçüde yuvarlak.
- `Star_Clip` objesinde 1.25 ölçek var (kaynak modelden); rig'i etkilemiyor, manifest'te uyarı olarak duruyor.
- Kimlik onayı yok; yüz benzerliği bu testin kapsamı dışında.

## Yeniden üretim

```powershell
& "C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe" -b `
  "..\aden-character-v1.blend" --factory-startup -noaudio `
  --python tools\build_rig.py -- --out . --render full

& "C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe" -b `
  "aden-character-rigged.blend" --factory-startup -noaudio `
  --python tools\validate_rig.py -- --out . --blend "aden-character-rigged.blend" `
  --glb "aden-character-rigged.glb" --qa 1
```
