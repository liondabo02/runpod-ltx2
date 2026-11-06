# Vendored: replica-skill tools

Bu klasördeki `parity.py` ve `imgdiff.py`, MIT lisanslı
[replica-skill](https://github.com/Jakeschincariol/replica-skill) projesinden
**olduğu gibi** alınmıştır (Jake Schincariol). Lisans metni `LICENSE` içinde.

- `parity.py` — özellik matrisinden parite skoru (must/should/could ağırlıklı).
- `imgdiff.py` — iki ekran görüntüsünün **düzen** farkı; renk farkı sayılmaz.
- `features.csv` — üst kaynaktaki örnek matris (şablon).

AHOS içinde `ahos/clone_acceptance.py` bu araçları sarar:

```python
from ahos.clone_acceptance import accept, feature_parity, layout_parity

passed, evidence = accept(
    "replica/features.csv",
    original_png="screenshots/original.png",
    clone_png="screenshots/clone.png",
    min_features=80.0,
    min_layout=50.0,
)
```

Kurallar (üst kaynaktan ve AHOS sözleşmesinden):

- Yalnızca **ölçer**; içerik, kod, görsel veya marka kopyalamaz.
- `skip` edilen ve orijinalde olmayan özellikler skora katılmaz — sayı sadece pariteyi ölçer.
- Zorunlu (must) bir özellik eksikse skor yüksek olsa bile teslim **kabul edilmez**.
- Araçlar ağa çıkmaz, standart kütüphane dışında bağımlılık kullanmaz.
