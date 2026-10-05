# senaryo.json alanları ve kart türleri

## Üst düzey

| Alan | Ne | Varsayılan |
|---|---|---|
| `vuruslar` | ekranın halleri, sırayla (aşağıda) | zorunlu |
| `tema` | `"acik"` (krem kâğıt, koyu mürekkep, mavi vurgu) / `"koyu"` ya da `{"ad": "acik", "vurgu": "#1E6FD9"}` | `acik` |
| `vurgu` | altyazıda italik + vurgu rengiyle çıkacak kelimeler (kök yeter: `"effort"` -> `effort'unu`) | yok |
| `altyazi_duzelt` | Whisper'ın yanlış yazdığı kelime -> doğrusu (`{"aranaya": "arenaya"}`) | yok |
| `kuyruk` | konuşma bittikten sonra son vuruşun ekranda kalma süresi (sn); görüntü donar | 0 |
| `efekt_fark` | efekt izinin konuşmanın kaç dB altında olacağı | 15 |

Tema renkleri (`araclar/cizim.py::TEMALAR`): `zemin`, `kart`, `murekkep`, `soluk`, `cizgi`,
`vurgu`, `vurgu_acik`, `terminal`, `terminal_yazi`, `yesil`, `kirmizi`, `balon_sen`, `balon_ai`;
hepsi `tema` sözlüğünde ezilebilir. Tek vurgu rengi kalsın; degrade, parıltı, neon kullanılmaz.

## Vuruş

```json
{"kelime": "plan modu", "kac": 1, "ofs": 0.0, "duzen": "bol", "kart": {...}}
```

| Alan | Ne |
|---|---|
| `kelime` | çıpa: kurguda kalan kelimenin BAŞI, birden çok kelime olabilir; önceki vuruştan sonra aranır. İlk vuruşta gerekmez (0'da başlar) |
| `kac` | çıpanın kaçıncı geçişi (önceki vuruştan sonra sayılır) |
| `ofs` | çıpaya eklenen saniye (ör. son kelimeden 0,5 sn sonra kapanış kartı) |
| `duzen` | `bol` / `yuz` / `grafik` (kart varsa `bol`, yoksa `yuz`) |
| `kart` | kart sözlüğü (`tur` + alanlar); `yuz` düzeninde yok |

Kart içindeki listelerin öğeleri (`satirlar`, `maddeler`, `mesajlar`) de `kelime` / `kac` / `ofs`
alabilir; çıpası olmayan öğe kartla birlikte, 0,12 sn arayla belirir. Kartın boyu son haline
göre hesaplanır: öğeler eklendikçe kart büyümez, yerinde dolar.

## Düzenler (1080x1920)

| duzen | Görünüş | Altyazı |
|---|---|---|
| `bol` | üstte kart (y 230-940), altta kenarlardan 24 px içeride yuvarlak yüz kartı (y 1070'ten) | dikişte, y ~1008, koyu |
| `yuz` | tam ekran yüz | çenenin altında (en az y 1290), beyaz + koyu kontur |
| `grafik` | tam ekran kart (y 250-1240, sağ kenar 940), yüz yok | y 1330, koyu |

Yüz kartının kırpması `kadraj.json`'dan gelir: yüz `bol`da 380 px, `yuz`da 560 px yükseklikte,
merkezi kartın üstünden 240 px (bol) / 800 px (yuz) aşağıda durur. Kaynak izin vermezse (yatay
kayıtta tam yüz) en yakın kırpma kullanılır. Değiştirmek için `kadraj.json`'a
`"bol": {"yuz_boy": 420, "merkez_y": 250}` gibi ekle.

## Kart türleri

| tur | Alanlar | Ses | Ne zaman |
|---|---|---|---|
| `baslik` | `etiket?` (küçük mono başlık), `satirlar` (`*kelime*` = italik vurgu), `alt?` | — | kanca, bölüm adı ("İkincisi: *plan* modu") |
| `liste` | `baslik?`, `isaret?` (`tik` / `carpi` / `sayi` / `nokta`), `maddeler [{yazi, kelime?, isaret?, ciz_kelime?}]` | madde başına pop, üstü çizilirken çizik | adımlar, artı/eksi, sayılan şeyler |
| `sohbet` | `baslik?`, `mesajlar [{kim: sen/ai, yazi, kelime?}]` | `sen` harf harf + klavye, `ai` üç nokta sonra pop | sorulan soru, verilen istem |
| `terminal` | `baslik?` (pencere adı), `satirlar [{yazi, tur?, kelime?}]`, `durum?` (alt satır) | `komut` harf harf + klavye, `tamam`/`hata` pop | komut, istem, çıktı |
| `agac` | `kok`, `satirlar [{yazi, vurgu?, kelime?}]` (iki boşluk = girinti, sonda `/` = klasör) | çıpalı satırda pop | proje/klasör düzeni, dosyanın yeri |
| `dosya` | `ad`, `satirlar [{yazi, kelime?}]` (`#` ile başlayan satır başlık), `yaz?` | `yaz` ise klavye, değilse çıpalı satırda pop | dosyanın içeriği (CLAUDE.md, ayar) |
| `sayi` | `deger`, `onek?`, `sonek?`, `etiket?`, `alt?`, `say?` (0'dan sayarak gelir) | inişte pop | tek, ÖLÇÜLMÜŞ sayı |
| `gorsel` | `yol` (proje klasörüne göre), `kesit? [x,y,w,h]`, `vurgu? [x,y,w,h]` + `vurgu_kelime`, `etiket?` | vurguda pop | kullanıcının GERÇEK ekran görüntüsü |
| `soru` | `soru` (`*kelime*` vurgu), `etiket?` (varsayılan "yorumlara yaz"), `anahtar?` (yorum kutusuna yazılır), `anahtar_kelime?`, `yer_tutucu?` | anahtar yazılırken klavye | kapanış: yorumlara yazdıran soru |

`terminal` satır türleri: `komut` (varsayılan, `>` ile başlar, harf harf yazılır), `cikti`,
`soluk`, `tamam` (yeşil onay), `hata` (kırmızı), `vurgu` (mavi).

`gorsel.kesit` ve `gorsel.vurgu` görüntünün kendi pikselindedir. Görüntü kartta yavaşça
(%3,5) yakınlaşır; vurgu kutusu soldan sağa dolar.

## Zaman ve ses

- Yazma hızı (harf/sn): terminal 26, sohbet 22, dosya 32, yorum kutusu 9. Klavye sesi aynı
  süreye insan ritminde (70-130 ms, ara sıra duraksama) yayılır: tek kaynak `kartlar.yazma()`.
- Whoosh her vuruş değişiminde, tepesi kesim anında. Efekt izi ölçülüp konuşmanın `efekt_fark`
  dB altına konur; konuşma -14 LUFS'a getirilir, yumuşak sınırlayıcı tepeyi ~-1,4 dBFS'te tutar.

## Ölçülenler (test: yatay 4K kamera kaydı, 42,7 sn'lik pencere, M1 Pro 16 GB)

- Render 40,97 sn'lik çıktı için ~35 sn (görüntü 26-28 ms/kare, ses 2 sn); makinede başka ağır
  iş (Whisper) varken ~73 sn. Kaynak yalnız kullanılan bölge kırpılıp çalışma ölçeğine (4K'da
  0,89) indirilerek okunur.
- Yatay kayıtta yüz karenin ortasındaysa `bol` düzendeki 826 px'lik yüz kartında çene y 1611'e
  iniyordu (alt %20'nin içi). Kart boyu artık yüzün altındaki kaynak görüntüsünden hesaplanıyor
  (o kayıtta 720 px) -> yüz y 1109-1511.
- Tam ekran yüzde (`yuz`) 4K yatay kaynaktan yüz 750 px kalıyor (daha fazla uzaklaşılamaz);
  altyazı y 1290'da ağza biniyordu, artık çenenin 75 px altına iniyor.
- AAC kodlaması gerçek tepeyi ~0,5 dB yükseltiyor: sınırlayıcı tavanı 0,85.
- Kapanış kartının yorum kutusu sağ sütuna giriyordu (x 971); `grafik` alanının sağ kenarı 940.
