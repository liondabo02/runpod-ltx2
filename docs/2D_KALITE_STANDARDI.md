# AHOS 2D Çizgi Film Kalite Standardı (bağlayıcı çalışma ölçüsü)

Bu belge, izlenen S01E001 denemesinin neden "berbat" bulunduğunu ve gerçek 2D çizgi filmlerde olup bizde olmayanları listeler.
Her madde bir işçiye atanmıştır ve `tools/studio_standards_check.py` ile ölçülür. Teknik PASS, profesyonel kalite DEĞİLDİR; son karar sahipte.

## 1. Teşhis (S01E001 ilk deneme)
| Alan | Gözlenen | Kök neden |
|---|---|---|
| Yüzler | 16 karakterin yüzü aynı kalıp | tek göz/burun/ağız şablonu, yalnız renk/giysi ayrışıyordu |
| Ses | robotik, bütün karakterler 2 ses | TTS dosyalarında ~1 sn sondaki sessizlik, tek perde, seviye farkı |
| Senkron | kayık, ölü boşluklar | sessizlik süreye ekleniyordu; 12 fps'te kısa ağız şekilleri atlanıyordu |
| Müzik | tıngırtı | rastgele pentatonik notalar; akor, tema, ritim, yankı yoktu |
| Mekân | düz, boş | tek katman, ışık/atmosfer yok |
| Efekt | sıfır | geçiş, parçacık, ışık huzmesi, duygu simgesi yoktu |
| Senaryo | olduğu gibi aktarım | zenginleştirme (tepki, arka plan, şaka) yoktu |

## 2. Gerçek 2D çizgi filmde olup bizde olması gerekenler
1. **Animasyonun 12 ilkesi**: ezme-esneme, hazırlık (anticipation), takip (follow-through), bindirme (overlap), yaylar, ikincil hareket, zamanlama, abartı, çekicilik.
2. **Karakter oyunculuğu**: bakış sıçramaları, göz kırpma, kaş, "önce bak sonra konuş", dinleyen karakterin tepkisi, tutuş (hold) sırasında bile hafif yaşam (moving hold).
3. **Ayırt edilebilir tasarım**: siluet testi (gölge olarak bile tanınma), göz/kaş/burun/saç/sakal/yüz oranı farkı, yaşa göre oran (bebek: iri göz; yetişkin: küçük göz).
4. **Çok katmanlı mekân**: arka plan + orta plan + ön plan, kamera ile paralaks, ışık yönü, gölge, atmosfer parçacıkları, renk betiği (sahne duygusuna göre renk tonu).
5. **Efekt animasyonu**: toz, ter, kalp, yıldız, hız çizgisi, geçişler (iris, silme, çapraz), vurgu yazısı.
6. **Ses tasarımı**: ayrı ses kimlikleri, tutarlı seviye, Foley (adım, kapı, kumaş), ortam sesi, nefes/tepki sesleri, diyalogda müzik kısılması.
7. **Müzik**: ana tema (leitmotif) her bölümde geri gelir; sahne duygusuna göre enstrüman/tempo; geçişlerde vurgu.
8. **Kurgu ritmi**: çekim uzunluğu çeşitliliği, plan çeşitliliği (geniş/orta/yakın/ara plan), 3-8 sn'de bir görsel değişim.
9. **Çocuk programı yazımı**: tekrar, çağrı-cevap, izleyiciye hitap, küçük komedi, her sahnede bir "ödül" anı.

## 3. Ölçülebilir kapılar (`studio_standards_check.py`)
- Yüz ayrışması: her karakter çifti için özellik mesafesi ≥ 4 (göz şekli, kaş, burun, saç, sakal, saç rengi, ten, yüz genişliği, gözlük/aksesuar).
- Ses kimliği: farklı (ses, perde, hız) üçlüsü sayısı ≥ karakter sayısının %75'i; satır başı/sonu sessizlik ≤ 0,25 sn; aynı vuruşta satır arası boşluk ≤ 0,8 sn.
- Dudak senkronu: ilk ağız açılışı ile ses başlangıcı farkı ≤ 80 ms (örneklem üzerinden).
- Müzik: yatak (bed) var, her sahne sınırında vurgu var, müzik/diyalog dengesi −10…−24 dB.
- Görsel zenginlik: dakikada ≥ 4 efekt/simge olayı, parçacık+ışık katmanı açık, sahne geçişi var.
- Kurgu: ortalama çekim ≤ 8 sn, en az 3 farklı plan türü.
- Senaryo: replik kapsamı ≥ %85 (sahip senaryosunda), zenginleştirme önerileri ayrı belgede.
Bu kapılar yalnız ölçülebilir olanları kontrol eder; **yaratıcı zevk sahip tarafından onaylanır**.

## 4. Sınırlar (dürüst)
- Poster 3D/Pixar görünümlüdür; bu motor düz 2D kukla (puppet) çizer. 3D veya poster benzeri görünüm için GPU/görüntü motoru kararı sahibindedir.
- Ücretsiz TTS doğal insan sesi değildir. Gerçek oyuncu kalitesi için ücretli ses motoru ya da sesli oyuncu gerekir (sahip kararı).
- Kulakla/gözle zevk kontrolü bu belgedeki ölçülerle yapılamaz.
