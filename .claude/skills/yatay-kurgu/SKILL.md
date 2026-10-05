---
name: yatay-kurgu
description: Yatay YouTube konuşma videosunu (kamera kaydı, isteğe bağlı ayrı ekran kaydı) kaba kurgular. Harfiyen döküm çıkarır, duraklamaları ve art arda tekrarları sesten keser; Claude dökümü okuyup gerekçeli bir atma listesi yazar, mp4 üretilir, kesilmiş ses yeniden çözülüp her birleşim denetlenir. Şu durumlarda kullan - "videoyu kurgula", "kaba kurgu", "ham kaydı kes", "beklemeleri/duraklamaları kes", "tekrarları at", "takılmaları temizle", "jump cut", "keseceğim dediğim yerleri at", "kamera ile ekran kaydını senkronla", "ekran kaydının köşesine kamera koy", "sessiz yerleri hızlandır".
---

# Yatay kurgu

Ham konuşma kaydından yayına yakın bir kaba kurgu çıkarır. İş bölümü şöyle:

- **Araçlar** sesi ölçer: duraklamaları, art arda tekrarları ve sessizlikte kalan boşlukları
  kendileri atar, kesim noktasını sesin en kısık karesine oturtur.
- **Sen (Claude)** dökümü baştan sona okur ve araçların göremediğini atarsın: yeniden
  başlamalar, "burayı keseceğim" gibi kurgu notları, yanlış söylenip düzeltilen sayılar,
  konudan sapan kısımlar. Her kesimin gerekçesini yazarsın.
- **Denetim** kesilmiş sesi yeniden çözer ve her birleşimde kopan ya da sızan kelime arar.

Çıktı bir mp4'tür (NLE projesi değil). Renk, müzik, altyazı ve grafik bu skill'in işi değil.

## Ne zaman kullanılır

- Kullanıcı yatay bir konuşma kaydı verip "kurgula", "kes", "beklemeleri at" dediğinde.
- Kamera ile ekran kaydı ayrı dosyalarsa ve ikisinin eşlenmesi gerekiyorsa.
- Dikey video (Reels/Shorts) için değil; o işte tuval ve altyazı farklı.

## Hazırlık

- `ffmpeg` PATH'te olmalı, Python bağımlılıkları repo kökündeki `kur.sh` ile kurulur.
  Komutlarda Python olarak `.venv/bin/python` kullan (Windows: `.venv\Scripts\python`).
- Whisper modeli ilk çalışmada iner (large-v3 ≈ 3 GB). İndirmeden önce kullanıcıya söyle.
- Süre en çok Whisper'da gider. Ölçüm (M1 Pro 8 çekirdek CPU, large-v3 int8, harfiyen mod,
  yanda başka bir render çalışırken): 4 dakikalık kayıt 10 dakikada çözüldü (gerçek zamanın
  0,4 katı); `dogrula` kesik sesi aynı hızla yeniden çözer. Kesim, senkron ve plan saniyeler,
  çekim dakikalar sürer. Uzun kayıtta kullanıcıya baştan süreyi söyle; hızlı deneme için
  `--model medium` ya da `small` verilebilir (daha az isabetli; kurallar large-v3 ile ölçüldü), son denetimi
  varsayılan modelle yap. NVIDIA GPU varsa `--cihaz auto` CUDA'yı kendisi seçer.
- Her iş kendi klasöründe: `calisma/<proje>/`. Kullanıcının ham dosyalarını taşıma, silme,
  üzerine yazma; araçlar onları yalnızca okur.

Aşağıda `K` = `.venv/bin/python .claude/skills/yatay-kurgu/araclar/kurgu.py`, `P` = `calisma/<proje>`.

## Döngü

**1. Döküm.** Sesi çıkarır, harfiyen dökümü alır ve ilk planı kurar (atma listesi olmadan).

```bash
K dokum P --video kamera.mp4 [--ekran ekran.mp4] [--terimler "videoya özel terimler"]
```

Videoda geçen özel adları (ürün, kişi, oyun adı) `--terimler` ile ver; Whisper doğru yazar.

**2. `P/dokum.md`'yi baştan sona oku.** Tamamını, parça parça Read ile. Göz gezdirme:
yeniden başlamalar ve kurgu notları cümlenin ortasında saklanır. Okurken şunları ara:

- Yeniden başlama: aynı fikrin ikinci denemesi. **Son deneme kalır**, öncekiler gider.
  `[ADAY]` satırları ipucudur, karar senin.
- Kurgu notu ve kendine not: "burayı keseceğim", "bunu tekrar alalım", "kesin", "pardon",
  "Tekrar.", "böyle olmasın", "…'a not: buraya şunu koy". Kullanıcı kesim talimatını sesli
  verebiliyor; en güvenilir işaret bu.
- Yanlış söylenip düzeltilen sayı, ad, birim: yanlış olan gider.
- Boşta kalan söz ("Evet. Şimdi şey…"), anlaşılmayan mırıltı, yarım cümle.
- Konudan sapan, gereksiz uzun kısım. **Bu bir içerik kararıdır:** kullanıcıya sorarak at.
- `DÜŞTÜ` satırları: ses ölçümüyle düşen kelimeler. Çoğu Whisper uydurması ya da nefes;
  anlamlı bir söz düşmüşse `zarf` ile bak.

**3. `P/atilacak.json`'ı yaz.** Kaynak saniyesiyle, her satıra gerekçe:

```json
[
  {"bas": 31.20, "son": 36.85, "gerekce": "yeniden başlama: cümlenin ilk denemesi, ikincisi kalıyor"},
  {"bas": 102.40, "son": 104.10, "gerekce": "kurgu notu: 'burayı keseceğim' dedi"}
]
```

- Sınırları dökümdeki `[baş–son]` satır sınırlarından al; araç kesimi ±0,2 sn içindeki en
  kısık kareye oturtur, tam isabet gerekmez. Ortası aralığa düşen kelime atılır: `son`'u
  kalacak ilk kelimenin damgasından biraz ÖNCE bitir, içine taşırma.
- Satırın yalnız bir kısmı gidecekse `K zarf P 100 106` ile kelime damgalarına ve sese bak.
- Bilerek yapılan vurgu tekrarı ("adım adım", "bilgi bilgi bilgi") otomatik atılmasın
  istiyorsan aralığını `P/korunacak.json`'a aynı biçimde yaz.
- Karşıtlık ve anafora tekrar değildir: "Burada bir şey yazıyor. Burada başka bir şey
  yazıyor." ikisi de kalır.

**4. Görüntü blokları (isteğe bağlı): `P/bloklar.json`.** Yoksa tüm kayıt tek kamera bloğu.

```json
[
  {"etiket": "giriş", "bas": 0, "son": 95.5, "goruntu": "kamera"},
  {"etiket": "demo", "bas": 95.5, "son": 400, "goruntu": "ekran"},
  {"etiket": "test koşuyor", "bas": 400, "son": 520, "goruntu": "ekran-hizli"}
]
```

- `kamera`: ana kayıt tam kare; atlanan kesimde 1,00 / 1,06 yakınlaşma sırayla değişir.
- `ekran`: ekran kaydı tam kare, köşede yuvarlak küçük kamera. Köşe kamerası istemediğin
  blokta `"kose": false`.
- `ekran-hizli`: sessizlik atılmaz; 2,4 sn'den uzun konuşmasız yer 2x (6 sn'den uzunsa 4x)
  hızlanır, sol üstte "2x" rozeti. Çalışan bir şeyi izletirken kullan.
- Blok sınırını cümle arasına koy. Kişi kameraya bakmıyorsa (ekrana bakarak anlatıyorsa)
  o bölüm `ekran` olsun; yüzü yalnızca kameraya baktığı yerde göster. Emin değilsen iki
  kayıttan birkaç kare çıkarıp bak (`ffmpeg -ss <sn> -i kamera.mp4 -frames:v 1 kare.jpg`).

**5. Planı kur ve yeniden oku.**

```bash
K kurgu P
```

`dokum.md` yeniden yazılır. `ATILDI` satırlarının doğru cümleyi aldığını, kalan metnin
akıcı okunduğunu kontrol et. Gerekirse 3-5'i tekrarla; bu adım saniyeler sürer.

**6. Senkron (ekran kaydı varsa).**

```bash
K senkron P            # ekran_t = ana_t + ofset + kayma·ana_t  -> P/senkron.json
```

Pencerelerin `r` değeri 0,5'in üstünde ve ofsetler birkaç ms içinde tutarlı olmalı.
Ekran kaydında mikrofon yoksa ofseti elle ver: `K senkron P --ofset 2.5`.

**7. Çek.** Önce küçük bir deneme, sonra tamamı (parçalar önbellekte kalır, ikinci çekim hızlı):

```bash
K cek P --bas 0 --bit 15      # ilk 16 parça -> P/cikti/kurgu-0-15.mp4
K cek P [--boyut 2560x1440]   # tamamı -> P/cikti/kurgu.mp4
K temas P                     # blok başına bir kare -> P/kontrol/temas.jpg (Read ile bak)
```

`temas.jpg`'ye mutlaka bak. Köşe kamerasında yüz küçük ya da kenardaysa kırpmayı
`--kose-kirp 0.52,0.45,0.5` ile (merkez x, merkez y, kenar/yükseklik) ayarla. Ekran kaydının
kenarında siyah şerit ya da tarayıcı çubuğu varsa `--ekran-kirp 2468:1388:46:47`
(genişlik:yükseklik:x:y, kaynak pikseli) ile kırp; en-boy oranını 16:9 tut.

**8. Denetle ve düzelt.**

```bash
K dogrula P                   # kesik sesi yeniden çözer -> P/dogrula.md
K pencere P 104.10 212.75    # şüpheli birleşimlerin ±3 sn'si (kaynak saniyesi)
```

`dogrula.md`'de her şüpheli için:
- **EKSİK** (beklenen kelime duyulmuyor): önce `pencere` ile dinlet. Kısa kelimeleri (ve, de,
  bu) Whisper ikinci çözümde sık atlar; çoğu yanlış alarmdır. Gerçekten kesildiyse ilgili
  `atilacak` sınırını genişlet/daralt ya da kesimi kaldır.
- **SIZAN** (atılan bir kelime duyuluyor): atma aralığını o kelimeyi kapsayacak şekilde büyüt.
- Bir kesimin yanlış olduğunu söylemeden önce `zarf` ile sese bak; damgaya güvenme.

Düzeltince `kurgu` → `cek` → `dogrula` yeniden. Değişmeyen parçalar yeniden üretilmez.

**9. Kullanıcıya rapor.** Kısa ve sayılarla:
- süre: ham → kurgu (ör. 4:00 → 2:48, %30 kısaldı), parça ve blok sayısı;
- elle attıkların, gerekçeleriyle tek tek (zaman + bir satır);
- otomatik atılan tekrar sayısı, hızlandırılan aralıklar;
- denetim: kaç birleşim, kaç şüpheli, hangileri düzeltildi, hangisi yanlış alarm çıktı;
- ses seviyesi (LUFS) ve çıktı dosyasının yolu.
İçerik kesimlerini (gereksiz detay) ayrıca belirt; geri istenirse tek satır silmek yeter.

## Öğrenilen kurallar (kısa)

- **Kararı ses verir.** Kelimesiz aralık sessizlik demek değildir: Whisper tekrarları yutabilir.
  Kesim noktası zarftan bulunur, kelimeler yalnızca neyin tutulacağını söyler.
- **Whisper damgası ~0,5 sn kayar** (çoğu zaman erken). Damgaya göre kesme, sese göre kes.
- **Kelimenin ortasından kesme.** Bölge sınırları sesin bittiği yere, artı nefes payı:
  cümle sonunda 0,28 sn, cümle içinde 0,12 sn kalır; baştan 0,06 sn önce başlar.
- **Uzun bağlamda Whisper takılmayı yutar**; bu yüzden döküm ≤10 sn'lik bağımsız parçalarla.
- **Ses ve görüntü aynı kare ızgarasında** (30 fps, parça = tam kare, ses = kare × 1600 örnek).
- İkinci bir "boşluk kısaltma" geçişi yazma; denendi, kelime yuttu (ayrıntı kurallar.md'de).

Ölçümleriyle tüm kurallar: [references/kurallar.md](references/kurallar.md).
Dosya biçimleri ve komut seçenekleri: [references/dosyalar.md](references/dosyalar.md).

## Bilinen sınırlar

- Tek ana kayıt (ses + kamera). Birden çok parça varsa önce ffmpeg ile birleştir ya da her
  parçayı ayrı proje yap.
- Ses daima ana kayıttan; ekran kaydının sesi yalnızca senkron için kullanılır.
- Köşe kamerası sabit kırpmadır, yüz takibi yok.
- Kamera bloğunda geçiş efekti yok; jump cut yakınlaşmayla yumuşatılır.
- `[ADAY]` gürültülüdür (4 dakikada ~17 satır); çoğu "gerekiyor … gerekiyor" gibi doğal tekrar.
  Asıl yeniden başlamaları dökümü okuyarak bulursun, aday listesi yalnız ipucu.
- Kurgu notu ("buraya zil sesi koy", "şuraya bar çıkart") kesilir ama uygulanmaz: grafik ve
  efekt bu skill'in işi değil. Raporda kullanıcıya ayrıca listele.
