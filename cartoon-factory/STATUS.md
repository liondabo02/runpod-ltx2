# Cartoon Factory — Proje Durumu

> Bu dosya projenin tek bakışta ilerleme ekranıdır. Her önemli geliştirmede güncellenir.

## Genel durum

- Altyapı / orkestrasyon: %78
- Telegram kontrol: %70
- 5 dil lokalizasyon zinciri: %72
- Görsel üretim / karakter assetleri: %32
- Ses / lip-sync: %68
- Render / montaj: %62
- Pilot bölüm: %18
- Tam otomatik 8 dk bölüm: %28

## Proje izolasyonu

- [x] Cartoon Factory ana LTX2 proje kökünden ayrıldı.
- [x] Tüm Cartoon Factory uygulama dosyaları `cartoon-factory/` altında toplandı.
- [x] Eski `cartoon_factory/` klasörü feature branch'ten kaldırıldı.
- [x] Main branch'e yanlışlıkla eklenen Cartoon Factory README temizlendi.
- [x] Bundan sonraki geliştirmeler yalnızca `cartoon-factory/` altında yapılacak.

## Ana hikâye yapısı

- Merkez karakter: **Harun**
- Çocuk başroller: **Aden (3)** ve **Kaan (1)**
- Ana ev: **Harun + Esma'nın evi**
- Esra, Aden ve Kaan bu evde yaşıyor.
- Ahmet Aden ve Kaan'ın babası; evde sürekli yaşamıyor, yaklaşık haftada bir aile içine geliyor.
- Harun herkesin toplandığı, güvenilen, sevilen ve çoğu bölümde çözümü toparlayan karakter.

## Sabit kadro — 16 karakter kilitli

1. Harun
2. Aden
3. Kaan
4. Esra
5. Ahmet
6. Esma
7. Veysel
8. Öznur
9. Salih
10. Medine
11. Davut
12. Fatoş
13. Emoş
14. Berzan
15. Aras
16. Ramin

Ana 16 karakter kalıcıdır. Bölüm akışına göre doktor, öğretmen, komşu, kasiyer, park görevlisi vb. misafir karakterler otomatik üretilebilir; bunlar ana kadroyu değiştirmez.

## Yapılanlar

- [x] `feature/cartoon-factory` branch'i oluşturuldu.
- [x] Otomatik senaryo ve sahne planlama altyapısı kuruldu.
- [x] Tek kelimeden 8 dakikalık bölüm planı üretecek giriş mantığı kuruldu.
- [x] OpenAI-compatible LLM bağlantısı eklendi (`openrouter/free` varsayılan).
- [x] 8 dakikalık bölüm için scene/job manifest yapısı kuruldu.
- [x] Sabit 16 karakter ile misafir karakterler ayrıldı.
- [x] 16 karakter için kimlik / rol / ilişki / görünüş kuralları kilitlendi.
- [x] 16 karakter için model sheet, pose, expression ve mouth-shape job builder güncellendi.
- [x] Tekrar kullanılabilir arka plan dünyası/bible eklendi.
- [x] 5 dil aktif: TR / DE / AR / FR / ES.
- [x] Lokalizasyon worker eklendi; sahne süreleri korunuyor.
- [x] Her dil için ayrı TTS/lip-sync job manifesti oluşturuluyor.
- [x] Chatterbox Multilingual V3 voice-service mikroservisi eklendi.
- [x] Piper hafif fallback olarak tutuldu.
- [x] Rhubarb lip-sync cue üretimi eklendi.
- [x] FFmpeg sprite render altyapısı eklendi.
- [x] Her dil için ayrı video klasörü ve final MP4 akışı eklendi.
- [x] Sahne videolarını tek MP4'e birleştiren final montaj eklendi.
- [x] Ortak müzik/SFX job altyapısı eklendi.
- [x] Telegram bot gateway eklendi: normal mesaj = yeni bölüm, `/status` = durum.
- [x] Telegram biten bölümde 5 dil çıktısını teslim edecek şekilde kodlandı.
- [x] FastAPI `/episodes/run` ve `/episodes/{id}/status` endpointleri eklendi.
- [x] Docker Compose'a API + Telegram + voice-service eklendi.
- [x] RunPod/LTX-2 özel sahne yönlendirme altyapısı mevcut.
- [x] RunPod karakter-generation worker paketi eklendi.
- [x] Karakter asset kontratı ve kalite kuralları oluşturuldu.
- [x] 30–60 saniyelik pilot manifest altyapısı eklendi.

## Şimdi üzerinde çalışılan aşama

### Gerçek karakter assetleri + ilk pilot

Öncelik sırası:

1. Harun
2. Aden
3. Kaan
4. Esra
5. Esma
6. Ahmet
7. Kalan 10 sabit karakter

Her karakter için:

- ana front reference / model sheet
- ön / 3-4 açı / yan / arka görünüş
- sabit renk / siluet / imza özellikler
- 8+ yüz ifadesi
- idle / talk / walk / run / sit / jump / point / wave / hug / carry / kneel pozları
- 8 ağız şekli
- tek karakter ses kimliği / reference WAV

## Kalan ana işler

- [ ] Cartoon Factory için ayrı RunPod ComfyUI endpoint oluşturmak
- [ ] 16 karakter için gerçek onaylı PNG/model-sheet assetleri
- [ ] 16 karakter için yapay/sahip olunan referans ses WAV'ları
- [ ] Arka plan PNG paketlerini gerçek olarak üretmek
- [ ] Rhubarb mouth-cue'larını gerçek mouth layer compositing ile sprite renderer'a bağlamak
- [ ] Daha doğal walk/talk/idle hareket sistemi
- [ ] Müzik üretim veya ticari kullanıma uygun özgün müzik motorunu bağlamak
- [ ] SFX kütüphanesini gerçek dosyalarla doldurmak
- [ ] RunPod'da Chatterbox voice-service GPU deploy
- [ ] RunPod/ComfyUI karakter asset generation endpointini gerçek workflow'a bağlamak
- [ ] 35–60 saniyelik ilk gerçek pilot render
- [ ] Pilot kalite değerlendirme + otomatik retry
- [ ] Tam 8 dakikalık bölüm render
- [ ] n8n import edilebilir üretim workflow'u
- [ ] Büyük MP4 dosyaları için object storage / public delivery URL
- [ ] YouTube otomatik yayınlama

## Başarı kriteri

İlk pilot ancak şu şartlarda "geçti" sayılacak:

- Harun, Aden ve Kaan her sahnede aynı görünmeli.
- 16 sabit karakterin kimliği değişmemeli.
- Karakterler fotoğraf gibi değil, kaliteli 2D çocuk çizgi filmi gibi görünmeli.
- Konuşma ve ağız hareketleri rahatsız edici olmamalı.
- Ses kimliği 5 dilde mümkün olduğunca korunmalı.
- Arka plan ve karakter stili birbiriyle uyumlu olmalı.
- 30–60 saniyelik pilot gerçekten izlenebilir olmalı.

## Kullanım hedefi

Telegram'a örnek:

`paylaşmak`

veya:

`Aden ve Kaan parkta paylaşmayı öğrensin. Harun herkesi toplasın.`

Beklenen çıktı:

- `episode_xxx_tr.mp4`
- `episode_xxx_de.mp4`
- `episode_xxx_ar.mp4`
- `episode_xxx_fr.mp4`
- `episode_xxx_es.mp4`

## Nereden takip edilir?

- Branch: `feature/cartoon-factory`
- Proje kökü: `cartoon-factory/`
- Durum dosyası: `cartoon-factory/STATUS.md`
- README: `cartoon-factory/README.md`

## Sonraki hedef

**Cartoon Factory için ayrı ComfyUI endpoint açmak; ardından 16 karakter için gerçek asset üretimini başlatmak ve ilk 35–60 saniyelik izlenebilir pilotu render etmek.**
