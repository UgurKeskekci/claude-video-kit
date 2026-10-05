# Dosyalar ve komut seçenekleri

Tüm iş tek klasörde döner (`calisma/<proje>/`). Ham videolar yalnızca okunur.

## Proje klasörü

| Dosya | Kim yazar | Ne |
|---|---|---|
| `kaynak.json` | dokum, senkron | ana kayıt ve ekran kaydının yolları, süre/boyut bilgisi |
| `ses16k.wav`, `ses48.wav` | dokum | ana kaydın sesi: döküm/zarf için 16 kHz, çıktı için 48 kHz mono |
| `transkript.json` | dokum | harfiyen kelimeler: `{"model","dil","istem","words":[{"start","end","word","prob"}]}` |
| `atilacak.json` | **Claude** | gerekçeli atma listesi (aşağıda) |
| `korunacak.json` | **Claude** (isteğe bağlı) | otomatik tekrar atmanın kapalı olduğu aralıklar, aynı biçim |
| `bloklar.json` | **Claude** (isteğe bağlı) | görüntü blokları (aşağıda) |
| `plan.json` | kurgu | parçalar: `{"fps","zoom","sayilar","parcalar":[{"blok","etiket","in","out","gorsel","hiz","zoom","kose","t"}]}` |
| `dokum.md` | kurgu | okunacak döküm: kalan metin + ATILDI / TEKRAR / [ADAY] / DÜŞTÜ satırları |
| `senkron.json` | senkron | `ekran_t = ana_t + ofset + kayma·ana_t`, pencere ölçümleri |
| `parca/` | cek | parça önbelleği (içerik değişmedikçe yeniden üretilmez) |
| `cikti/kurgu.mp4` | cek | sonuç |
| `kontrol/` | cek, dogrula, temas | kesik ses, yeniden çözüm, `temas.jpg`, ara görüntü |
| `dogrula.md` | dogrula | birleşim denetimi |

Zamanlar her yerde **kaynak saniyesi** (ana kaydın saniyesi). Yalnızca `dokum.md`'deki satır
başı (`MM:SS.ss`) ve `dogrula.md`'deki ilk sütun çıktı zamanıdır.

## atilacak.json / korunacak.json

```json
[
  {"bas": 31.20, "son": 36.85, "gerekce": "yeniden başlama: ilk deneme, ikincisi kalıyor"},
  {"bas": 102.40, "son": 104.10, "gerekce": "kurgu notu: 'bunu keseceğim'"}
]
```

- `bas` < `son`, `gerekce` boş olamaz (araç hata verir).
- Bir kelime, ORTASI aralığın içindeyse atılmış sayılır (Whisper başı erken damgaladığı için
  başlangıca bakılmaz). Kesim noktası aralık sınırının ±0,2 sn'si içindeki en kısık kareye oturur.
- Liste yerine `{"aralik": [...]}` biçimi de okunur.

## bloklar.json

```json
[
  {"etiket": "giriş", "bas": 0, "son": 95.5, "goruntu": "kamera"},
  {"etiket": "demo", "bas": 95.5, "son": 400, "goruntu": "ekran", "kose": true},
  {"etiket": "test koşuyor", "bas": 400, "son": 520, "goruntu": "ekran-hizli"}
]
```

- `goruntu`: `kamera` | `ekran` | `ekran-hizli`. `kose: false` o blokta köşe kamerasını kapatır.
- Bloklar sırayla birleştirilir; aralarındaki kaynak kullanılmaz (bilerek dışarıda bırakmak için
  blok koyma). Blok yoksa tüm kayıt tek `kamera` bloğu.

## Komutlar

`K` = `.venv/bin/python .claude/skills/yatay-kurgu/araclar/kurgu.py`

| Komut | Seçenekler |
|---|---|
| `K dokum P --video V` | `--ekran E` · `--model large-v3` (medium, small …) · `--dil tr` · `--cihaz auto\|cpu\|cuda` · `--terimler "…"` · `--sozluk dosya.json` · `--yeniden` · `--fps 30` · `--zoom 1.06` · `--serbest "adım,bilgi"` |
| `K kurgu P` | `--fps 30` (24, 25, 30, 48, 50, 60) · `--zoom 1.06` (1 = kapalı) · `--serbest …` |
| `K senkron P` | `--ekran E` · `--ofset 3.2` (ölçmeden elle) |
| `K cek P` | `--boyut 1920x1080` · `--kodlayici auto\|videotoolbox\|nvenc\|x264` · `--ekran-kirp genişlik:yükseklik:x:y` · `--kose sag-alt\|sol-alt\|sag-ust\|sol-ust\|yok` · `--kose-boyut 0.26` · `--kose-kirp 0.5,0.42,0.75` · `--kose-sekil daire\|yuvarlak` · `--ses temiz\|ham` · `--paralel 2` · `--bas N --bit M` · `--cikti dosya.mp4` |
| `K dogrula P` | `--model` (varsayılan: dökümdeki model) · `--cihaz` |
| `K pencere P t1 t2 …` | `--cikti` (zamanlar çıktı saniyesi) · `--pay 3` · `--model` |
| `K zarf P bas son` | — (her işaret 20 ms; `#` konuşma, `+` eşik üstü, `.` sessiz; plan varsa altında `=` kalan) |
| `K temas P` | `--cikti video.mp4` |

## Kodlayıcı

`auto`: macOS'ta `h264_videotoolbox` (çözmede de VideoToolbox), başka sistemde önce
`h264_nvenc`, olmazsa `libx264` (CRF 18). Listede olmak yetmez, her biri 0,1 sn'lik deneme
kodlamasıyla sınanır. Bit hızı 1080p için 14 Mbit/sn, piksel sayısıyla ölçeklenir.

## Yazı tipi

"2x" rozeti repo kökündeki `fontlar/IBMPlexMono-SemiBold.ttf` ile çizilir (SIL OFL). Başka
yazı tipi kullanılmaz.
