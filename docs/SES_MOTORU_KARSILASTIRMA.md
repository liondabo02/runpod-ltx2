# Ses motoru karşılaştırması (araştırma, 2026-11-25)
Kaynaklar: github.com/debpalash/OmniVoice-Studio README; ablt.dev "Open Source Turkish TTS" rehberi (ikincil kaynak — kurmadan önce her modelin resmî kartı doğrulanacak).

## "Voice Studio" nedir?
Büyük olasılıkla **VoiceStudio / OmniVoice-Studio** (debpalash). Yerel, açık kaynak; klonlama, dublaj, transkripsiyon. Varsayılan motor k2-fsa/OmniVoice. README 646 dil diyor ama **Türkçeyi listelemiyor → Türkçe doğrulanmadı**. Kod AGPL-3.0; model ağırlıkları, sesler ve çıktı için lisanslar model başına ayrı (Model Manager). Ücretli "Pro" sürüm kapalı kaynak. Windows: CUDA/ROCm/CPU. Kullanıcının kastettiği ürünün bu olup olmadığı **doğrulanmadı** (kullanıcıya sorulacak tek şey: kurulu olan hangisi).

## Adaylar (Türkçe)
| Aday | Türkçe kalite (ikincil kaynak) | Lisans | Ticari | Not |
|---|---|---|---|---|
| edge-tts (mevcut) | robotik bulundu (dinleme yapılmadı) | Microsoft servisi, ticari izin sahip kararı | belirsiz | 2 TR ses (Emel, Ahmet); çocuk sesi yok |
| Coqui XTTS-v2 | en doğal | CPML | **kısıtlı** | ücretsiz ticari kullanım yok |
| Meta MMS-TTS | 3/5 | CC-BY-NC 4.0 | **hayır** | zaten Kurmancî için kullanılıyor, uyarı notu var |
| SpeechT5 TR ince ayar | orta-iyi | MIT (taban); ince ayar kartı doğrulanmalı | muhtemel evet | tek konuşmacı değil, embedding ile çeşit |
| TurkicTTS | kullanılabilir | Apache-2.0 | **evet (izinli)** | en güvenli lisans |
| OmniVoice (VoiceStudio) | bilinmiyor | AGPL kod / ağırlık ayrı | ağırlığa bağlı | önce Türkçe testi şart |

## Karar durumu
Henüz seçilmedi. Elenenler (ticari hedef nedeniyle): XTTS-v2, MMS-TTS. İncelenecek: TurkicTTS, SpeechT5-TR, OmniVoice Türkçe testi. Donanım: kahta'da GPU durumu ölçülmedi (A1 ölçütü açık).
