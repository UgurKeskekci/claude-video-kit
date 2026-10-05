# Teknik tarifler — ölçülerek bulunanlar

Buradaki her madde bir işte gerçekten karşılaşılıp ölçülerek çözüldü. Yeni bir tuzak ölçtüysen
buraya ekle; bir sonraki iş sıfırdan başlamasın.

## Motor seçimi

| | PIL + `kit/murekkep.py` (bu skill) | Remotion (`x-animasyon` skill'i, `remotion/`) |
|---|---|---|
| En iyi | el çizimi/mürekkep, karakter, parçacık, yığın, çok sayıda nesne, tek sahne | tipografi ağırlıklı hareketli grafik: başlık, sayaç, sütun, karşılaştırma, liste |
| Kurulum | yok (numpy + Pillow + ffmpeg) | Node 18+, `cd remotion && npm install` |
| Hız (M1 Pro) | 17,7 sn 4:5 video ~1-2 dk | 27 sn 1080p60 ~1 dk |
| Ses | `kit/sentez.py`, aynı zaman programından | `x-animasyon/araclar/ses.py`, aynı sahne listesinden |

Karar kuralı: **çizim, karakter ya da fizik varsa PIL**; sayı, yazı ve veri anlatıyorsa
`x-animasyon`.

**Sürekli dünya:** sahneler kesmeyle değil tek bir yolda kamera kaydırarak bağlanıyorsa
(10 dönem, tek zaman yolu) sahne sayısı fazla olsa da PIL yeter; kamera geçişin kendisidir.
Ölçüldü: 62,5 sn 1080p böyle bir video ~5 dk'da render oldu.

## Zaman programı — TEK kaynak

Her şey `program()` gibi tek bir fonksiyondan çıkar: olay listesi (t, tür, konum, tohum).
Görüntü ve ses AYNI listeyi okur, senkron hiç kaymaz. Rastgelelik
`np.random.default_rng(sabit)`: aynı kare her render'da aynı çıkar, düzeltme turlarında iki
sürüm kare kare karşılaştırılabilir. Örnek: `ornekler/animasyon-bir-hafta/anim.py::program`,
`ses.py` aynı modülü okur.

## Kompozisyon

- Sahneyi kendi koordinatında çiz, `Kalem(d, kare, s, sc, ox, oy)` ile tuvale oturt. Örnekteki
  ilk sürümde sahne 4:5 tuvalin üst %70'indeydi; tek satırla (sc=1.1, oy=99) düzeldi.
- Başlık/sayaç **sahne dışı** (`yazi(..., sahne=False)`): kompozisyon değişince yeri oynamasın.
- Uçan/hareketli nesneler başlık bandına **girmeden söner** (y < 320'de ölçek -> 0). Girerse
  metni örter, hikâyeyi taşıyan cümle okunmaz.
- Rastgele yığında boşluk kalır. Bir şeyi GÖMMEK gerekiyorsa o bölgeye ayrıca "son kat" koy
  (örnekte baş bölgesine 34 kart); yoksa gömülen şey aralıktan görünür.
- Bir öğe bir şeyin "içinden çıkıyorsa" (yığından uzanan kol) dibini, üstüne çizilen nesneyle ört.
- **Dünya içi yazı kamera ölçeğiyle büyür** (`olcekli_font`), ekran yazısı (yıl, cümle) sabit
  kalır. Sabit boyda kalan dünya yazısı kamera geri çekilince kenardan taşıyordu.
- **Kapanış dizilimi:** her dönemin ikonu kendi `Kalem`'iyle küçültülüp tek sıraya dizilir.
  Bütün dünyayı sığdırmak için kamerayı 0,12'ye indirmek ikonları toz gibi gösteriyordu.
- Kâğıt renginde "solan" yazı dokunun üstünde hayalet gibi görünür: alfa ~0 iken HİÇ çizme.
- Başlık bandının altına inen nesne DÜŞEREK girmesin (her denemede alt yazıya girdi); yandan
  kayarak girsin. Döndürerek oturtmak da olmadı: PIL poligonu döndürür, içindeki yazıyı döndürmez.

## Karakter

`kit/murekkep.py::Iskelet` — ileri kinematik, açılar derece (0 = aşağı, + = ileri).
Diz GERİ (-), dirsek İLERİ (+) bükülür. `yuru(faz)`: sinüs uyluk, geride diz bükümü, kollar ters.
**Kalça adım açıldıkça iner** (bacak · (1 - cos açı)); inmezse 28°'de basan ayak 19 px havada
kalıyordu. Kalan kayma ±7 px (bükük ön diz). Pozlar arası `poz_karistir(a, b, u)` (ease_io).
Kostüm/saç/yüz `ciz(yuz=fn)` ile eklenir.

- **Oturma/kalkma ara pozunda kalçayı ayaktan hesapla:** `poz_karistir` oturuştan ayağa geçerken
  ayağı zeminin altına sokuyordu. Her karede kalçayı en alttaki ayak zemine değecek kadar kaydır;
  kalkarken kalça oturan adamın ayaklarının üstüne gelir.
- **El bir hedefe gidecekse (klavye, fincan, ağız) iki kemikli IK** kullan (kosinüs teoremi,
  dirsek aşağıda); açıyı elle vermek gövde eğilince eli kaçırıyor. Önce erişimi ölç: bir işte
  omuz-klavye arası 215 px, kol 150 px çıktı, eller havada kaldı; karakter masaya yaklaştırıldı.
- Iskelet yalnız sağa bakar; sola yürütmek için noktaları kalça ekseninde aynala (ayak çizgisi
  dahil).

## Geçişler

Kit'te hazır geçiş kütüphanesi yok; gerekince yaz, buraya ekle. Çok sahneli işte en az şunlar
lazım olur: **iris** (daire açılır/kapanır), **perde** (yatay silme + parlak kenar), **itme**
(sahne yana kayar), **eşleşen kesme** (bir nesne sonraki sahnenin nesnesine dönüşür),
**ışık** (beyaza/siyaha soluş). Geçiş 0,4-0,8 sn; çıkış girişten biraz uzun olsun.

- **Perde iki sahnenin yazısını harf harf karıştırır** (ESKİDEN + ŞİMDİ, perde ortasında
  "ŞİKİDEN" okundu): çıkan sahnenin çapa ve altyazısını perdeden hemen önce (~0,2 sn) söndür.
- Perdenin ortasını, whoosh tepesini ve yeni bölümün ilk akorunu AYNI vuruşa koy.

## Metin

- Yazı kaynatılmaz (titremez), ölçek animasyonu verilmez: piksel ızgarasına yuvarlanan ölçek
  her karede metni titretiyor.
- El yazısı: `fontlar/Caveat.ttf` (Türkçe harfler tam). Font yolu çağıran taraftan verilir:
  `M.font(yol, boy)`.
- Emoji fontlarda yok — çizerek ya da hiç.
- Cümle kısa: sahne başına tek satır, 3-7 kelime. Espriyi görüntü taşır, metin çerçeveler.
- Türkçede `str.upper()` kullanma: `"i".upper()` "I" verir, "İ" değil. Büyük harf gerekiyorsa
  önce `i -> İ`, `ı -> I` çevir.

## Ses (`kit/sentez.py`)

- **Karplus-Strong perdesi:** tel ÜÇGEN çekilir (beyaz gürültüyle bazı notalarda 2.-5. harmonik
  temelden güçlü çıkıyor, perde oktav yukarı duyulabiliyordu); başlangıç DC'si silinir; etkin
  gecikme N - 0,5 örnek (yoksa tizde +32 cent). `denetim.py --perde` ile doğrula.
- **Whoosh yumuşak olmalı:** geniş bant gürültü + ani atak "pıssst" diye tıslıyor. Kit'teki
  `whoosh()` frekansı süpürülen iki kademe bant + çan zarfı; tepe zarfın %45'inde, kesime
  oturtmak için `kesim - 0.45 * sure`'de başlat.
- **Yazma sesi tek tek tuş:** eşit aralıklı tik dizisi "tırrrt" diye duyuluyor. `tus()` +
  `yazma()` insan ritmi (70-140 ms, ara sıra duraksama) verir.
- **Tuş sesinde saf ton olmaz:** eski `tus()` 170-560 Hz sönümlü SİNÜS kullanıyordu; enerjinin
  ~%75'i tek 1/6 oktavda toplanıyor, "bip" gibi yapay duyuluyordu. Şimdiki `tus()` yalnız gürültü
  (tık + plastik gövde + yumuşak dip + sessiz bırakma tıkı, tuştan tuşa renk/seviye farkı); aynı
  ölçümde tek 1/6 oktavın payı ~%10. Boşluk/Enter için `tus(r, bosluk=True)`.
- Kart/öğe girişine "bik bik" pop sesi koyma; ya yumuşak whoosh ya hiç.
- Geçiş/koşu süresi vuruşun katı olsun: koşu 1,4 sn iken varış tiki vuruş dışına düşüyordu;
  1,25 sn (96 BPM'de 2 vuruş) ile oturdu. Durak = 2 ölçü.
- Müzik animasyonun VURUŞLARINA oturtulur: tempo olay zamanlarından seçilir (72 BPM'de 10,0 ve
  20,0 sn ölçü başına denk gelir). Büyük an = tek vuruş + ardından sessizlik.
- Komedi: hızlanan müzik -> **keskin kesim** (`kes()`) -> 1+ sn sessizlik -> tek efekt. En
  güçlü an sessizliktir.
- **Yankıyı kesimden ÖNCE uygula.** `kes()` sonra `yanki()` gelirse kuyruk sessizliğe taşar,
  keskin kesim ~0,6 sn sönümlenmeye döner (ölçüldü: `ornekler/animasyon-bir-hafta` 14,7'de
  -23 dB'den 15,3'te ancak -45 dB'e iniyor). Kesilecek müziği ayrı tamponda yankıla, sonra kes;
  kesimden sonra başlayan müzik başka tamponda kalsın. Düzeltilince kesim sonrası -55 dB.
- Seviye: tek başına video -15 LUFS (X/Reels); altında konuşma olacaksa müzik ve efektler
  konuşmanın belirgin altında (konuşma -14..-16 ise müzik ~ -26).
- "Telifsiz" demek için ses tamamen sentez olmalı. Hazır bir müzik kütüphanesi kullanılacaksa
  lisansını kullanıcı kontrol eder.

## Denetim (`kit/denetim.py`) — izleyemediğin için ÖLÇ

**Önizleme karesini tam render'la aynı komuta zincirleme.** Bak, SONRA render et; zincirlenince
kare görülmeden 5 dk'lık render bitiyor ve düzeltme bir render daha yiyor.

1. `--sayfa`: temas sayfası; kompozisyon, çakışma, okunurluk.
2. `--lufs`: entegre ses yüksekliği ve gerçek tepe hedefte mi.
3. `--ses`: 0,5 sn dilimlerde dB; plan edilen sessizlik ve vuruş yerinde mi.
4. `--gecis --bpm N`: görsel geçişler müzik ızgarasına oturuyor mu.
5. Karakter/rig değiştiyse: poz dizisi (yürüme döngüsü) tek görselde.

`--gecis --bpm` ızgarayı t=0'dan sayar: müziği ortada başlayan bölümün ilk vuruşunu vuruşun
katına koy (96 BPM'de 6,875 = 11 × 0,625; 7,0'da başlayınca her şey 0,2 vuruş kaymış ölçüldü).
Perdede ölçülen tepe perdenin ortası değil en büyük kontrast değişimidir (koyu pencerenin
silindiği an); kadraja giren/çıkan karakter de "geçiş" sayılır. Sapmayı bunları ayırarak oku.

Kullanıcıya "izle, dinle" demeden önce bunlar geçmeli; geçmeyenler söylenir.

## Çıktı

| Hedef | Boyut | fps | Not |
|---|---|---|---|
| X | 1080×1350 ya da 1920×1080 | 30 | `-movflags +faststart` (kit'in `yaz_mp4`'ü ekliyor) |
| Reels/Shorts | 1080×1920 | 30 | alt ~520 px ve sağ x > 900 arayüz |
| YouTube arası | videonla aynı (1920×1080 / 2560×1440) | 30 | şeffaf gerekiyorsa ProRes 4444 (`-c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le`), değilse h264 |

Çalışma dosyaları ve çıktı `calisma/<ad>/` altına; kaynak kod (`anim.py`, `ses.py`) da orada
ya da kalıcı bir örnekse `ornekler/<ad>/` altında.
