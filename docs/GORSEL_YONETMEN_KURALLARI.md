# AHOS Görsel Yönetmen Kuralları (referanslardan öğrenilen — kopya değil, ilke)

Kaynak: Harun'un verdiği referans çizgi filmler (Scooby-Doo, Şirinler, Tom & Jerry, Cedric, Caillou, Türkçe masal çizgi filmleri). Karakter, müzik, sahne KOPYALANMAZ; yalnız ilkeler alınır.
Senaryo, mekân, ışık, kamera ve arka plan işçileri hazırlık yaparken bu kuralları uygular. `studio_standards_check.py` ve QA bunlara göre denetler.

## 1. Mekân (arka plan) kuralları
1. Sade/boş duvar yok. İç mekân her planda en az 5 "yaşam izi" taşır: poster/tablo, raf+nesneler, lamba/abajur, perde/pencere, halı/mobilya. (Caillou salonu: abajur, çekmeceli dolap, kanepe, mum, vazo, raf.)
2. Arka plan "boyama" hissi verir: yumuşak doku, tuğla/ahşap/yaprak gibi malzeme desenleri (Tom & Jerry kapı sütunları: tuğla deseni, demir parmaklık, ağaç gövdesi).
3. Derinlik 3 katmandır: ön plan (parmaklık, bitki, mobilya kenarı), orta plan (oyuncular), uzak plan (silik, açık renkli, hafif odak dışı). Ön plan nesnesi karakterin önünden geçerek derinlik yaratır (kapı demirleri arkasında köpek).
4. Gökyüzü düz renk değil: gradyan + bulut şeritleri.
5. Mekân kimliği: her mekân en az 1 ayırt edici nesne taşır; iç/dış mekân karışmaz (ev koridoru asla park gibi çizilmez).
6. Perspektif: zemin çizgisi ufuktan farklı; masa/halı elips ve yamuk kullanır.

## 2. Işık kuralları
1. Her sahnenin bir ışık kaynağı vardır ve senaryoda yazılır (pencere, abajur, güneş, ay). Işık yönü gölgeyi belirler.
2. İç mekân sıcak (sarı/turuncu) dolgu + dış/pencere soğuk (mavi) karşıtlığı (Şirinler yatak odası gece: mavi duvar + sıcak lamba).
3. Gece sahnesi tamamen karanlık değil: mavi ton + tek sıcak ışık adası; karakter yüzü okunur kalır.
4. Karakterlerin altında yumuşak zemin gölgesi; ışık tarafında hafif kenar parlaması.
5. Duygu = ışık: korku sahnesi soğuk ve düşük, neşe sahnesi sıcak ve parlak.

## 3. Kamera ve kurgu
1. Her sahne bir "kuruluş planı" (geniş) ile başlar, sonra orta/yakın plana iner.
2. Konuşan karakter yakın/orta planda; tepki planı (dinleyen yüz) araya girer.
3. Önemli nesne (Masal çizgi filmindeki mücevher/makara) için ayrı "ek plan" (insert) vardır, nesne tam görünür.
4. Plan başına 2–6 sn; hareketsiz uzun plan yok. Hafif kamera kayması/zoom (push-in) duyguyu vurgular.
5. Yakın planda yüz kadrajda tam olmalı (kesik kafa/yalnız bacak yok).

## 4. Karakter / hareket
1. Çizgi kalın ve tutarlı; renk alanları düz + tek ton gölge (cel shading). Masal örneğinde ten, giysi ve duvar ayrı renk ailesindedir; karakter arka plandan renk olarak ayrışır.
2. Abartılı ifade: göz kırpma, ağız şekilleri, kaş eğimi; Tom & Jerry'de beklenti (anticipation) ve aşırı tepki.
3. Hareketin ön hazırlığı, ana hareketi, oturması vardır (squash/stretch, follow-through).
4. Eller okunur ve jest yapar (masalda parmaklar ayrı, anlamlı).

## 5. Senaryo hazırlığı (yazarken zorunlu çıktılar)
Her sahne için işçi şunu üretir: mekân kimliği, ışık kaynağı+saat, 5 yaşam izi listesi, kamera planı listesi, ayırt edici nesne, duygu eğrisi. Bunlar `beat_sheet` alanlarına (`location`, `light_time`, `camera`, `enrichment`) yazılır; eksikse standart kontrolü FAIL verir.

## 6. Yasaklar
- Boş/tek renk arka plan, iç-dış mekân karışıklığı, düz tek renk gökyüzü, tüm planın aynı kadrajda kalması, karakter kesilmesi, referans karakter/müziğin kopyalanması.
