# AHOS Yaratıcılık Protokolü

Amaç: işçilerin "ortalama ama güvenli" çıktı üretmesini önlemek, yaratıcılığı ÖLÇÜLEBİLİR bir süreç yapmak.

1. **Farklı seçenekler:** Her yaratıcı karar için en az 3 seçenek; her biri farklı niyet/duygu/biçim.
2. **Bağımsız seçim:** Üretici seçmez. Eleştirmen/QA rubrikle seçer ve gerekçeyi `decision_log`a yazar.
3. **Referans kütüphanesi:** Serinin bible'ı ve önceki onaylı işler "ne yaptık" listesidir; tekrar yerine ilerleme hedeflenir.
4. **Orijinallik kapısı:** Bilinen karakter, eser, logo veya ses kopyalanmaz.
5. **Ders döngüsü:** Reddedilen her iş ve sahibin her geri bildirimi `studio/agents/memory/<worker_id>.jsonl` a ders olarak yazılır; sonraki işte işçi bu dersleri okur. Böylece işçiler eğitilmiş olur (model değil, kılavuz + hafıza).
6. **Sınır:** Yaratıcı onay yalnız sahibindedir; bütçe ve güvenlik kuralları yaratıcılıktan önce gelir.
