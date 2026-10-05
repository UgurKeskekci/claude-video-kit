# reels örneği: "Claude Code'da işini kolaylaştıracak 3 şey"

Medya yok; kendi kaydını kullan. `senaryo.ornek.json`, aşağıdaki okuma metnini kameraya okuyan
bir kayıt için yazılmış kart senaryosudur: CLAUDE.md, plan modu ve skill. Dokuz kart türünün
hepsi bir arada görünsün diye seçildi (sayı, dosya ağacı, dosya, terminal, başlık, ekran görüntüsü,
liste, sohbet, kapanış sorusu).

## Okuma metni (~95 kelime, 35-40 sn)

> Claude Code kullanıyorsan işini kolaylaştıracak üç şey var. Birincisi CLAUDE.md. Projenin
> köküne bir dosya koyuyorsun, kurallarını içine yazıyorsun. Claude her oturumda önce bu dosyayı
> okuyor. Terminalde /init yazarsan ilk taslağı kendisi çıkarıyor. İkincisi plan modu. Shift Tab'a
> iki kez basıyorsun. Claude kod yazmadan önce bir plan çıkarıyor, sen onaylamadan hiçbir dosyaya
> dokunmuyor. Üçüncüsü skill. Sık yaptığın bir işi bir klasöre SKILL.md olarak yazıyorsun. O iş
> gelince Claude onu kendisi açıp kullanıyor. Sen bunlardan hangisini kullanıyorsun? Yorumlara yaz.

Kameraya bakarak oku; takılırsan cümleyi baştan söyle (araç ve Claude son denemeyi tutar).
Metni birebir okumak şart değil, ama kendi cümlelerinle söylediysen kart çıpalarını
`reels.py kelimeler` çıktısına göre değiştirmen gerekir (Claude bunu kendisi yapar).

## Dosyalar

| Dosya | Ne |
|---|---|
| `senaryo.ornek.json` | Vuruşlar: hangi kart hangi kelimede girer. `calisma/reels/<ad>/senaryo.json` olarak kopyalanır |
| `gorsel/plan-modu.png` | **Senin** ekran görüntün (repoda yok): terminalin plan modundayken alınmış gerçek görüntüsü. Yoksa o vuruşu senaryodan sil |

## Elle denemek

```bash
./kur.sh
R=".venv/bin/python .claude/skills/reels/araclar/reels.py"
P=calisma/reels/uc-sey

$R dokum $P --video kayit/reels.mp4 --terimler "CLAUDE.md, plan modu, skill, init"
# $P/dokum.md'yi oku, gerekirse $P/atilacak.json yaz, sonra:
$R kurgu $P
$R kelimeler $P
cp ornekler/reels/senaryo.ornek.json $P/senaryo.json   # çıpaları kelimeler çıktısına göre düzelt
mkdir -p $P/gorsel && cp kayit/plan-modu.png $P/gorsel/plan-modu.png
$R vuruslar $P
$R yuz $P          # kontrol/kadraj.jpg'ye bak
$R kare $P         # kontrol/kareler.jpg'ye bak
$R render $P       # cikti/uc-sey.mp4 + kontrol/olcum.md + kontrol/temas.jpg
```

Asıl kullanım Claude Code içinde: "kayit/reels.mp4'ten kartlı bir Reels çıkar" demen yeterli;
Claude `reels` skill'ini açar, dökümü okur, senaryoyu yazar, render alır ve ölçer.

## Kurallar (kısaca)

- Kart yalnız gerçekte olanı gösterir: komut, dosya adı, ekran yazısı uydurulmaz; sayı ölçülmüş olmalı.
- Yüz yalnız kameraya bakılan cümlede; ekrana bakarak okunan yer `grafik` düzeni.
- Altyazı ve kartlar Instagram arayüzünün altına (üst 220 px, alt %20, sağ sütun) girmez;
  `render` bunu piksel piksel ölçüp `kontrol/olcum.md`'ye yazar.
