# ECC analizi — nedir, bizim için ne anlama gelir

İnceleme: 2026-11-01 · kaynak: [github.com/affaan-m/ECC](https://github.com/affaan-m/ECC)

## Tek cümle

ECC, **kodlama ajanlarının çalışma disiplinini paketleyen bir katman**:
planla → test et → uygula → gözden geçir → doğrula → hatırla → iyileştir.
Kendi başına model veya çalışma zamanı değil; Claude Code, Codex, Cursor,
OpenCode gibi ajanların içine "skills / agents / rules / hooks / memory"
olarak yerleşen bir sistem.

## Ölçülen büyüklük

| Gösterge | Değer |
|---|---|
| Yıldız | **294.733** |
| Çatal | 43.628 |
| Lisans | MIT |
| Dil | JavaScript (Node 18+) |
| İlk yayın | 2026-01-18 |
| İçerik | 71 agent · 314 skill · 98 komut · hook/memory/instincts · AgentShield |
| Dağıtım | `npx ecc-universal@2.2.3 setup`, Claude/Codex eklentisi, npm |
| Ticari katman | ECC Pro (özel repolar, 19 $/koltuk/ay) — açık kaynak MIT kalıyor |

## Nasıl çalışıyor

1. **Skills**: `SKILL.md` + YAML başlık; TDD, araştırma, güvenlik, veri, ML,
   operasyon gibi konularda hazır prosedürler. Tüm harness'lerde okunur.
2. **Agents**: planlama, inceleme, build onarımı, güvenlik, mimari rolleri.
3. **Hooks**: oturum başlangıcı/bitişi, komut öncesi/sonrası denetimler;
   `ECC_HOOK_PROFILE`, `ECC_DISABLED_HOOKS` ile ayarlanır.
4. **Memory + instincts**: oturum özetleri, öğrenilen "sezgi"ler, güven eşiği
   (`ECC_INSTINCT_CONFIDENCE_THRESHOLD`) ile bağlama enjekte edilir.
5. **AgentShield**: prompt, hook, MCP yapılandırması, izinler, sırlar ve ajan
   dosyalarını tarayan güvenlik katmanı.
6. **Token optimizasyonu**: bağlam penceresi yönetimi, oturum saklama süresi,
   enjeksiyon üst sınırı.

## Bizde zaten olanlar (ECC'nin fikri, bizim uygulamamız)

| ECC fikri | AHOS'ta karşılığı |
|---|---|
| plan → test → uygula → doğrula | Görev zinciri: brief → produce → proje kabul kapısı → bağımsız QA |
| "Doğrulanmadan tamam sayılmaz" | `delivery.verified` + DB tetikleyicisi (kayıt seviyesinde zorunlu) |
| Memory / instincts | `learning` durumu: 743 kart, 167 kaynak, enjeksiyon 872 |
| Skills | `doc_factory.PLAYBOOKS` (departman başına araç seti + çıktı) |
| AgentShield | `guvenlik` departmanı + sır taraması (kısmi) |
| Çok harness | Bizim harness Python; ECC JS/Node tabanlı plugin |

## Bizde olmayan, alınmaya değer üç şey

1. **SKILL.md Taşınabilirliği** — departman bilgimiz Python sözlüğünde kilitli.
   `skills/<departman>/SKILL.md` olarak dışa aktarılırsa Claude Code, Codex,
   Cursor gibi araçlar da aynı bilgiyi okur. (Bu depoda
   `tools/export_skills.py` ile yapıldı.)
2. **AgentShield tarzı sır/izin taraması** — `tools/agentshield_lite.py`:
   `sk-`, `ghp_`, `AKIA`, özel anahtar blokları, izlenen `.env` dosyaları.
3. **Sezgi (instinct) eşiği** — bizim öğrenme kartlarımız her zaman enjekte
   ediliyor; güven eşiği + üst sınır eklemek gürültüyü azaltır.

## Alınmaması gerekenler

- **Doğrudan kurulum**: ECC Claude Code/Codex eklentisi olarak çalışır; bizim
  Python hattına kurulmaz. Ajanlarımızın davranışını değiştirmez.
- **Körü körüne `npx`**: README'nin kendisi "sürüm pinleme güvenlik denetimi
  değildir" diyor. Kaynağı incelenmemiş paket çalıştırılmamalı.
- **Bağımlılık**: 294 bin yıldız kalite garantisi değil; MIT lisanslı içeriği
  kopyalamak yerine **fikirlerini** uygulamak bizim için daha güvenli.

## Sonuç

ECC, "ajanı disiplinli mühendis gibi çalıştıran" olgun bir tarif koleksiyonu.
Bizim sistemimizde bu disiplinin **zorlayıcı** hâli zaten var (kapılar,
tetikleyiciler, kanıt). ECC'den alacağımız şey **taşınabilirlik** (SKILL.md),
**güvenlik taraması** (AgentShield) ve **öğrenme eşiği**; kurulacak bir çalışma
zamanı değil.
