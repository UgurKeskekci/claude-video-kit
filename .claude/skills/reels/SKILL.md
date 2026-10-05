---
name: reels
description: Konuşan kafa kaydından (kamera, ses içinde; yatay 4K ya da dikey) dikey Instagram Reels / YouTube Shorts / TikTok videosu (1080x1920, 30 fps) üretir, "kart" formatında - üstte söylenen kelimede beliren sade arayüz kartları (sohbet balonu, liste, harf harf yazılan terminal, dosya ağacı, büyük sayı, gerçek ekran görüntüsü), altta yuvarlak köşeli yüz kartı, aralarında kelime kelime altyazı, kart geçişinde yumuşak whoosh, yazarken klavye sesi, sonda "yorumlara yaz" sorusu. Şu durumlarda kullan - "reels yap", "bundan reels çıkar", "shorts yap", "dikey video", "kartlı reels", "bilgi veren reels", "ipucu videosu", "üstte kart altta yüz", "yorumlara yaz diye bitsin", "tips reels".
---

# Reels (kart formatı)

Bir konuşma kaydını, söylenen her fikrin üstte bir kartla göründüğü dikey videoya çevirir.
İş bölümü şöyle:

- **Araçlar** sesi ölçer ve keser (`yatay-kurgu` skill'inin döküm/kesim araçları), kartları
  ve altyazıyı çizer, sesi dengeler, sonucu ÖLÇER.
- **Sen (Claude)** dökümü okursun, atılacakları seçersin, hangi kartın hangi KELİMEDE
  gireceğini `senaryo.json`'a yazarsın, kontrol resimlerine BAKARSIN.

Saniye yazmazsın: kart, söylenen kelimeye bağlanır; kesim değişse de yerinde kalır.

## Hazırlık

- `ffmpeg` PATH'te, Python bağımlılıkları repo kökündeki `kur.sh` ile kurulur. Komutlarda
  Python olarak `.venv/bin/python` kullan (Windows: `.venv\Scripts\python`). libass'lı ffmpeg
  GEREKMEZ: altyazı Pillow ile çizilir.
- Aynı repodaki iki skill'in araçlarını kullanır, onlara dokunmaz: `yatay-kurgu` (harfiyen
  döküm + sesten kesim) ve `x-animasyon` (whoosh ve klavye sesi sentezi).
- Whisper modeli ilk çalışmada iner (large-v3 ≈ 3 GB); indirmeden önce kullanıcıya söyle.
- Yazı tipleri yalnız repo kökündeki `fontlar/` (OFL): Inter, Newsreader, IBM Plex Mono.
- Her iş kendi klasöründe: `calisma/reels/<ad>/`. Ham kayda yalnızca okunur.

Aşağıda `R` = `.venv/bin/python .claude/skills/reels/araclar/reels.py`, `P` = `calisma/reels/<ad>`.

## Döngü

**1. Döküm.**

```bash
R dokum P --video kayit.mp4 [--bas 56 --sure 42] [--terimler "videoya özel adlar"]
```

Kayıt uzunsa ve Reels yalnız bir bölümüyse `--bas/--sure` ile pencereyi ver (kesit
`P/kaynak.mov` olarak çıkarılır, ham dosya değişmez). Hedef: 35-45 sn'lik çıktı.

**2. Dökümü oku, kes.** `P/dokum.md`'yi baştan sona oku (yatay-kurgu SKILL.md'deki kurallar
geçerli). Duraklama ve art arda tekrar zaten atıldı; sen şunları `P/atilacak.json`'a yazarsın,
her satıra gerekçe:

- yeniden başlama (son deneme kalır), kurgu notu ("burayı keseceğim"), yanlış söylenip düzeltilen sayı;
- **anlaşılmayan söz**: iki çözümde de belirsiz kalan kısım altyazıya uydurulmaz, kesilir
  (`.venv/bin/python .claude/skills/yatay-kurgu/araclar/kurgu.py pencere P <sn>` ile yeniden çözdür);
- Reels'e fazla gelen yan konu: içerik kararı, kullanıcıya sor.

Kesim noktasını SES verir: aralığı `dokum.md` satır sınırlarından yaz, araç ±0,2 sn içindeki en
kısık kareye oturtur. Sonra:

```bash
R kurgu P        # planı yeniden kur
R kelimeler P    # kurguda kalan kelimeler, çıktı saniyesiyle (çıpaları buradan seç)
```

**3. Senaryo: `P/senaryo.json`.** Örnek: `ornekler/reels/senaryo.ornek.json`. Alan listesi ve
kart türleri: [references/kartlar.md](references/kartlar.md).

```json
{"vurgu": ["effort"], "kuyruk": 2.0, "vuruslar": [
  {"duzen": "yuz"},
  {"kelime": "Önce", "kart": {"tur": "liste", "baslik": "Sıra", "isaret": "sayi",
     "maddeler": [{"yazi": "Modeli seç", "kelime": "modeli"}, {"yazi": "Effort'u seç", "kelime": "effort"}]}},
  {"kelime": "oynattım", "ofs": 0.5, "duzen": "grafik", "kart": {"tur": "soru", "soru": "Sen hangisini kullanıyorsun?"}}
]}
```

- **Vuruş** = ekranın bir hali. `kelime` çıpası kelimenin BAŞIdır ("effort" -> "effort'unu"),
  önceki vuruştan SONRA aranır; birden çok kelime olabilir ("plan modu"), `kac` n'inci geçiş,
  `ofs` saniye kaydırma. İlk vuruş 0'da başlar. Karttaki madde/satır/mesaj da kendi `kelime`siyle girer.
- **Düzen:** `bol` (kart üstte, yüz altta; kartı olan vuruşun varsayılanı), `yuz` (tam ekran yüz;
  kartsız vuruşun varsayılanı), `grafik` (tam ekran kart, yüz yok).
- **Tempo:** vuruş başına 1,5-4 sn; 40 sn'lik Reels'te 10-15 vuruş. Kanca (ilk 1-2 sn) yüzle açılır.
- **Yüz yalnız kameraya bakılan yerde.** Kişi ekrana/metne bakarak konuşuyorsa o vuruş `grafik`.
- **Uydurma yok:** kart yalnız gerçekte söyleneni ya da gerçekte olanı gösterir. Ölçülmemiş sayı,
  var olmayan komut, uydurma ekran yazısı yazma. Ekran görüntüsü kullanıcının gerçek dosyası (`gorsel`).
- **Kapanış:** son vuruş `soru` kartı (yorumlara yazdıran soru); konuşma bitince `kuyruk`
  (sn) kadar ekranda kalır, bu yüzden `grafik` düzeni seç (kuyrukta görüntü donar).
- Altyazıda yanlış duyulan kelime: `"altyazi_duzelt": {"aranaya": "arenaya"}`. `vurgu` listesindeki
  kelimeler altyazıda italik + vurgu rengiyle çıkar (kök yeter: "effort").

Çözülen zamanlara bak: `R vuruslar P` (her vuruşun başı/sonu, öğe zamanları; görünmeden kart
değişecek öğe için UYARI verir).

**4. Kadraj.**

```bash
R yuz P          # yüz kutusu tahmini -> P/kadraj.json + P/kontrol/kadraj.jpg
```

`kontrol/kadraj.jpg`'yi Read ile AÇ: yeşil kutu yüzü (alından çeneye) sarmalı; mavi `bol`,
turuncu `yuz` kırpmasıdır. Tahmin modelsizdir (ten rengi + merkez önceliği); arka planda ten
rengine yakın yüzey, iki kişi ya da renkli ışık onu yanıltabilir. Yanlışsa `kadraj.json`'daki
`kutu`yu cetveldeki kaynak piksellerine bakarak ELLE düzelt ve `R yuz P` ile resmi yenile
(var olan kadraj.json'un üzerine yazmaz). Kişi kayıyorsa `anahtarlar` (zamanlı kutular) yaz.

**5. Önizleme, sonra render.**

```bash
R kare P                    # her vuruştan bir kare -> P/kontrol/kareler.jpg (BAK)
R kare P 2.3,31.4           # belirli anlar (giriş animasyonu, yazılan terminal)
R render P                  # -> P/cikti/<ad>.mp4, sonunda ölçüm kendiliğinden çalışır
```

**6. Ölç (izleyemezsin, ölçerek bak).** `R olc P` (render sonunda zaten çalışır) ->
`P/kontrol/olcum.md` + `P/kontrol/temas.jpg`:

- **Süre:** görüntü/ses aynı uzunlukta, kare sayısı beklenenle aynı.
- **Güvenli alan:** her 5 karede altyazının, kartın ve yüzün PİKSEL kutusu ölçülür. Instagram
  arayüzü üstte y<220'yi, altta %20'yi (y>1536) ve sağdaki beğen/yorum sütununu (x>940,
  y 1000-1536) kapatır; altyazı ve kart oraya girmez, yüz alt %20'nin üstünde kalır. İHLAL
  satırı varsa senaryoyu (kart içeriği, düzen) ya da `kadraj.json`'u düzelt.
- **Ses:** son dosya -14 LUFS, gerçek tepe <= -1 dBTP; efekt izi konuşmanın ~15 dB altında;
  whoosh tepeleri kesimlere oturuyor mu.
- **Temas sayfası:** her vuruştan kartın DOLMUŞ hali (değişimden hemen önce). AÇ ve bak:
  taşan yazı, üst üste binen öğe, kesilen baş, boş kalan kart.
- **Birleşimler (isteğe bağlı):** `.venv/bin/python .claude/skills/yatay-kurgu/araclar/kurgu.py dogrula P`
  kesik sesi yeniden çözer, kopan/sızan kelimeyi raporlar (`P/dogrula.md`).

Düzeltince yalnızca `R render P` (ses ve görüntü baştan, M1 Pro'da 40 sn'lik video ~35 sn).

**7. Teslim.** Kullanıcıya kısa ve sayılarla: çıktı yolu, süre (ham -> kurgu), vuruş/kart sayısı,
attıkların ve gerekçeleri, güvenli alan sonucu, LUFS/tepe, temas sayfasının yolu. Ölçemediğin
şeyi (sesin hoşluğu, kartın anlaşılırlığı) açıkça kullanıcıya bırak.

## Bilinen sınırlar

- Yüz kutusu modelsiz tahmin; her kayıtta `kadraj.jpg`'ye bakmak şart. Kare kare yüz takibi
  yok: sabit kutu ya da anahtar kareler arası doğrusal geçiş.
- Yatay kayıttan tam ekran yüz (`yuz`) kaynağın yüksekliğiyle sınırlı: 4K'da yüz büyük kalır,
  altyazı kendiliğinden çenenin altına iner. `bol` düzende yüz kartının boyu, yüzün altında
  kaynakta kalan görüntüye göre kısalır (çene alt %20'ye inmesin diye).
- Müzik yok; efektler sentez (whoosh, klavye, pop, çizik).
- Kart türleri sabit (references/kartlar.md). Yeni tür: `araclar/kartlar.py`'ye çizim + ses
  fonksiyonu, `CIZ` ve `OLAY` sözlüklerine kayıt.
- Arayüz bölgeleri (üst 220, alt %20, sağ sütun x>940) Instagram Reels için yaklaşık, temkinli
  değerlerdir (`araclar/cizim.py` başında); Shorts/TikTok'ta benzer ama birebir aynı değil.
