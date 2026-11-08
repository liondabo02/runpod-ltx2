# AHOS-QUALITY-99 — Program Durumu

**Amaç:** AHOS Holding'in ölçülebilir kalitesini mevcut mimariyi bozmadan %99 hedefine yaklaştırmak.
**İzolasyon:** Bu program ayrı bir Git worktree'sinde çalışır.

| Alan | Değer |
|---|---|
| Worktree | `C:\actions-runner\_work\ahos-quality-99` |
| Branch | `quality-99/ahos` |
| Başlangıç commit'i | `32bc435` (feature/agent-control-plane) |
| Ana çalışma ağacı | `C:\actions-runner\_work\runpod-ltx2\runpod-ltx2` (başka ajanlar kullanıyor) |
| Canlı runtime | `...\runpod-ltx2\ahos_core\runtime` (salt-okunur ölçüm) |

## Çalışma kuralları

1. Ana çalışma ağacındaki dosyalara yazma yok; tüm kod değişiklikleri worktree'de.
2. Başka ajanların commit'leri silinmez, rebase/force-merge yapılmaz.
3. Canlı servisler (8765, 8766), kuyruk ve proje kilitleri değiştirilmez; yalnız okunur.
4. Ücretli API yok. Yerel model ancak ≥2 GiB boş RAM ve yapılandırma varsa.
5. Her değişiklik: birim testi → ilgili entegrasyon testi → tam paket → kanıt kaydı.
6. Ölçülmemiş alan "tamamlandı" sayılmaz; tahmini yüzde başarı olarak sunulmaz.

## Durum

- Aşama: **ölçüm tamam, ilk düzeltme uygulandı**
- Başlangıç ölçümü: `BASELINE.md`
- Test tabanı: worktree'de `python -m pytest -q` → aşağıdaki kayıtlara bakın
- Açık işler: `BACKLOG.md`

## Kanıt klasörü

`quality/evidence/` — her görev için komut + çıktı + değişen dosya listesi.
