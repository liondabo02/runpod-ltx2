# Karakter birleştirme raporu — 16 karakter, tek kanon

Tarih: 2026-11-07 · Kapsam: eski Character Bible + ses kataloğu + yeni görsel kanon
Kural: mevcut veri **silinmedi**, yeni veritabanı **açılmadı**, özel veriler public
repoya **aktarılmadı**.

## 1. Doğrulanan kaynaklar

| Kaynak | Doğrulanan |
|---|---|
| `control_plane_v2/runtime/private/animation-studio/character-memory.db` | **16 karakter, 16 sürüm, 28 ilişki, 3 kanonik bilgi** |
| `character-seed.local.json` | 16 karakter, 28 ilişki, 3 kanonik bilgi (DB ile aynı) |
| `ahos_core/ahos/core_cast_voice_catalog.py` | 16 ses kimliği; cinsiyet/yaş/konuşma biçimi |
| `ahos_core/config/core-cast-voice-production-plan.json` | 16 karakter, cinsiyet + TR/EN metin |
| `audio/core-voices/` | **14 klasör × 2 dosya = 28 WAV** (Medine ve Ramin bebek: klasör yok) |
| `characters/aden.json`, `kaan.json` | yalnız **2** görsel kanon dosyası |

Birleşik katman: `ahos_core/ahos/character_canon.py` (salt okunur).
Çalıştırma: `python -m ahos.character_canon --summary` →
`16 karakter · 28 ilişki · 3 kanonik bilgi · 14 ses · 2 görsel · 0 kritik çelişki`.

## 2. Bulunan ve düzeltilen kimlik hatası

| Alan | Eski kanon | Yeni dosya (önce) | Şimdi |
|---|---|---|---|
| Aden cinsiyeti | **kız** (`CoreCastVoiceSpec: "girl"`, production plan `"gender": "girl"`) | `3-year-old boy` | **kız** |
| Aden yaşı | 3 | 3 | 3 |
| Kaan | 1, erkek | 1, erkek | 1, erkek |

Düzeltilen yerler:
- `characters/aden.json`: `gender: "female"`, `prompt_fragment` → girl, `her left cheek`,
  omuz hizasında dalgalı saç + sarı yıldız toka.
- `characters/scenes/park-kite-01.json`: `keyframe`, `image_to_video`,
  `keyframe_baby_focus` → "girl / big sister / her little brother".
- `docs/KARAKTER-KANONU.md`: Aden satırı kız olarak güncellendi.
- Regresyon testi: `tests/test_character_canon.py::test_scene_and_character_prompts_say_girl_not_boy`
  ve `test_aden_is_female_in_unified_canon`.

**Kanon boşluğu:** eski DB'de cinsiyet alanı yok; cinsiyet yalnız ses kataloğunda.
Bu yüzden birleşik katman cinsiyeti **ses kataloğundan** okur ve görsel promptla
çelişirse `gender_conflict` üretir (test edildi).

## 3. Take1 kararı

`park-kite-take1-*.mp4` **erkek Aden** promptuyla üretildi. Bu nedenle:
- **yeni kanonun geçerli referansı değildir**, arşivde "eski/yanlış kimlik" olarak kalır;
- yeni çekimler kız Aden kanonuyla yapılacaktır.

## 4. Ses varlıkları (silinmedi, yeniden üretilmedi)

`tools/audio_asset_audit.py` → 14 klasör, 28 dosya:

| Kontrol | Sonuç |
|---|---|
| Eksik dosya | 0 |
| Sessiz (≤ −50 dBFS) | 0 |
| Aşırı kısa (< 0,4 sn) | 0 |
| Örnekleme hızı uyumsuzluğu | 0 |
| Süre aykırısı | **1** (`fatos/tr.wav` ≈ 39,96 sn; medyan ≈ 6,1 sn) |

Süre aykırısı silinmedi; insan dinlemesi gerekir. **Yaşa uygunluk, karakterlerin
birbirinden ayrışması ve çoklu dilde kimlik** otomatik PASS edilmedi:
`NOT_EVALUATED` — dinleme kontrol listesi raporda.

Bebekler (Medine, Ramin): ses klasörü yok; cümle söyletilmemesi kanonda yazılı.

## 5. Hugging Face durumu (gizli bilgi yok)

```text
huggingface_hub.get_token() -> None   (token yok)
token path: C:\Users\esmak\.cache\huggingface\token  (dosya yok)
```

- Oturum açılmamış; `hf auth whoami` için token yok.
- ZeroGPU kotası ücretsiz kademede sınırlı; kota yoksa araç `blocked: zerogpu_quota`
  ile durur, sonsuz tekrar yapmaz.
- Ücretli çağrı/abonelik yapılmadı; token değeri loglanmadı.

## 6. Test kanıtı (ham)

```text
python -m pytest -q tests/test_character_canon.py tests/test_audio_audit.py
6 passed in 1.21s        (exit 0)

python -m ahos.character_canon --summary
{"characters":16,"relationships":28,"canon_facts":3,"with_visual_canon":2,
 "with_audio_en_tr":14,"gender_known":16,"conflicts":16,"errors":0}

python tools/audio_asset_audit.py
{"folders":14,"files":28,"issues":1,"characters_with_issues":1}
```

`conflicts:16` = 14 görsel kanon eksik (NOT_CREATED) + 2 bebek sesi yok; **kritik 0**.

## 7. Görsel karakter tasarımı durumu

| Karakter | JSON kanon | Model sheet (görsel) | Ses |
|---|---|---|---|
| Aden | var (kız) | **NOT_CREATED** | var (TR+EN) |
| Kaan | var | **NOT_CREATED** | var (TR+EN) |
| Diğer 14 | **NOT_CREATED** | **NOT_CREATED** | 14/14 var |

JSON profili gerçek karakter görseli sayılmadı. Model sheet üretimi için tek eksik
ücretsiz HF tokeni (ZeroGPU) veya onaylı API; ücret harcanmadı.

## 8. Tek karakter sistemi (mimari)

```text
CharacterBibleStore (SQLite, private)     → kimlik, sürüm, 28 ilişki, 3 kanon
CoreCastVoiceSpec (kod)                   → cinsiyet, yaş, konuşma, ses yönü
characters/*.json (public repo)           → görsel kanon (2/16)
audio/core-voices/ (private)              → 28 WAV (denetlendi)
                       ↓
        CharacterCanon (salt okunur birleşik görünüm)
                       ↓
   çizgi film hattı (keyframe → I2V → QA) · ses üretimi · merch model sheet
```

Yeni bağımsız DB yok; mevcut store yeniden kullanılıyor. Özel yollar raporlarda
yalnız yerel olarak geçiyor; public repoda aile/ilişki dökümü yok.

## 9. Kalan işler

1. Aden ve Kaan model sheet (ön/yan/arka/3-4 + ifade) — HF tokeni bekliyor.
2. Kız Aden kanonuyla take2 (sabit kamera) — kota bekliyor.
3. Diğer 14 karakter için görsel kanon + model sheet.
4. Seslerde insan dinlemesi: yaş uygunluğu, ayrışma, TR/EN kimlik sürekliliği.
5. 3 sahnelik pilot ve işçi/QA kayıtları (onay sonrası).
