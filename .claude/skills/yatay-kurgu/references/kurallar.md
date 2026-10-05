# Kesim kuralları ve ölçümleri

Buradaki her kural gerçek kayıtlarda ölçülerek kondu. Çoğu derleme hatası vermeyen hatalara
karşı: bozulduğunda video yine çıkar ama yanlış kesilir. Mekanik olanlar
`tests/test_kesim.py` ile kilitli; sayıyı değiştirirsen testi de bilerek değiştir.

## Kararı ses verir, kelimeler değil

**Kelimesiz aralık sessizlik demek değildir.** Whisper art arda tekrarlanan cümleleri
atlayabiliyor. Ölçüldü: kelimesiz bir aralık −24,2 dB çıktı (konuşma −23,5 dB, gerçek
sessizlik −91 dB). Kelime yokluğuna güvenen ilk sürüm 1 dk 12 sn gerçek konuşmayı siliyordu.
Bu yüzden konuşma parçaları 10 ms'lik ses zarfından kurulur; kelimeler yalnızca "bu bölge
tutulacak mı" sorusuna cevap verir.

**Whisper damgası kayar.** Başlangıcı çoğu zaman 0,1-0,5 sn erken damgalar ("Açıkça"
17,86'da damgalı, ses 18,45'te başlıyor). Bir kelime 4,08-6,76 aralığına yayılmış damga da
gördük; aralıkta kesintisiz konuşma vardı. Kural: bir kesimin yanlış olduğunu iddia
etmeden önce sese bak (`zarf`), ya da o pencereyi ayrıca çözdür (`pencere`).

**Uyarlamalı eşik.** `eşik = max(p10 + 8 dB, p90 − 30 dB)`: gürültü kapılı kayıtta
(sessizlik −120 dB, konuşma ~−20 dB) konuşmanın 30 dB altı, gürültülü odada gürültü
tabanının 8 dB üstü belirleyici olur.

## Parçalar (`kesim.parcalar`)

| Kural | Değer | Neden |
|---|---|---|
| Sesli bölge içindeki kısa boşluk kapanır | < 0,12 sn | hece arası, ünsüz kapanması |
| Kısa sesli ada atılır | < 0,06 sn | tık, dudak sesi |
| Atılan aralığın sınırı | ±0,2 sn içindeki en kısık kare | damga kayması; kelime ortasından kesmemek |
| Kelime-bölge örtüşme payı | 0,3 sn | 0,15 iken kısa kelimeler ("Ve", "Doğal") bölgesiz kalıp düşüyordu |
| Kelimesiz bölge tutulur | ≥ 0,2 sn, eşik +12 dB, iki komşusu tutuluyor | Whisper'ın yazmadığı gerçek söz |
| Parça başı | sesten 0,06 sn önce | ilk ünsüz kesilmesin |
| Parça sonu | cümle sonunda +0,28 sn, cümle içinde +0,12 sn | nefes ve doğal bırakış |
| Pay komşu bölgeye taşmaz | komşunun 0,01 sn öncesi | yarım hece bırakmamak |
| İki parça arası < 0,05 sn | tek parça | gereksiz birleşim |

**İkinci bir "boşluk kısaltma" geçişi denendi ve kaldırıldı.** Kalan uzun boşlukları tek tek
ölçüp kısaltan bir modül yazıldı; ölçüm onu çürüttü: 5 kelime yuttu ve 0,6 sn üstü boşluk
sayısını 5'ten 9'a çıkardı (segmenti bölerken açtığı yeni sınırlar kazandığından fazlasını
geri veriyordu). Sorun segment içindeki boşluklar değil kesim noktalarındaki pay; çözüm
parametrede, ikinci geçişte değil.

## Blok sınırları

- Blok başı ±0,25 sn içindeki en kısık kareye oturur (kelimenin ortasına düşmesin).
- Blok sonu son kelimeyi kesmesin: verilen sondan 0,1 sn önceden başlayarak ilk ≥0,3 sn
  sessizliğin başı + 0,35 sn (en çok 1,5 sn uzar).
- Bitişik bloklar birbirine taşmaz; sınır tek bir sessiz kareye oturur.

## Tekrar

- Art arda aynı 1-3 kelime ve iki kopya arası < 1,5 sn → **ilk kopya atılır** (son deneme kalır).
  Kesim aralığı ilk kopyanın başından ikinci kopyanın başına kadardır; iki sınır da sessiz
  kareye oturur, böylece "bu işi bu işi" bitişik söylense bile "işi bu işi" kalmaz.
- **Sayı içeren kelime karşılaştırılmaz**: harfiyen döküm "5.5"i "5" + ".5" yazıyor,
  "5" tekrar sanılıp atılıyordu.
- Türkçe ikilemeler ve vurgu ("çok çok", "tek tek", "yavaş yavaş", "evet evet") tek kelimelik
  tekrarda atılmaz (`TEKRAR_SERBEST`). "bir" bilerek listede yok: "bir, bir şey" takılması
  çok daha sık.
- Cümle sonu noktalı kelimenin tekrarı atılmaz ("…yaptık. Yaptık ki…").
- 4+ harfli bir kelime 2-5 kelime sonra yeniden geçiyorsa **[ADAY]** yazılır: yeniden
  başlama olabilir. Otomatik atılmaz.

**Mekanik eşleştirme iki yönde de yanılıyor**, bu yüzden son karar okuyanındır:

| Yanılma | Örnek |
|---|---|
| Kaçırıyor: denemeler arasında cümle değişiyor | "konteks nedir" → "çok basit bir şekilde ne ifade ediyor" |
| Fazladan atıyor: anafora ve karşıtlık tekrar sanılıyor | "Burada bir şey yazıyor. / Burada **başka** bir şey yazıyor." |

Eşiği oynatmak ikisini birden çözmüyor; karar dosyası (atilacak.json, korunacak.json) gerekçeli tutulur.

**Kullanıcı kesim talimatını sesli söyleyebiliyor:** "tekrar böyle kesin", "burayı tekrar
alalım", "burayı keseceğim". Bunlar dökümde durur ve en güvenilir kesim işaretidir.

## Harfiyen döküm

- Uzun bağlamda Whisper takılmayı yutuyor ("bu işi, bu işi beş" → "bu işi 5", süresi 1,4 sn).
  Kayıt sessizliklerin ortasından ≤10 sn'lik parçalara bölünür, her parça **bağımsız** çözülür
  (`condition_on_previous_text=False`); istemde takılma örnekleri var ("Ee, şey. Bu işi, bu işi.").
- Whisper sessizlikte uydurur ("Altyazı M.K." gibi). Sesli oranı %15'in altındaki satır atılır.
- Alan sözlüğü girdiyi düzeltir: bir ölçümde transkriptte "Claude" 0, "Cloud" 14 kez geçiyordu.
  İki katman: istem (çözüm anında) + düzeltmeler (sonrasında). Çok kelimeli düzeltme kelimeleri
  tek kelimeye birleştirir, zaman aralığı korunur.

## Kare ızgarası ve ses

- Parçanın başı kareye yuvarlanır, süresi tam kare sayısıdır. Ses ile görüntü ayrı ayrı
  yuvarlanırsa 200+ parçada kayma birikiyor.
- Ses örnek örnek kurulur: parça = kare sayısı × (48000 / fps) örnek, uçlarında 10 ms
  yumuşatma (tık sesi olmasın). Bu yüzden fps 48000'i tam bölmeli (24, 25, 30, 48, 50, 60).
- Hızlanan parçanın sesi aralığın kendi sesinin başıdır (zaten konuşmasız).
- Son ses zinciri: 80 Hz alçak kesen, hafif FFT gürültü azaltma, 3:1 kompresör, sonra −14 LUFS.
  Tek geçişli loudnorm konuşmada hedefin altında kalıyor (ölçüldü: −15,0 LUFS; tepe/ses oranı
  yüksek, doğrusal kazanç −1,5 dBTP tepeyi aşacağı için dinamik moda düşüyor). Bu yüzden: ölç,
  eksik kazancı ver, tepeleri sınırlayıcıyla −2 dBFS'te tut, ölçülmüş değerlerle loudnorm
  (ölçüldü: −14,0 LUFS).

## Hızlandırma (`ekran-hizli`)

- En az 0,5 sn'lik sessiz koşular, aralarındaki 0,4 sn'den kısa gürültüyle birleşir.
- ≥ 2,4 sn ve içinde Whisper kelimesi yoksa: iki kenarda 0,35 sn normal hız kalır, ortası 2x;
  hızlanan kısım ≥ 6 sn ise 4x. Konuşma hiçbir zaman hızlanmaz.

## Senkron

- Ses zarfı (200 Hz, log RMS, 1 sn'lik ortalaması çıkarılmış) çapraz ilişkisi. Önce tüm
  kayıtla kaba ofset, sonra pencere pencere ±1 sn içinde ince ofset ve doğru uydurma.
- Ölçüm: 25 dakikalık kamera ↔ ekran kaydı, sürüklenme 25 dakikada 15 ms, r ≈ 0,7. 4 dakikalık
  pencerede aynı ofset 2 ms içinde bulundu.
- Ekranın kendi mikrofonu (dizüstü dahili mikrofonu) yeterli; konuşmanın inip çıkışı eşleşir.

## Birleşim denetimi

- Kesik ses yeniden harfiyen çözülür. Her birleşimde önceki parçanın son 2 ve sonrakinin
  ilk 2 kelimesi, birleşim anının ±1,6 sn'sinde aranır (benzerlik > 0,72).
- **EKSİK** = beklenen kelime duyulmuyor; **SIZAN** = birleşime 1,5 sn'den yakın atılmış bir
  kelime duyuluyor ve çevrede tutulan kelimeler arasında yok.
- 25 dakikalık bir kayıtta 217 birleşimin 22'si şüpheli çıktı; her biri pencereyle dinletilip
  karar verildi. Çoğu Whisper'ın kısa kelimeyi yeniden duymaması.
- Duyulur kelime-içi kesimde ATILAN tarafa bak: tutulan tarafta ses olması normaldir (kelime
  başında kesmek doğru kesimdir); asıl işaret iki yanın da konuşma seviyesinde olması.
  Bu ayrım bir denetimde 36 şüpheliyi 2 gerçek hataya indirdi.

## Uçtan uca ölçüm (bu skill, 2026-10)

4 dakikalık bir kesit: kamera kaydı (sesi taşıyan, 2560x1440) + ayrı ekran kaydı (dahili mikrofonlu).
M1 Pro 8 çekirdek, 16 GB, large-v3 int8 CPU; aynı anda başka bir render çalışıyordu.

| Adım | Sonuç | Süre |
|---|---|---|
| dokum | 35 parça, 613 kelime, eşik −55,6 dB | 596 sn (gerçek zamanın 0,4 katı) |
| senkron | ofset +3,872 sn (bağımsız ölçüm 3,870), 4 dakikada 7 ms kayma, r medyan 0,67, 8/8 pencere | 1,5 sn |
| kurgu | 8 gerekçeli atma (57,5 sn), 4 blok, 29 parça; 4:00,0 → 2:48,2 (%30) | 0,1 sn |
| cek | 1920x1080 30 fps, VideoToolbox, 2 paralel; süre planla aynı (168,20 sn), −14,0 LUFS | 36 sn (önbellekle 13 sn) |
| dogrula | 28 birleşim, 0 şüpheli; beklenen 471 kelime, duyulan 474 | 482 sn |
| pencere | 4 birleşim yeniden çözüldü, hepsi temiz | 77 sn |

Claude'un dökümü okuyarak yazdığı 8 kesimin 7'si, aynı kaydın sahibinin elle yaptığı kesimlerle
örtüştü (yeniden başlamalar, kurgu notu, sürçme, yanlış okuma, anlaşılmayan söz, bir yan konu).
Fazladan 1 kesim (yarım kalan "Çünkü her…"), alınmayan 1 kesim (girişi kısaltan içerik kararı;
kullanıcıya sorulmadan atılmadı).
