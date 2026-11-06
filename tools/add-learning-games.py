"""Mipiluna · öğrenme oyunları (Sayı Avı + Harf Eşleştirme) ekler.

- İki yeni oyun: sayı tanıma ve harf tanıma (okul öncesi müfredatı)
- Öğretmen anlatım sesleri üretilir
- Mevcut oyun motoruna (CLASSES) bağlanır
"""

from __future__ import annotations

import asyncio
import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import edge_tts

WWW = Path(r"C:\actions-runner\_work\runpod-ltx2\runpod-ltx2\ahos_core\runtime\projects\mipiluna\www")
VOICES = WWW / "voices" / "ahos"
HTML = WWW / "sokak-oyunlari.html"


async def make_voice(name: str, sentences: list[str]) -> None:
    frames = []
    for sentence in sentences:
        data = b""
        for _ in range(3):
            buffer = io.BytesIO()
            try:
                communicate = edge_tts.Communicate(sentence, "tr-TR-EmelNeural", rate="-5%")
                async for chunk in communicate.stream():
                    if chunk.get("type") == "audio" and chunk.get("data"):
                        buffer.write(chunk["data"])
                data = buffer.getvalue()
            except Exception:
                data = b""
            if data:
                break
            await asyncio.sleep(0.4)
        if data:
            frames.append(data)
    if frames:
        (VOICES / f"{name}.mp3").write_bytes(b"".join(frames))
        print(f"  ses: {name}")


async def voices() -> None:
    await make_voice("t-16-sayilar", [
        "Sayı avı oynuyoruz.",
        "Kaç tane olduğunu say ve doğru sayıya dokun.",
    ])
    await make_voice("t-17-harfler", [
        "Harf oyunu.",
        "Resmin adı hangi harfle başlıyorsa ona dokun.",
    ])


GAME_ENTRIES = """    { id:'sayilar', emoji:'🔢', title:'Sayı Avı', desc:'Nesneleri say, doğru sayıya dokun.',
      teacher:'t-16-sayilar', hint:'t-09-ipucu-seksek' },
    { id:'harfler', emoji:'🔤', title:'Harf Eşleştirme', desc:'Resmin ilk harfini bul.',
      teacher:'t-17-harfler', hint:'t-09-ipucu-seksek' }
  ];"""

CLASS_CODE = r"""
  /* ---------- 7) SAYI AVI (okul öncesi sayı tanıma) ---------- */
  function Sayilar(){
    var target = 1, options = [], rects = [], answered = false, tries = 0;
    var EMOJI = ['⭐','🍎','🐟','🌸','🚗','🐥','🪁','🍓','🐞','🎈'];
    this.setup = function(){
      var lv = (window.__level || 1);
      target = 1 + Math.floor(Math.random() * Math.min(10, 3 + lv * 3));
      answered = false; tries = 0;
      options = [target];
      while (options.length < 3){
        var value = 1 + Math.floor(Math.random() * 10);
        if (options.indexOf(value) < 0) options.push(value);
      }
      options.sort(function(){ return Math.random() - 0.5; });
      play('sayi-01-yonerge');
    };
    this.down = function(p){
      if (answered) return;
      for (var i = 0; i < rects.length; i++){
        var r = rects[i];
        if (p.x > r.x && p.x < r.x + r.w && p.y > r.y && p.y < r.y + r.h){
          if (options[i] === target){
            answered = true;
            try { play('sayi-' + String(target).padStart(2, '0')); } catch(e){}
            finish(12, tries === 0 ? 3 : (tries <= 2 ? 2 : 1), 'Doğru! ' + target + ' tane vardı.');
          } else {
            tries++; lives--; play('k-03-yanlis');
            if (lives <= 0) fail('Sayıyı bilemedin, tekrar dene.');
          }
          return;
        }
      }
    };
    this.key = function(){};
    this.update = function(){ energy = Math.max(0, lives / 3); };
    this.draw = function(g){
      g.fillStyle = '#cfe0ff'; g.font = '18px system-ui'; g.textAlign = 'center';
      g.fillText('Kaç tane var?', W / 2, 40);
      var emoji = EMOJI[target % EMOJI.length];
      var startX = W / 2 - (target * 46) / 2;
      g.font = '34px system-ui'; g.textAlign = 'left';
      for (var i = 0; i < target; i++) g.fillText(emoji, startX + i * 46, 130);
      rects = [];
      var bw = 150, gap = 26, totalW = options.length * bw + (options.length - 1) * gap;
      var bx = (W - totalW) / 2;
      for (var k = 0; k < options.length; k++){
        var r = { x: bx + k * (bw + gap), y: H - 160, w: bw, h: 110 };
        rects.push(r);
        g.fillStyle = '#22345c'; g.strokeStyle = '#3a4d78'; g.lineWidth = 2;
        g.beginPath(); g.roundRect(r.x, r.y, r.w, r.h, 18); g.fill(); g.stroke();
        g.fillStyle = '#eef3ff'; g.font = 'bold 46px system-ui'; g.textAlign = 'center';
        g.fillText(String(options[k]), r.x + r.w / 2, r.y + r.h / 2 + 16);
      }
    };
  }

  /* ---------- 8) HARF EŞLEŞTİRME ---------- */
  function Harfler(){
    var words = [
      { e:'🐝', w:'arı', l:'a' }, { e:'🍎', w:'elma', l:'e' }, { e:'🐄', w:'inek', l:'i' },
      { e:'🚌', w:'otobüs', l:'o' }, { e:'✈️', w:'uçak', l:'u' }, { e:'🐟', w:'balık', l:'b' },
      { e:'🐈', w:'kedi', l:'k' }, { e:'🐌', w:'salyangoz', l:'s' }
    ];
    var chosen = null, options = [], rects = [], answered = false, tries = 0;
    this.setup = function(){
      chosen = words[Math.floor(Math.random() * words.length)];
      answered = false; tries = 0;
      options = [chosen.l];
      var pool = words.map(function(x){ return x.l; });
      while (options.length < 3){
        var letter = pool[Math.floor(Math.random() * pool.length)];
        if (options.indexOf(letter) < 0) options.push(letter);
      }
      options.sort(function(){ return Math.random() - 0.5; });
      play('harf-01-yonerge');
    };
    this.down = function(p){
      if (answered) return;
      for (var i = 0; i < rects.length; i++){
        var r = rects[i];
        if (p.x > r.x && p.x < r.x + r.w && p.y > r.y && p.y < r.y + r.h){
          if (options[i] === chosen.l){
            answered = true;
            try { play('harf-' + chosen.l); } catch(e){}
            finish(12, tries === 0 ? 3 : (tries <= 2 ? 2 : 1), 'Doğru! ' + chosen.w + ' ' + chosen.l + ' ile başlar.');
          } else {
            tries++; lives--; play('k-03-yanlis');
            if (lives <= 0) fail('Harfi bilemedin, tekrar dene.');
          }
          return;
        }
      }
    };
    this.key = function(){};
    this.update = function(){ energy = Math.max(0, lives / 3); };
    this.draw = function(g){
      g.fillStyle = '#cfe0ff'; g.font = '18px system-ui'; g.textAlign = 'center';
      g.fillText('Hangi harfle başlıyor?', W / 2, 40);
      g.font = '86px system-ui'; g.fillText(chosen.e, W / 2, 170);
      g.fillStyle = '#eef3ff'; g.font = 'bold 30px system-ui';
      g.fillText(chosen.w, W / 2, 220);
      rects = [];
      var bw = 130, gap = 26, totalW = options.length * bw + (options.length - 1) * gap;
      var bx = (W - totalW) / 2;
      for (var k = 0; k < options.length; k++){
        var r = { x: bx + k * (bw + gap), y: H - 160, w: bw, h: 110 };
        rects.push(r);
        g.fillStyle = '#22345c'; g.strokeStyle = '#3a4d78'; g.lineWidth = 2;
        g.beginPath(); g.roundRect(r.x, r.y, r.w, r.h, 18); g.fill(); g.stroke();
        g.fillStyle = '#eef3ff'; g.font = 'bold 48px system-ui'; g.textAlign = 'center';
        g.fillText(options[k], r.x + r.w / 2, r.y + r.h / 2 + 16);
      }
    };
  }

  var CLASSES = { seksek: Seksek, bestas: Bestas, yakartop: YakarTop, yerdenyuksek: YerdenYuksek, yedikule: YediKule, saklambac: Saklambac, sayilar: Sayilar, harfler: Harfler };
"""


def main() -> None:
    asyncio.run(voices())
    text = HTML.read_text(encoding="utf-8", errors="replace")

    if "id:'sayilar'" in text:
        print("öğrenme oyunları zaten var")
    else:
        text = text.replace(
            "    { id:'saklambac', emoji:'🙈', title:'Saklambaç', desc:'Saklan; ebe görmeden 25 saniye dayan.',\n"
            "      teacher:'t-14-saklambac', hint:'t-15-ipucu-saklambac' }\n  ];",
            "    { id:'saklambac', emoji:'🙈', title:'Saklambaç', desc:'Saklan; ebe görmeden 25 saniye dayan.',\n"
            "      teacher:'t-14-saklambac', hint:'t-15-ipucu-saklambac' },\n" + GAME_ENTRIES,
        )
        # sınıf kodunu CLASSES satırının önüne ekle, eski CLASSES satırını kaldır
        text = re.sub(
            r"  var CLASSES = \{[^\n]*\};\n",
            CLASS_CODE,
            text,
            count=1,
        )
        HTML.write_text(text, encoding="utf-8")
        print("öğrenme oyunları eklendi")

    scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)
    for script in scripts:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
            handle.write(script)
            path = handle.name
        done = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        print("JS:", "OK" if done.returncode == 0 else "HATA")
        if done.returncode != 0:
            print(done.stderr[:500])


main()
