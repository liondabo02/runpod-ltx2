# Cartoon Factory — Proje Durumu

> Bu dosya projenin tek bakışta ilerleme ekranıdır. Her önemli geliştirmede güncellenir.

## Genel durum

- Altyapı: %60
- Görsel üretim / karakter assetleri: %20
- Ses / lip-sync: %55
- Render / montaj: %55
- Pilot bölüm: %15
- Tam otomatik 8 dk bölüm: %10

## Ana hikâye yapısı

- Merkez karakter: **Harun**
- Çocuk başroller: **Aden (3)** ve **Kaan (1)**
- Ana ev: **Harun + Esma'nın evi**
- Esra, Aden ve Kaan bu evde yaşıyor.
- Ahmet Aden ve Kaan'ın babası; evde sürekli yaşamıyor, yaklaşık haftada bir aile içine geliyor.
- Harun herkesin toplandığı, güvenilen, sevilen ve çoğu bölümde çözümü toparlayan karakter.

## Sabit kadro

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

## Yapılanlar

- [x] `feature/cartoon-factory` branch'i oluşturuldu.
- [x] Otomatik senaryo ve sahne planlama altyapısı kuruldu.
- [x] OpenAI-compatible LLM bağlantısı eklendi (`openrouter/free` varsayılan).
- [x] 8 dakikalık bölüm için scene/job manifest yapısı kuruldu.
- [x] Piper TTS worker eklendi.
- [x] Rhubarb lip-sync entegrasyonu eklendi.
- [x] FFmpeg sprite render altyapısı eklendi.
- [x] Sahne videolarını tek MP4'e birleştiren final montaj eklendi.
- [x] Müzik/SFX job altyapısı eklendi.
- [x] n8n/webhook için FastAPI endpoint eklendi.
- [x] RunPod/LTX-2 özel sahne yönlendirme altyapısı eklendi.
- [x] Karakter asset kontratı ve kalite kuralları oluşturuldu.
- [x] 30–60 saniyelik pilot manifest altyapısı eklendi.
- [x] 16 karakterlik gerçek aile evreni ve ilişkiler sisteme işlendi.

## Şimdi üzerinde çalışılan aşama

### Karakter üretimi ve kilitleme

Öncelik:

1. Harun
2. Aden
3. Kaan
4. Esra
5. Esma
6. Ahmet

Her karakter için üretilecek:

- model sheet
- ön / 3-4 açı / yan / arka görünüş
- sabit kıyafet ve renk paleti
- 8+ yüz ifadesi
- idle / talk / walk / run / sit / jump / point / wave pozları
- 8 ağız şekli
- ses kimliği

## Kalan ana işler

- [ ] Harun, Aden ve Kaan için gerçek onaylı karakter görselleri
- [ ] Diğer 13 karakter için karakter paketleri
- [ ] Arka plan kütüphanesi (ev, salon, mutfak, park, sokak vb.)
- [ ] 16 karakter için sabit ses modelleri / ses profilleri
- [ ] Gerçek müzik üretim veya telifsiz müzik motoru bağlantısı
- [ ] SFX kütüphanesi
- [ ] Sprite animasyonlarını daha doğal hale getiren hareket sistemi
- [ ] 35–60 saniyelik ilk gerçek pilot render
- [ ] Pilot kalite değerlendirme ve düzeltme
- [ ] Tam 8 dakikalık bölüm render
- [ ] n8n ile uçtan uca tek komut üretim
- [ ] QC + otomatik retry
- [ ] Çok dilli seslendirme
- [ ] YouTube otomatik yayınlama

## Başarı kriteri

İlk pilot ancak şu şartlarda "geçti" sayılacak:

- Harun, Aden ve Kaan her sahnede aynı görünmeli.
- Karakterler fotoğraf gibi değil, kaliteli 2D çocuk çizgi filmi gibi görünmeli.
- Konuşma ve ağız hareketleri rahatsız edici olmamalı.
- Sesler karakterlere sabitlenmeli.
- Arka plan ve karakter stili birbiriyle uyumlu olmalı.
- 30–60 saniyelik pilot gerçekten izlenebilir olmalı.

## Nereden takip edilir?

- PR: `https://github.com/liondabo02/runpod-ltx2/pull/3`
- Branch: `feature/cartoon-factory`
- Bu dosya: `cartoon_factory/STATUS.md`
- Ana klasör: `cartoon_factory/`

## Sonraki hedef

**Harun + Aden + Kaan karakterlerini görsel olarak üretip kilitlemek ve ilk gerçek pilotu render etmek.**
