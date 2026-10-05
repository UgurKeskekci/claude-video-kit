---
name: x-animasyon
description: Sayı ve yazıyla hikâye anlatan editoryal hareketli grafik videosu üretir (Remotion) — X/Twitter gönderisi, Reels/Shorts, YouTube video arası. Hikâye JSON sahne listesi olarak yazılır (başlık, yazılan istem, sayaç, ölçer, sütunlar, karşılaştırma, liste, soru), 16:9 ve 9:16 render edilir, yumuşak whoosh + klavye + sakin müzik yatağı numpy ile sentezlenip eklenir, sonuç ölçülerek denetlenir. Şu durumlarda kullan: "X için animasyon/video", "hareketli grafik", "motion graphics", "sayılarla anlat", "sonuçları grafikle göster", "karşılaştırma videosu", "test sonucunu animasyonla anlat", "reels grafiği", "araya grafik", "Remotion".
---

# Editoryal hareketli grafik (Remotion)

Bir deneyin, testin ya da fikrin hikâyesini 15-30 saniyelik, sayı ve yazı ağırlıklı bir
videoya çevirir. Görünüş sabit ve özenli: zarif serif başlık + italik vurgu kelimesi (gök mavisi),
küçük aralıklı mono BÜYÜK HARF etiketler, sıkı kalın grotesk sayılar; sürekli ince çerçeve
(sol üstte marka, sağ üstte "01 — BÖLÜM", altta bölmeli ilerleme + zaman), zeminde hafif
ızgara, kenar kararması, ince gren. Hikâyeyi sen JSON olarak yazarsın, görüntü ondan çıkar.

Çizim, karakter, el yapımı sahne gerekiyorsa bu değil **`animasyon`** skill'i (PIL mürekkep).

Örnek: `ornekler/x-animasyon/ornek.json` ("Aynı işi üç farklı ayarla yaptırdım"; sayıları
**uydurma demo verisi**, ekranda "örnek veri" yazar).

## Kurulum (bir kez)

```bash
cd remotion && npm install      # Node 18+; fontlar/ klasörü public/fonts'a kendiliğinden kopyalanır
```
İlk render Chrome Headless Shell'i indirir (~100 MB). Python tarafı: numpy, Pillow, ffmpeg.
Komutlarda Python olarak `.venv/bin/python` kullan (Windows: `.venv\Scripts\python`).

## Döngü

### 1. Hikâyeyi anla
Tek cümlelik iddia ne? Hangi sayılar var ve **nereden geliyor**? Platform ve oran (X: 16:9,
Reels/Shorts: 9:16, ikisi de olabilir), süre (X 15-30 sn). Sayı yoksa sayı uydurma: ya
kullanıcıdan ölçülmüş sayıyı iste ya da sayısız sahneler kullan (başlık, liste, soru).

### 2. Sahne listesini yaz: `calisma/x-animasyon/<ad>.json`
Örnekten kopyala. Kurallar:
- Her sahne **tek fikir**, satır başına 3-7 kelime, doğal ve sade Türkçe. Uzun cümle yerine iki satır.
- `*kelime*` = vurgu (serifte italik + mavi). Sahne başına en fazla bir vurgu.
- **Sayılar yalnız ölçülmüş olabilir.** Ölçülmemiş/örnek sayı kullanıyorsan üst düzeyde
  `"etiket": "örnek veri"` kalsın ve kullanıcıya söyle.
- Türkçede yüzde önde: `"onek": "%"` → `%80`. Para ve süreyi karşılaştırmada hazır metin ver: `"$0,61"`, `"5 dk 12 sn"`.
- `bolum` yeni bir bölüm açar (sağ üst etiket + ilerleme çubuğunun bir parçası); 3-5 bölüm yeter.
- "beklemede", "yakında" gibi durum rozetleri ve kendine not yazma; ekrandaki her yazı izleyici için.

| `tur` | Alanlar | Ne için | Önerilen süre |
|---|---|---|---|
| `baslik` | `ust?`, `satirlar` | kanca: ilk 2-3 sn | 2,4-3 |
| `yazi` | `satirlar?`, `ust?`, `metin` (≤160) | istem/komut harf harf yazılır, klavye sesiyle | 0,55 + harf × 0,09 + 0,9 |
| `sayac` | `ust?`, `deger`, `baslangic?`, `ondalik?`, `onek?`, `sonek?`, `alt?` | tek büyük sayı sayarak gelir | 3 |
| `olcer` | `satirlar`, `seviyeler[2-6]` (`ad`, `etiket?`) | kavramsal seviye: düşükten yükseğe sırayla dolar | 3-4 |
| `sutunlar` | `satirlar`, `ogeler[2-6]` (`ad`, `deger`, `etiket?`), `onek/sonek/ondalik?`, `not?` | ölçülmüş sonuçlar, sıra etiketi otomatik | 4-4,5 |
| `karsilastirma` | `satirlar` (tek satır), `a`, `b` (`ad`, `ust?`, `deger`, `altEtiket?`, `alt?`), `fark?` (`deger`, `etiket?`, `alt?`) | A ile B: maliyet, süre | 4-5 |
| `liste` | `satirlar`, `ogeler[2-5]` | çıkarım, kural, adım | 1,6 + 0,5 × madde |
| `soru` | `satirlar`, `alt?` | kapanış sorusu / çağrı | 3 |

Her sahnede `sure` (sn) zorunlu, `bolum` isteğe bağlı. Üst düzey: `marka` (sol üst ad),
`etiket?`, `tema?`, `sahneler`. Şema: `remotion/src/x/sema.ts`.

### 3. Taslak (hızlı bakış)
```bash
.venv/bin/python .claude/skills/x-animasyon/araclar/uret.py calisma/x-animasyon/<ad>.json --oran ikisi --taslak
```
Yarım boy, sessiz render + temas sayfası (`<ad>-<oran>-taslak-sessiz-sayfa.jpg`). Sayfayı
AÇ ve bak: taşan satır, üst üste binen öğe, okunmayan etiket, boş kalan büyük alan. Düzelt,
tekrar taslak al. Canlı düzenlemek için: `cd remotion && npx remotion studio`.

### 4. Render + ses
```bash
.venv/bin/python .claude/skills/x-animasyon/araclar/uret.py calisma/x-animasyon/<ad>.json --oran ikisi
```
Çıktılar `calisma/x-animasyon/`: `<ad>-16x9.mp4` (1920×1080, 60 fps) ve `<ad>-9x16.mp4`
(1080×1920, 30 fps), sesli. Ses seviyesi varsayılan **-26 LUFS**: konuşmanın (-14..-16) belirgin
altında, üstüne seslendirme ya da konuşan kafa gelirse boğmaz. Tek başına gönderilecekse
`--lufs -18`; müziksiz istenirse `--muziksiz`.

Adım adım (aynı şey):
```bash
cd remotion && npx remotion render XAnimasyon16x9 ../calisma/x-animasyon/<ad>-16x9-sessiz.mp4 \
    --props=../calisma/x-animasyon/<ad>.json --muted && cd ..
.venv/bin/python .claude/skills/x-animasyon/araclar/ses.py calisma/x-animasyon/<ad>.json \
    --video calisma/x-animasyon/<ad>-16x9-sessiz.mp4 --cikti calisma/x-animasyon/<ad>-16x9.mp4
```

### 5. Ölç — izleyemezsin, dinleyemezsin
`uret.py` sonunda `olc.py`'yi çalıştırır (elle: `olc.py <mp4> --json <json>`):
- kare sayısı ve süre JSON'dan beklenenle aynı mı, ses ile görüntü aynı uzunlukta mı;
- temas sayfası: her sahneden iki kare (ortası ve çıkıştan hemen önce) — mutlaka aç ve bak;
- entegre LUFS ve gerçek tepe; her kesimde whoosh yataktan kaç dB yukarıda (2 dB altı uyarı).
  Yazma sahnesinden hemen sonraki kesimde fark küçük çıkar: önceki pencerede tuş sesi var, normal.
Ölçemediğin şeyi (müzik hoş mu, ritim doğru mu) kullanıcıya açıkça bırak.

### 6. Teslim
Dosya yolları, süre, render süresi ve ölçüm özeti. Örnek veri kullanıldıysa bunu tekrar söyle.

## Görünüşü uyarlamak

- **Renk:** JSON'da `"tema": {"vurgu": "#38bdf8", "zemin": "#111113", "yazi": "#ece7df", "soluk": "#8b8883", "seri": [...]}`.
  Tek vurgu rengi kalsın; `seri` ölçer/sütun renkleri. Varsayılanlar `remotion/src/x/parcalar.tsx`.
- **Marka:** `"marka"` sol üstteki ad (kanalın ya da serinin adı).
- **Font:** yalnız dağıtımı serbest (OFL gibi) fontlar. TTF'yi ve lisans metnini `fontlar/`'a koy,
  `remotion/scripts/fontlari-kopyala.mjs` listesine ve `remotion/src/x/fontlar.ts` içindeki
  `YUZLER`'e ekle, `npm run fontlar`. İşletim sistemiyle gelen fontlar (macOS/Windows sistem
  fontları) repoya konmaz, dağıtılamaz.
- **Yerleşim:** iki yön `useDuzen()` içinde (`parcalar.tsx`). Dikeyde içerik y 300-1320 arası:
  Reels/Shorts arayüzü üstte ~190 px, altta ~520 px ve sağ alt köşeyi kapatır.
- Yeni sahne türü: `sema.ts`'e şema, `sahneler.tsx`'e bileşen, `SahneCiz`'e dal, `uret.py`
  `TURLER`'e ad. Klavye gibi sahne içi bir sese ihtiyacı varsa zamanını `zaman.ts` ile
  `araclar/ortak.py`'de AYNI formülle hesapla.

## Tuzaklar (ölçüldü)

- **Zaman tek kaynak:** `remotion/src/x/zaman.ts` ile `araclar/ortak.py` aynı hesabı yapar (kare
  yuvarlama, yazma ritmi). Birini değiştirip ötekini unutursan whoosh kesimden, tuş sesi harften kayar.
- Kompozisyon kimliğinde alt çizgi yok; `--props`'a JSON gömme, **dosya yolu** ver.
- Fontlar FontFace API ile yüklenir; `document.fonts.ready` beklenmez (uzun render'da bir sekmede
  hiç çözülmediği görüldü). Font yüklenemezse render hata verip durur, sessizce yedek fonta düşmez.
- Gren her karede SVG `feTurbulence` ile hesaplanmaz (render'ı kilitliyor): bir kez üretilen
  gürültü karosu kaydırılır.
- Türkçe büyük harf CSS ile (`lang="tr"` + `text-transform`): İ/ı doğru çıkar. JS'de `toUpperCase()` kullanma.
- Yazıya ölçek (zoom/pop) animasyonu verme: titriyor. Giriş = maskeden yükselme + saydamlık.
- Uzun 60 fps render takılırsa `--frames=0-899` gibi parçalara bölüp ffmpeg concat ile birleştir.
- Ölçülen render süresi (M1 Pro, 16 GB, varsayılan eşzamanlılık): 27,4 sn'lik örnek
  16:9@60 ~67 sn, 9:16@30 ~40 sn; taslak (yarım boy) 33 / 18 sn.

## Lisans notu: Remotion

Remotion MIT lisanslı **değildir**. Bireyler ve küçük şirketler için ücretsizdir; belli bir
büyüklüğün üstündeki şirketlerin ücretli lisans alması gerekir. Kullanmadan önce güncel
şartları kontrol et: https://www.remotion.dev/license — bu repodaki kod MIT'dir, Remotion'un
kendisi kendi lisansına tabidir.
