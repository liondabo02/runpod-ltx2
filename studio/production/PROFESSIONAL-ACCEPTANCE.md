# AHOS Studio-16 | Uretim standardi ve gercek durum

Son kullanici onayi: 16 kisilik posterin **son revizyonu**, ozellikle Fatos'un son gorunumu. 
Onay yalnizca **2D posterin gorsel yonu** icindir. Bagimsiz karakter identity model, mesh, rig veya ses onayi degildir.
Kanon/identity-lock dosyalarini onaysiz degistirmeyin.

## Kanitli referans
- `studio/reference/owner_accepted_roster_v1/AHOS_Studio16_Approved_Poster.png`
- `studio/reference/owner_accepted_roster_v1/characters/01_aden.png` ... `16_ramin.png`
- `studio/reference/owner_accepted_roster_v1/manifest.json` her parcanin SHA-256 degerini icerir.
- Her panel tek postere ait bir **crop**; ayrik karakter gorseli, turnaround veya 3D model degildir.
- `tools/studio_production_gate.py --level storyboard` ile 16/16 poster kanitini dogrula.

## Profesyonel bir sahne icin kabul kosullari
1. Her karaktere ait onayli ayri on/yan/arka *model sheet*, mimik seti ve degismez kimlik referansi.
2. 3D secilirse yapilandirilmis mesh + rig + yuz blendshape; 2D secilirse gercek katmanlara ayrilmis puppet + armature/eklemler. Crop ile tum vucudu oynatmak bu kosulu karsilamaz.
3. Hareketler: aden yuruyus/kosus; Kaan yasina uygun emekleme; kafa/goz/agiz/el/ayak artikulasyonu; esya tutma ve karsilikli bakis.
4. Sesler: kayitli ses kimligi, Turkce telaffuz, lipsync, dogal zamanlama; ayrica hedef dil QA.
5. Izleyiciye giden video: gercek karakter eklemi hareketi, en az 1920x1080, kontrol edilen ses, tutarli yuz ve konum, sinematik sahne. Kayan sabit resim, yazi karti veya crop hareketi basari sayilmaz.
6. Uretim sonucu ve lisanslar hash ile kayitli olmali. Harcama kullanici onayi olmadan 0 EUR; bulut GPU/API baslatilmaz.

## Komutlar
```powershell
python tools/identity_lock.py --verify
python tools/studio_production_gate.py --level storyboard
python tools/studio_production_gate.py --level professional
python -m unittest discover -s tests -p test_studio_production_gate.py -v
```

Profesyonel kontrolu **basarisizsa** pazarlama metinlerinde 'film hazir', 'rig hazir', 'studio production-ready' ifadeleri yasaktir.
Resmî stage varliklari icin `studio/production/verified-assets.json` kayitlari **gercek SHA** ile eklenir. Sadece JSON kaydi veya fotograf dosyasina rig denmesi yeterli degildir. 
Producere teslim: hangisinin eksik oldugu; kanit; harcama; sonraki teknik gercek is.

## Mevcut makine sinirlari (2026-11-08)
- Nvidia CUDA, Blender CLI veya yerel GPU tabanli gorsel/3D karakter kurulumunun mevcut oldugu dogrulanmadi.
- OpenMontage skill dokumani ve Cline tek basina yeni mesh/rig olusturmaz.
- Hugging Face ZeroGPU denemesi ucretsiz kotaya takildi.
- Profesyonel 3D/karakter hareketi testini gercek olarak gostermek icin model/rig/animasyon uretim araci ve varliklar gerekiyor.
