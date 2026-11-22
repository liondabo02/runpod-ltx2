# -*- coding: utf-8 -*-
"""S01E001 'Merhaba, Bizim Aile! — Parkın Kuralları' — elle yazılmış senaryo verisi (480 sn, 12 sahne, sabit süreler).
Kurallar: bebekler (medine, ramin) konuşmaz; kaan (1 yaş) en çok 2 kelime; salih/berzan/aras en çok 4 kelime; aden/emos en çok 6 kelime.
Replik biçimi 'karakter_id: cümle'. Şiddet/korku yok; Fatoş'un geçmişine atıf yok."""

TITLE = "Merhaba, Bizim Aile! — Parkın Kuralları"
EPISODE_ID = "S01E001"
TARGET_MS = 480000

# sahne: (id, loc, start_s, end_s, başlık, ışık, gündüz_saati, katılımcılar, mekân_dışı_ses/müzik notu, aksesuar, performans notu)
# shot: (dur_s, çerçeve, kamera hareketi, [kim], başlangıç_pozu, bitiş_pozu, eylem, [satırlar], geçiş)
SCENES = [
 dict(id="sc01", loc="A", s=0, e=35, title="Evde sabah", light="sabah güneşi doğu penceresinden, sıcak, gün 08:30",
  cast=["aden", "kaan"], props=["uçurtma", "sehpa", "battaniye"],
  act="Aden uyanık ve enerjik; Kaan emekleyerek ona yetişmeye çalışır. Çocukların küçük, gerçek tepkileri: göz teması, bekleme, el uzatma.",
  shots=[
   (7, "geniş", "yavaş içeri itme", ["aden", "kaan"], "Aden battaniyede oturur, Kaan kanepe altından görünür", "Aden ayağa fırlar, Kaan emekler", "Güneş ışığı salonu doldurur, Aden gerinir ve uçurtmasını fark eder", ["aden: Günaydın! Bugün park var!"], "yumuşak açılış"),
   (7, "orta", "sabit, hafif sağa kayış", ["aden"], "Aden uçurtmayı alır", "Uçurtmayı havaya kaldırır, zıplar", "Aden uçurtmayı gösterir ve izleyiciye elini sallar", ["aden: Ben Aden. Üç yaşındayım."], "kesme"),
   (7, "yakın (alçak açı)", "Kaan'ı takip", ["kaan"], "Kaan dört ayak üstünde", "Kaan oturur, kahkaha atar", "Kaan emekleyerek kameraya yaklaşır, durur, başını yana eğer", ["kaan: Aaa!"], "kesme"),
   (7, "orta", "sabit", ["aden", "kaan"], "Aden Kaan'a bakar, çömelir", "Aden Kaan'ın elini tutar", "Aden kardeşini tanıtır; Kaan Aden'in parmağını yakalar", ["aden: Bu da kardeşim Kaan.", "kaan: Abla!"], "kesme"),
   (7, "geniş", "arkadan yavaş geri çekilme", ["aden", "kaan"], "İkisi birlikte kapıya bakar", "Aden kapıya koşar, Kaan emekler", "Mutfaktan çağrı gelir; çocuklar sese doğru gider", ["esra: Kahvaltı hazır, gelin bakalım!"], "mutfağa geçiş (ses köprüsü)"),
  ]),
 dict(id="sc02", loc="B", s=35, e=75, title="Esra ve Ahmet", light="sabah, mutfak penceresinden yumuşak ışık, gün 08:35",
  cast=["esra", "ahmet", "aden", "kaan"], props=["piknik sepeti", "bebek arabası", "elma", "su şişesi"],
  act="Esra piknik sepetini hazırlar, Ahmet bebek arabasının tekerini kontrol eder. Aileyi aralarındaki sıcak dille tanıtırız.",
  shots=[
   (8, "orta", "sol kayış", ["esra", "aden"], "Esra sepeti açar, Aden yanında", "Esra elmayı Aden'e uzatır", "Esra kendini tanıtır, Aden annesine sarılır", ["esra: Merhaba! Ben Esra, Aden'in annesiyim.", "aden: Annem!"], "kesme"),
   (8, "orta", "sabit", ["ahmet"], "Ahmet bebek arabasının tekerini çevirir", "Ahmet doğrulur, başparmak gösterir", "Ahmet gülümseyerek tekerleği sağlamlaştırır", ["ahmet: Ben de Ahmet, babalarıyım. Tekerler tamam!"], "kesme"),
   (8, "yakın", "Kaan'a odaklanma", ["kaan", "ahmet"], "Kaan Ahmet'in ayağına tutunur", "Ahmet Kaan'ı kucağına alır", "Kaan babasına uzanır; baba kucaklar", ["kaan: Baba!"], "kesme"),
   (8, "geniş", "yavaş yukarı kaldırma", ["esra", "ahmet", "aden", "kaan"], "Aile masada dağınık", "Aile sepet etrafında toplanır", "Esra herkese suyu verir, Ahmet sepeti kapatır", ["esra: Bugün parkta hepimiz kurallara uyacağız.", "aden: Ben biliyorum!"], "kesme"),
   (8, "orta", "sabit", ["aden", "esra", "ahmet"], "Aden ellerini beline koyar", "Aden kapıya yürür", "Aden ebeveynlerini kapıya çağırır, Ahmet sepeti kaldırır", ["aden: Hadi gidelim!", "ahmet: Önce teyzeye uğrayalım."], "koridora geçiş"),
  ]),
 dict(id="sc03", loc="C", s=75, e=125, title="Esma ve Harun", light="sabah, koridor penceresinden tatlı ışık, gün 08:45",
  cast=["esma", "harun", "aden", "kaan", "esra", "ahmet"], props=["ayakkabılık", "çanta", "güneş gözlüğü"],
  act="Esma hamile, zarif ve rahat; Harun uzun boylu, sakin liderdir. Aden teyzesinin karnını nazikçe okşar. Esma'ya özen gösterilir.",
  shots=[
   (8, "geniş", "sabit", ["esma", "harun"], "Esma ayakkabılığın yanında, Harun çantayı toplar", "Esma gülümseyerek kapıya döner", "Harun ve Esma misafirleri koridorda karşılar", ["esma: Hoş geldiniz! Ben Esma, Aden ve Kaan'ın teyzesiyim."], "kesme"),
   (8, "orta", "sağa kayış", ["harun"], "Harun çantayı omuzlar", "Harun elini kalbine koyar", "Harun uzun boyuyla eğilir, çocuklara selam verir", ["harun: Ben Harun, enişteniz. Bugün park lideriyim!"], "kesme"),
   (8, "yakın", "sabit", ["aden", "esma"], "Aden Esma'nın karnına bakar", "Aden elini nazikçe karnına koyar", "Aden teyzesinin karnını yavaşça okşar, Esma gülümser", ["aden: Teyze, içinde bebek var mı?", "esma: Evet, beş aylık."], "kesme"),
   (9, "orta", "sabit", ["kaan", "harun"], "Kaan Harun'un bacağına tutunur", "Harun Kaan'ı yukarı kaldırır", "Kaan Harun'a bakar ve kıkırdar; Harun onu omzuna oturtur", ["kaan: Hop!", "harun: Hop! Kaan uçuyor."], "kesme"),
   (9, "geniş", "arkadan takip", ["harun", "esma", "esra", "ahmet", "aden", "kaan"], "Herkes koridorda", "Herkes kapıdan çıkar", "Harun herkesi topluyor; Esma çantasını alır; hep birlikte çıkarlar", ["harun: Herkes hazır mı? Parka!", "esma: Hadi bakalım!"], "dış mekâna geçiş"),
   (8, "orta (kapı eşiği)", "sabit", ["aden", "kaan"], "Çocuklar kapıda", "Aden el sallar", "Aden ve Kaan izleyiciye el sallar; kapı yavaşça kapanır", ["aden: Bizimle gelin!"], "kapı kapanışıyla geçiş"),
  ]),
 dict(id="sc04", loc="C", s=125, e=170, title="Veysel, Öznur, Salih, Medine", light="sabah, giriş kapısında dışarıdan gelen ışık, gün 09:00",
  cast=["veysel", "oznur", "salih", "medine", "aden", "harun"], props=["bebek taşıma koltuğu", "oyuncak ayı", "çiçekli kese"],
  act="Zil çalar; komşu aile gelir. Medine (2 aylık) taşıma koltuğunda uyur, yalnız ses çıkarır (konuşmaz); Öznur onu tanıtır. Salih kısa cümlelerle konuşur.",
  shots=[
   (9, "geniş", "sabit", ["veysel", "oznur", "salih"], "Kapı açılır, aile dışarıda", "Veysel içeri adım atar", "Kapıda Veysel, Öznur ve Salih; Harun karşılar", ["veysel: Günaydın! Ben Veysel.", "harun: Hoş geldiniz!"], "kesme"),
   (9, "orta", "sağa kayış", ["oznur", "medine"], "Öznur taşıma koltuğunu gösterir", "Öznur koltuğu hafifçe sallar", "Öznur uyuyan bebeği tanıtır; Medine hafif bir ses çıkarır", ["oznur: Ben Öznur. Bu da bebeğimiz Medine, iki aylık.", "medine: [ince bebek mırıltısı]"], "kesme"),
   (9, "yakın", "sabit", ["salih", "aden"], "Salih ayıyı sıkı tutar", "Salih ayıyı Aden'e uzatır", "Salih oyuncağını paylaşır; Aden bakar ve gülümser", ["salih: Ben Salih. İki!", "aden: Merhaba Salih!"], "kesme"),
   (9, "orta", "sabit", ["veysel", "harun"], "Veysel güler, mavi gözlerini kırpar", "Veysel ve Harun el sıkışır", "Erkekler selamlaşır; Veysel koltuğu kaldırır", ["veysel: Hadi, park bizi bekliyor!"], "kesme"),
   (9, "geniş", "geri çekilme", ["veysel", "oznur", "salih", "aden", "harun"], "Grup kapıda", "Grup yola koyulur", "İki aile birlikte sokağa çıkar; Salih Aden'in elini tutar", ["oznur: Salih, elini bırakma."], "sokağa geçiş (güneşli dış)"),
  ]),
 dict(id="sc05", loc="D", s=170, e=215, title="Davut, Fatoş, Emoş, Berzan, Aras, Ramin", light="sabah, park girişinde açık gökyüzü, gün 09:30, güneş doğu-güneydoğuda",
  cast=["davut", "fatos", "emos", "berzan", "aras", "ramin", "aden", "kaan", "harun"], props=["bebek arabası (çift)", "tavşan peluş", "oyuncak araba", "park giriş kapısı"],
  act="Davut iri, neşeli ve şakacı; Fatoş doğal ve rahat. İkizler (Berzan, Aras) birbirine benzer ama davranışları farklıdır. Ramin (1 aylık) yalnız nefes ve mırıltı.",
  shots=[
   (9, "geniş", "sabit", ["davut", "fatos", "emos", "berzan", "aras", "ramin"], "Aile park kapısında", "Davut el sallar", "Davut ailesiyle girişte bekliyor; kapı kemeri görünür", ["davut: Selam millet! Biz geldik!"], "kesme"),
   (9, "orta", "sol kayış", ["davut", "fatos"], "Davut ellerini beline koyar", "Davut gülerek omuzlarını silkelemeler", "Davut kendini tanıtır; Fatoş rahat bir gülümsemeyle yanına gelir", ["davut: Ben Davut, kocaman bir babayım!", "fatos: Ben Fatoş. Hoş geldiniz!"], "kesme"),
   (9, "orta", "sabit", ["emos", "aden"], "Emos ellerini beline koyar", "Emos Aden'e koşar", "Emos dört yaşında, kendinden emin; Aden'le el çırparlar", ["emos: Ben Emoş. Dört yaşındayım!", "aden: Emoş!"], "kesme"),
   (9, "yakın", "ikiz çifte odaklanma", ["berzan", "aras"], "İkizler yan yana; Berzan göz kırpar, Aras peluşa sarılır", "Berzan başparmak, Aras gülümser", "İkizlerin farklılığı: Berzan hareketli, Aras sakin; Fatoş tanıtır", ["fatos: Bunlar ikizlerimiz Berzan ve Aras.", "berzan: Ben Berzan!", "aras: Aras."], "kesme"),
   (9, "orta", "sabit", ["fatos", "ramin"], "Fatoş çift arabanın yanında", "Fatoş battaniyeyi düzeltir", "Fatoş uyuyan Ramin'i tanıtır; Ramin nefes alır, hafif bir ses çıkarır", ["fatos: Bu da Ramin, bir aylık.", "ramin: [yeni doğan nefes ve minik ses]"], "parka geçiş"),
  ]),
 dict(id="sc06", loc="F", s=215, e=255, title="Parkın kuralları", light="sabah sonu, güneş yükselmiş, gölgeler kısa, gün 10:00",
  cast=["harun", "esma", "esra", "ahmet", "veysel", "oznur", "davut", "fatos", "aden", "kaan", "salih", "emos", "berzan", "aras", "medine", "ramin"], props=["kurallar tabelası", "dört işaret panosu"],
  act="Harun tabelayı gösterir; çocuklar tabeladaki resimleri tekrar eder. Dört kural: çöp kutusu, çiçekler, kaydırakta sıra, işaretler.",
  shots=[
   (8, "geniş", "yavaş içeri itme", ["harun", "aden", "emos", "salih", "berzan", "aras"], "Çocuklar tabelaya doğru yürür", "Çocuklar tabelanın önünde", "Park kurallar tabelası görünür; Harun çocukları tabelanın önüne toplar", ["harun: Bakın, parkın kuralları!"], "kesme"),
   (8, "orta", "sabit", ["harun", "aden"], "Harun tabelayı gösterir", "Aden tabelaya el sürmeden parmağıyla işaret eder", "Harun birinci ve ikinci kuralı anlatır; Aden tekrar eder", ["harun: Bir: Çöpler çöp kutusuna!", "aden: Çöp kutusu!"], "kesme"),
   (8, "yakın", "sağa kayış", ["emos", "salih"], "Emos tabelaya bakar", "Salih ellerini çırpar", "İki: çiçekleri koparmayız; Emos ve Salih tepki verir", ["harun: İki: Çiçeklere bakarız, koparmayız.", "emos: Koparmayız!"], "kesme"),
   (8, "orta", "sabit", ["berzan", "aras", "kaan"], "Berzan zıplar, Aras Kaan'a bakar", "Aras Kaan'ın elini tutar", "Üç: kaydırakta sıra; Berzan sabırsız, Aras sakin", ["harun: Üç: Kaydırakta sıra bekleriz.", "berzan: Sıra!"], "kesme"),
   (8, "geniş", "hafif yukarı kayış", ["harun", "esma", "davut", "fatos", "veysel", "oznur", "esra", "ahmet"], "Yetişkinler çocukların arkasında", "Yetişkinler başlarıyla onaylar", "Dört: işaretlere bakarız; herkes birlikte alkışlar", ["harun: Dört: İşaretlere bakar, güvenli yoldan yürürüz.", "davut: Yaşasın kurallar!"], "kesme"),
  ]),
 dict(id="sc07", loc="G", s=255, e=300, title="Çöpler çöp kutusuna", light="öğleye doğru, güneş doğudan yükselmiş, gün 10:20",
  cast=["berzan", "aras", "aden", "davut", "harun", "emos"], props=["çöp kutusu", "elma sapı", "meyve suyu kutusu", "çöp torbası"],
  act="Berzan elma sapını çimene atar; Aras onu fark edip alır ve çöp kutusuna götürür. Davut'un esprili 'çöp avcısı' oyunu.",
  shots=[
   (9, "geniş", "sabit", ["berzan", "aden"], "Berzan elma yer", "Berzan sapı fırlatır", "Berzan elmayı bitirir ve sapı çimene atar", ["berzan: Bitti!"], "kesme"),
   (9, "orta", "Aras'ı takip", ["aras"], "Aras peluşa sarılı oturur", "Aras kalkar ve sapı alır", "Aras sapı fark edip eğilir, alır; çöp kutusuna bakar", ["aras: Çöp. Kutu."], "kesme"),
   (9, "yakın", "sabit", ["aras", "berzan"], "Aras sapı tutar", "Aras sapı kutuya atar, Berzan bakar", "Aras sapı çöp kutusuna atar; Berzan utanarak güler", ["berzan: Pardon!", "aras: Çöp kutusu!"], "kesme"),
   (9, "orta", "sol kayış", ["davut", "aden", "emos"], "Davut çömelir", "Davut kutuya çöp atar", "Davut 'çöp avcısı' olur; çocuklar kutu etrafında toplanır", ["davut: Ben çöp avcısıyım! Hop, kutuya!", "aden: Ben de!"], "kesme"),
   (9, "geniş", "geri çekilme", ["harun", "aden", "emos", "berzan", "aras", "davut"], "Çocuklar çöp toplar", "Çocuklar kutu önünde sıralanır", "Temiz yürüyüş alanı; Harun başparmak gösterir", ["harun: Aferin! Park tertemiz."], "kesme"),
  ]),
 dict(id="sc08", loc="H", s=300, e=340, title="Çiçekleri korumak", light="öğle öncesi, çiçeklikte yumuşak gölge, gün 10:40",
  cast=["emos", "fatos", "salih", "oznur", "aden", "kaan"], props=["çiçeklik", "kelebek", "kırmızı laleler"],
  act="Emos çiçek koparmak ister; Fatoş çömelip 'bakarız, koklarız, koparmayız' der. Kelebek gelir, çocuklar sessizce izler.",
  shots=[
   (8, "geniş", "sabit", ["emos", "aden", "salih"], "Çocuklar çiçekliğe yaklaşır", "Emos elini uzatır", "Çiçeklik renklidir; Emos kırmızı laleye uzanır", ["emos: Güzel çiçek!"], "kesme"),
   (8, "orta", "sabit", ["fatos", "emos"], "Fatoş Emos'un yanına çömelir", "Fatoş Emos'un elini nazikçe tutar", "Fatoş sakin ve şefkatli bir tonda açıklar", ["fatos: Bakalım, koklayalım. Ama koparmayalım."], "kesme"),
   (8, "yakın", "sabit", ["emos", "salih"], "Emos eğilir", "Emos ve Salih lalenin yanında durur", "Emos çiçeği koklar; Salih aynısını yapar", ["emos: Mis gibi!", "salih: Mis!"], "kesme"),
   (8, "orta", "yavaş sağa", ["kaan", "oznur"], "Kaan çimende oturur", "Kaan kelebeğe uzanır", "Kelebek Kaan'ın önünde uçar; Öznur sessizce bekler", ["kaan: Kelebek!", "oznur: Sessiz, ürkütmeyelim."], "kesme"),
   (8, "geniş", "geri çekilme", ["emos", "fatos", "salih", "oznur", "aden", "kaan"], "Çocuklar çiçeklik çevresinde", "Çocuklar çiçekliği geride bırakır", "Kelebek uçar gider; çiçekler yerinde kalır", ["aden: Çiçekler yerinde!"], "kesme"),
  ]),
 dict(id="sc09", loc="I", s=340, e=385, title="Kaydırakta sıra", light="öğle, güneş yüksek, kısa gölgeler, gün 11:00",
  cast=["aden", "berzan", "salih", "emos", "harun", "kaan", "esra"], props=["kaydırak", "merdiven", "sıra işareti"],
  act="Berzan ve Salih öne atlamak ister; Harun 'sıra' oyunu kurar. Aden ilk, Emos sonra; Kaan alt tarafta bekler ve kaydırağın dibinde kucaklanır.",
  shots=[
   (9, "geniş", "sabit", ["berzan", "salih", "aden", "emos"], "Çocuklar merdiven önünde karışık", "Berzan öne doğru atılır", "Çocuklar kaydırağa koşar; Berzan sıra bozmak ister", ["berzan: Ben ilk!"], "kesme"),
   (9, "orta", "sabit", ["harun", "berzan"], "Harun yavaşça önünü keser", "Berzan durur", "Harun nazikçe durdurur ve sıra işaretini gösterir", ["harun: Dur bakalım. Sıra nerede?"], "kesme"),
   (9, "orta", "sol kayış", ["aden", "emos", "salih", "berzan"], "Çocuklar bir çizgide", "Çocuklar tek sıra olur", "Çocuklar sıraya girer; Aden başa geçer", ["aden: Ben başta!", "emos: Ben arkada."], "kesme"),
   (9, "yakın", "kaydıraktan aşağıya", ["aden"], "Aden kaydırak tepesinde", "Aden kaydıraktan aşağı inip kollarını açar", "Aden kaydırır, yüzü neşeli; alt tarafta Kaan bekler", ["aden: Yuppi!"], "kesme"),
   (9, "geniş", "geri çekilme", ["salih", "berzan", "emos", "kaan", "esra"], "Sıra devam eder", "Sıradaki çocuk kaydırağa çıkar", "Sırayla herkes kayar; Esra Kaan'ı kucağına alır", ["berzan: Sıra benim!", "esra: Aferin, güzel bekledin."], "kesme"),
  ]),
 dict(id="sc10", loc="J", s=385, e=425, title="İşaretler ve güvenli yollar", light="öğleye yakın, açık gökyüzü, gölgeler kısa, gün 11:20",
  cast=["davut", "aden", "ahmet", "esma", "harun", "emos", "berzan"], props=["bisiklet yolu işareti", "yaya yolu işareti", "çocuk bisikleti", "zil"],
  act="Davut yanlışlıkla bisiklet yoluna girer; Aden işaretleri okuyup 'yaya yolu bu taraf' der. Harun ve Ahmet güvenli yürüyüşü gösterir.",
  shots=[
   (8, "geniş", "sabit", ["davut", "aden"], "Davut yola yürür", "Davut bisiklet yoluna girer", "Yaya yolu ile bisiklet yolu yan yana; Davut yanlış tarafta", ["davut: Ne güzel yol!"], "kesme"),
   (8, "orta", "sabit", ["aden", "davut"], "Aden işaretlere bakar", "Aden Davut'un elini tutar", "Aden işareti gösterir; Davut hemen çekilir", ["aden: Amca, bu bisiklet yolu!"], "kesme"),
   (8, "yakın", "sağa kayış", ["ahmet", "emos", "berzan"], "Ahmet çocukları yaya yoluna alır", "Çocuklar yaya yolunda sıralı", "Ahmet işareti gösterir; çocuklar işareti tekrar eder", ["ahmet: Yaya yolu yürüyenler için.", "emos: Yürüyenler!"], "kesme"),
   (8, "orta", "arkadan takip", ["esma", "harun"], "Harun Esma'nın elini tutar", "Çift güvenli yolda yürür", "Harun Esma'ya destek olur; birlikte kuralı gösterirler", ["harun: Güvenli yol, güvenli adım."], "kesme"),
   (8, "geniş", "yükselen", ["davut", "aden", "emos", "berzan", "ahmet", "harun", "esma"], "Grup iki yolun kenarında", "Grup yaya yolunda ilerler", "Bir bisikletli zil çalarak geçer; herkes yaya yolunda güvende", ["davut: Zil sesi duydum, kenardayım!"], "kesme"),
  ]),
 dict(id="sc11", loc="E", s=425, e=460, title="Öğrendiklerimizi tekrarlıyoruz", light="öğle, aile alanında açık gölge, gün 11:40",
  cast=["harun", "aden", "emos", "salih", "berzan", "aras", "kaan", "esra", "fatos"], props=["piknik örtüsü", "dört işaret panosu", "meyve tabağı"],
  act="Piknik örtüsünde Harun kuralları çocuklarla tekrarlar; her kural küçük bir hareketle (çöp atma, koklama, sıra, işaret) gösterilir.",
  shots=[
   (7, "geniş", "sabit", ["harun", "aden", "emos", "salih", "berzan", "aras"], "Çocuklar örtüde otururlar", "Harun elini kaldırır", "Piknik örtüsünde tekrar oyunu başlar", ["harun: Hadi, kuralları tekrar edelim!"], "kesme"),
   (7, "orta", "sabit", ["aden", "harun"], "Aden elinde çöp tutar", "Aden çöpü kutuya atma hareketi yapar", "Aden çöp kutusu hareketini gösterir", ["aden: Çöp kutusuna!"], "kesme"),
   (7, "orta", "sabit", ["emos", "salih"], "Emos çiçek koklama hareketi", "Salih koklama hareketini taklit eder", "İki çocuk çiçek koklar, koparmaz", ["emos: Koklarız!", "salih: Mis!"], "kesme"),
   (7, "orta", "sağa kayış", ["berzan", "aras", "kaan"], "Çocuklar sıra olur", "Kaan en önde parmağını kaldırır", "Sıra bekleme hareketi; Kaan öne geçer ve eller havada", ["berzan: Sıra!", "aras: Bekle.", "kaan: Ben!"], "kesme"),
   (7, "geniş", "geri çekilme", ["harun", "aden", "emos", "salih", "berzan", "aras", "kaan", "esra", "fatos"], "Grup işaretlere bakar", "Grup birlikte alkışlar", "Herkes dört işareti birlikte gösterir; alkış", ["harun: Süper! Hepsini biliyorsunuz.", "esra: Aferin bizim çocuklara!"], "kesme"),
  ]),
 dict(id="sc12", loc="E", s=460, e=480, title="Aile finali", light="öğle sonrası, sıcak ışık, gün 12:00",
  cast=["aden", "kaan", "esra", "ahmet", "esma", "harun", "veysel", "oznur", "salih", "medine", "davut", "fatos", "emos", "berzan", "aras", "ramin"], props=["piknik örtüsü", "uçurtma", "balonlar"],
  act="Bütün aile (16 kişi) birlikte; bebekler kucakta. Sıcak, kutlama havası; Aden uçurtmayı kaldırır.",
  shots=[
   (7, "geniş", "yavaş yukarı kaldırma", ["aden", "kaan", "esra", "ahmet", "esma", "harun"], "Aile örtüde dağınık", "Aile toplanır", "Aden ve Kaan'ın ailesi bir araya gelir; Esra Kaan'ı alır", ["aden: Hepimiz buradayız!"], "kesme"),
   (7, "çok geniş", "sabit", ["veysel", "oznur", "salih", "medine", "davut", "fatos", "emos", "berzan", "aras", "ramin"], "Diğer aileler yaklaşır", "Büyük aile fotoğrafı için dizilir", "Tüm aile parkta toplanır; bebekler kucakta görünür", ["davut: Fotoğraf zamanı!"], "kesme"),
   (6, "geniş", "yavaş geri çekilme", ["aden", "kaan", "esra", "ahmet", "esma", "harun", "veysel", "oznur", "salih", "medine", "davut", "fatos", "emos", "berzan", "aras", "ramin"], "Aile fotoğraf pozunda", "Aden uçurtmayı havaya kaldırır; herkes el sallar", "Kapanış: gün ışığında bütün aile el sallar; uçurtma göğe yükselir", ["aden: Güle güle! Yine gelin!", "harun: Parkta görüşürüz!"], "kararma ve başlık"),
  ]),
]

# Sahne ve mekân kimlikleri (park ve ev tutarlılık kuralları)
LOCATIONS = {
 "A": dict(id="env_home_salon_v1", name="Harun ve Esma'nın evi — salon", group="home", ref="studio/canon/(yeni)", notes="Kanepe, sehpa, doğu penceresi, halı"),
 "B": dict(id="env_home_kitchen_v1", name="Aynı ev — mutfak", group="home", notes="Masa, tezgâh, doğu penceresi"),
 "C": dict(id="env_home_entry_corridor_v1", name="Aynı ev — giriş/koridor", group="home", notes="Ayakkabılık, ana kapı, aynı ev düzeni"),
 "D": dict(id="env_park_entrance_v1", name="Park girişi", group="park", notes="Kemer kapı, güney ucu"),
 "E": dict(id="env_park_family_area_v1", name="Park aile buluşma ve dinlenme alanı", group="park", notes="Piknik çimi, bank, büyük ağaç, merkez-batı"),
 "F": dict(id="env_park_rules_sign_v1", name="Kurallar tabelası", group="park", notes="Girişin sağında, ana yolda"),
 "G": dict(id="env_park_trash_walk_v1", name="Çöp kutusu ve yürüyüş alanı", group="park", notes="Ana yol boyunca, tabelanın kuzeyi"),
 "H": dict(id="env_park_flower_bed_v1", name="Çiçeklik", group="park", notes="Doğuda, kırmızı laleler, taş çerçeve"),
 "I": dict(id="env_park_slide_zone_v1", name="Kaydırak bölgesi", group="park", notes="Kuzeydoğuda, tek kaydırak, merdiven, yumuşak zemin"),
 "J": dict(id="env_park_bike_pedestrian_v1", name="Bisiklet ve yaya yolu", group="park", notes="Parkı çevreleyen halka; bisiklet ve yaya şeritleri yan yana"),
}

PARK_GEOGRAPHY = {
 "kuzey": "I (kaydırak) kuzeydoğu, H (çiçeklik) doğu",
 "orta": "E (aile alanı) merkez-batı; G (çöp/yürüyüş) ana yol boyunca",
 "güney": "D (giriş) güney ucu; F (tabela) girişin sağında",
 "çevre": "J (bisiklet/yaya halkası) bütün parkı çevreler",
 "güneş": "Sabah doğu-güneydoğuda (azimut ~110°), yükseklik sahne boyunca 30°→55°; gölgeler batı-kuzeybatıya düşer. Sahneler arasında sabit.",
}

# Karakter -> bölüm kıyafeti (onaylı poster kırpımından okunan, değiştirilemez bölüm kıyafeti)
WARDROBE = {
 "aden": "kobalt tişört, sarı uçurtma, lacivert şort, sarı yıldız toka (sabit), sol yanakta üç çil (sabit)",
 "kaan": "mercan/kırmızı tişört, koyu mavi pantolon, bebeksi oran",
 "esra": "gül kurusu başörtüsü, krem çiçek işlemeli üst",
 "ahmet": "bordo kazak, lacivert yaka",
 "esma": "zeytin yeşili başörtüsü, krem işlemeli elbise, hamile (5 aylık)",
 "harun": "lacivert gömlek, krem iç tişört, omuz çantası, saat, uzun dalgalı saç",
 "veysel": "turkuaz gömlek, kahverengi yelek, mavi gözler, kısa sakal",
 "oznur": "mor başörtüsü, mavi hırka, bordo yelek, sarı çiçek broş",
 "salih": "hardal tişört, yeşil bahçıvan tulum, ayı nakışı",
 "medine": "pembe battaniye, çiçekli bebek tulumu, pembe fiyonk (2 aylık)",
 "davut": "kırmızı gömlek, kahverengi yelek, uzun kıvırcık saç, iri yapı",
 "fatos": "somon hırka, kolsuz bluz, küpe, omuz hizası kestane saç, BAŞÖRTÜSÜZ",
 "emos": "turkuaz bluz, mercan askılı elbise, kısa kahverengi kâhkül saç, kırmızı toka",
 "berzan": "turuncu tişört (araba desenli), lacivert pantolon",
 "aras": "mavi üst, tavşan peluş",
 "ramin": "nane yeşili tulum, ayıcık kulaklı bere, bez kundak (1 aylık)",
}

ROLES = {"aden": "lead", "kaan": "lead", "esra": "mother", "ahmet": "father", "esma": "aunt", "harun": "uncle_by_marriage",
         "veysel": "friend", "oznur": "friend", "salih": "child", "medine": "baby", "davut": "friend", "fatos": "friend",
         "emos": "child", "berzan": "child", "aras": "child", "ramin": "baby"}
ORDER = ["aden", "kaan", "esra", "ahmet", "esma", "harun", "veysel", "oznur", "salih", "medine", "davut", "fatos", "emos", "berzan", "aras", "ramin"]
BABIES = {"medine", "ramin"}
WORD_LIMIT = {"kaan": 2, "salih": 4, "berzan": 4, "aras": 4, "aden": 6, "emos": 6}

# Birbirine fazla benzeyen çiftler için ayrıştırma ÖNERİLERİ (sahip yetkisiyle; onaylı panelin yerine geçmez, onaylı sürüm ayrı kalır)
DIFFERENTIATION = [
 dict(group=["esra", "esma", "oznur"], problem="Üçü de başörtülü, benzer yüz oranı ve ten rengi",
      proposals={"esra": "gül kurusu başörtü, yuvarlak yüz, hafif dolgun yanak, sakin kaşlar; ayırt edici silüet: bol üst",
                 "esma": "zeytin yeşili başörtü, ince oval yüz, uzun kirpikler, hamile silüet; zarif duruş, boyun dik",
                 "oznur": "mor başörtü, keskin çene ve ince burun, hafif sivri çene; sarı çiçek broş, mavi hırka"},
      rule="Üçünün yüz şekli (yuvarlak / ince oval / köşeli oval) ve başörtü rengi sabit kalır"),
 dict(group=["kaan", "salih", "berzan", "aras"], problem="Dört bebek/yürümeye başlayan çocuğun hepsi koyu kıvırcık saçlı",
      proposals={"kaan": "bebeksi oran, ince düz-dalgalı siyah saç, büyük baş; mercan tişört",
                 "salih": "açık kızıl-kestane kıvırcık saç, yuvarlak yanak; yeşil tulum",
                 "berzan": "koyu kıvırcık saç, sol tarafta tek tutam, çene gamzesi; turuncu araba tişörtü; hareketli ifade",
                 "aras": "koyu kıvırcık saç ama daha kısa ve düz kenar, yuvarlak sakin yüz; mavi üst, tavşan peluş"},
      rule="İkizler (Berzan/Aras) benzer kalır; Berzan'ı gamze ve tutam, Aras'ı peluş ve sakin ifade ayırır. Kaan ve Salih ikizlerden saç renk/dokusuyla ayrılır"),
 dict(group=["aden", "emos"], problem="İkisi de kahverengi saçlı kız çocuk",
      proposals={"aden": "koyu kahverengi dalgalı uzun saç, sarı yıldız toka, sol yanakta üç çil",
                 "emos": "kısa küt kesim kahverengi saç + kâhkül, kırmızı toka, çilsiz yanak, turuncu/turkuaz renkler"},
      rule="Aden: uzun dalgalı + yıldız + çil; Emoş: küt kesim + kâhkül + kırmızı toka"),
 dict(group=["ahmet", "veysel"], problem="İki baba tipi yetişkin",
      proposals={"ahmet": "ince yapı, koyu gözler, alın geride, saç ince, sakalsız; bordo kazak",
                 "veysel": "dolgun yapı, mavi gözler, açık kestane saç ve kısa sakal; turkuaz gömlek"},
      rule="Siluet (ince/dolgun) ve göz rengi ayırır"),
 dict(group=["harun", "davut"], problem="İkisi de uzun saçlı erkek",
      proposals={"harun": "uzun boylu, fit, sakallı, dalgalı uzun saç geriye; lacivert gömlek",
                 "davut": "iri, geniş vücutlu, dolgun yüz, kıvırcık uzun saç; kırmızı gömlek"},
      rule="Vücut tipi ve yüz dolgunluğu kesin ayırır; Harun fit ve uzun, Davut iri ve geniş"),
 dict(group=["medine", "ramin"], problem="İki bebek uyur pozda, benzer",
      proposals={"medine": "pembe fiyonk, pembe battaniye, 2 aylık; uzun kirpik",
                 "ramin": "nane yeşili ayıcık kulaklı bere, 1 aylık; daha küçük, kırmızı yüz"},
      rule="Renk kodu (pembe/nane) ve aksesuar (fiyonk/bere) ayırır"),
]
