import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import audio_qa as Q
SR = 16000

def tone(sec, amp=0.3, f=180):
    t = np.arange(int(SR * sec)) / SR
    return (amp * np.sin(2 * np.pi * f * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)

def fade(x, n=800):
    x = x.copy(); x[:n] *= np.linspace(0, 1, n); x[-n:] *= np.linspace(1, 0, n); return x

def test_good_line_passes():
    p, s = Q.validate_speech(fade(np.concatenate([np.zeros(3000), tone(2.0), np.zeros(3000)])), SR, "Merhaba ben Aden, nasılsın bugün")
    assert p == [], p

def test_silent_file_fails():
    p, _ = Q.validate_speech(np.zeros(SR * 2, dtype=np.float32), SR, "Merhaba")
    assert any("SESSİZ" in x for x in p)

def test_clipping_is_caught():
    x = np.clip(tone(2.0, 3.0), -1, 1)
    p, _ = Q.validate_speech(x, SR, "Merhaba ben Aden nasılsın")
    assert any("CLIPPING" in x for x in p)

def test_missing_text_short_audio_is_caught():
    p, _ = Q.validate_speech(fade(tone(0.4)), SR, "Bu çok uzun bir cümle ve ses dosyası çok kısa kalmış demek ki metin eksik")
    assert any("METİN_EKSİK" in x for x in p)

def test_abrupt_cut_is_caught():
    p, _ = Q.validate_speech(tone(2.0), SR, "Merhaba ben Aden nasılsın bugün")      # fade yok, yüksek seviyede biter
    assert any("KESİLME" in x for x in p)

def test_music_masking_and_ducking_measured():
    sp = np.concatenate([np.zeros(SR), fade(tone(2.0, 0.3)), np.zeros(SR)])
    loud_music = tone(4.0, 0.3, 300)
    assert Q.speech_over_music_db(sp, loud_music, SR) < 6                         # müzik konuşmayı bastırıyor
    duck = loud_music.copy(); duck[SR:3 * SR] *= 0.1
    assert Q.speech_over_music_db(sp, duck, SR) > 12
    assert Q.ducking_db(sp, duck, SR) > 15
    assert Q.ducking_db(sp, loud_music, SR) < 3
