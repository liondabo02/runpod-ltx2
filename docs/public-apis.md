# public-apis kataloğu (ücretsiz API'ler)

Kaynak: [public-apis](https://github.com/public-apis/public-apis) — MIT lisanslı,
yüzlerce ücretsiz API'nin bakımı yapılan listesi.

**Bu bir sağlayıcı değil, bir listedir.** AHOS onu yalnızca *arama* için kullanır;
katalogdan otomatik istek atmaz. Dış çağrılar egress muhafızından geçer ve yalnızca
açıkça izin verilen origin'lere gider.

## Kurulum (ağ erişimi olan makinede, bir kez)

```bash
curl -L https://raw.githubusercontent.com/public-apis/public-apis/master/README.md -o public-apis.md
python tools/build_public_api_catalog.py public-apis.md
# -> ahos_core/data/public-apis.json
```

Katalog yoksa arama **boş döner ve nedenini söyler**; uydurma sonuç üretmez.

## Kullanım

```python
from ahos.api_catalog import search, stats

stats()
# {'available': True, 'entries': 1400, 'categories': 50, 'no_auth': 700, 'https': 1300}

search("weather")                      # varsayılan: HTTPS + her türlü auth
search("currency", no_auth_only=True)  # anahtarsız, doğrudan kullanılabilir
search(category="Animals", limit=5)
```

## Kural

Bir görev dış veri gerektirdiğinde sıra şudur:

1. `search(..., no_auth_only=True)` ile **anahtarsız + HTTPS** uç ara.
2. Uygun aday varsa origin'i egress allowlist'ine ekle (politika: `net.allow`).
3. Anahtar gerekiyorsa **sahip onayı** olmadan kullanma; anahtar `.env`'e girer, loglanmaz.
4. Sonuç, görev çıktısında kaynak URL'siyle birlikte saklanır — kanıtsız veri "teslim" sayılmaz.
