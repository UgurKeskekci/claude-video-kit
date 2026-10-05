# yatay-kurgu örnek dosyaları

Medya yok; kendi kaydını kullan. Buradaki dosyalar `calisma/<proje>/` içine konacak girdilerin
biçimini gösterir. Normalde bunları Claude, dökümü okuduktan sonra kendisi yazar.

| Dosya | Ne işe yarar |
|---|---|
| `atilacak.ornek.json` | Atılacak aralıklar, her biri gerekçeli (yeniden başlama, kurgu notu, yanlış sayı, gereksiz detay, boşta kalan söz) |
| `bloklar.ornek.json` | Videonun bölümleri ve her bölümde ne görüneceği: `kamera`, `ekran`, `ekran-hizli` |
| `korunacak.ornek.json` | Bilerek yapılan tekrarın otomatik atılmaması için aralık |

Zamanlar ana kaydın (sesin geldiği kaydın) saniyesidir; `dokum.md`'deki `[baş–son]` sütunundan okunur.

## Elle denemek

```bash
./kur.sh                                     # ffmpeg + .venv + bağımlılıklar
K=".venv/bin/python .claude/skills/yatay-kurgu/araclar/kurgu.py"

$K dokum calisma/deneme --video kayit/kamera.mp4 --ekran kayit/ekran.mp4
# calisma/deneme/dokum.md'yi oku, sonra:
cp ornekler/yatay-kurgu/bloklar.ornek.json calisma/deneme/bloklar.json     # zamanları kendi kaydına göre düzelt
$EDITOR calisma/deneme/atilacak.json
$K kurgu calisma/deneme
$K senkron calisma/deneme
$K cek calisma/deneme
$K dogrula calisma/deneme
```

Asıl kullanım Claude Code içinde: "calisma/deneme için kayit/kamera.mp4'ü kurgula, ekran kaydı
kayit/ekran.mp4" demen yeterli; Claude `yatay-kurgu` skill'ini açar ve döngüyü kendisi yürütür.
