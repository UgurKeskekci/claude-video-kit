# Claude Video Kit

Kendi çektiğin konuşma videolarını Claude Code ile kurgulamak için skill'ler. Kaydı veriyorsun,
Claude dökümü okuyup neyi atacağını gerekçesiyle yazıyor, kesimi sesin kendisinden yapıyor ve
çıkan videoyu yeniden dinleyip denetliyor. Son dokunuş (vurgu, mizah, ritim) sende kalıyor.

Ücretli bir kurgu programı yok: konuşmayı yazıya Whisper döküyor, videoyu ffmpeg kesiyor,
animasyonları Remotion ve Python çiziyor. Hepsi kendi bilgisayarında çalışıyor.

## İçinde ne var

| Skill | Ne yapar | Çıktı |
|---|---|---|
| `yatay-kurgu` | Yatay YouTube kaydının kaba kurgusu: duraklamalar, yeniden başlamalar, "burayı keseceğim" notları gider. Kamera ile ekran kaydını sesten eşler. | mp4 (16:9) |
| `reels` | Kamera kaydından dikey Reels/Shorts: üstte konuşmaya senkron kartlar, altta yüz, kelime kelime altyazı, yumuşak geçiş sesleri. | mp4 (9:16) |
| `x-animasyon` | Sayı ve yazıyla hikâye anlatan hareketli grafik (Remotion). X gönderisi, Reels ya da video arası için. | mp4 (16:9 ve 9:16) |
| `animasyon` | Görsel üretim modeli olmadan, tamamen kodla çizilmiş kısa mürekkep animasyonu; müzik ve efektler de kodla. | mp4 |

Her skill `.claude/skills/<ad>/SKILL.md` içinde adım adım anlatılıyor. Claude işe başlamadan
o dosyayı okuyor; senin okuman gerekmiyor.

## Kurulum

Gerekenler: Claude Code (Claude aboneliği), macOS, [Homebrew](https://brew.sh). Animasyon
skill'leri için ayrıca Node 18+.

```bash
git clone https://github.com/UgurKeskekci/claude-video-kit.git
cd claude-video-kit
./kur.sh
```

`kur.sh` ffmpeg'i, Python sanal ortamını (`.venv`) ve bağımlılıkları kurar. Remotion tarafı
için bir kez:

```bash
cd remotion && npm install
```

En kolayı: klasörde Claude Code'u açıp **"bu repoyu kur"** demek. Gerisini o halleder.

İlk dökümde Whisper modeli iner (large-v3, yaklaşık 3 GB); ilk Remotion render'ı da Chrome
Headless Shell'i indirir (yaklaşık 100 MB).

## Kullanım

Claude Code'u bu klasörde aç ve ne istediğini söyle:

```text
~/Movies/kayit.mp4'ü kurgula. Ekran kaydı ~/Movies/ekran.mp4.
```

```text
Bu kayıttan 40 saniyelik bir Reels çıkar: ~/Movies/kamera.mp4
```

```text
Şu testin sonucunu X için 20 saniyelik bir animasyona çevir: ...
```

Her iş `calisma/<proje>/` altında yürür: döküm, atılacaklar listesi, ara dosyalar ve çıktı
orada. Bu klasör git'e girmez. Ham dosyalarına dokunulmaz, yalnız okunur.

### Yatay kurgu nasıl çalışıyor

1. **Döküm:** konuşma kelimesi kelimesine yazıya dökülür. Takılmalar, yeniden başlamalar,
   sesli kurgu notları da metinde kalır.
2. **Atılacaklar:** Claude dökümü baştan sona okur ve her kesimi gerekçesiyle yazar
   (`atilacak.json`). Duraklamaları ve art arda tekrarları araçlar zaten kendisi bulur.
3. **Kesim sesten:** Whisper'ın zaman damgaları yarım saniye kayabiliyor. Kesim noktası bu
   yüzden sesin en kısık anına oturtulur; kelimenin ortasından kesilmez.
4. **Denetim:** kesilmiş ses yeniden yazıya dökülür ve her birleşime bakılır: kopan kelime
   var mı, atılması gereken bir söz hâlâ duyuluyor mu.

Çıktı bir mp4. CapCut ya da başka bir programa atıp cilasını orada yaparsın.

## Klasörler

```
.claude/skills/   dört skill ve araçları
ornekler/         her skill için örnek girdi dosyaları (medya yok)
remotion/         x-animasyon'un Remotion projesi
fontlar/          açık lisanslı fontlar (OFL)
tests/            kesim mantığının testleri
calisma/          senin işlerin (git'e girmez)
```

Testler: `.venv/bin/python tests/test_kesim.py`

## Platform

macOS'ta (Apple Silicon) geliştirildi ve denendi. Windows'ta Python ve ffmpeg kuruluysa
araçlar çalışmalı ama düzenli denenmedi; komutlarda `.venv/bin/python` yerine
`.venv\Scripts\python` kullan. NVIDIA ekran kartı varsa döküm CUDA ile çok daha hızlı.

## Lisans

Bu repodaki kod [MIT](LICENSE). Fontlar SIL Open Font License ile dağıtılıyor, lisansları
`fontlar/` içinde.

**Remotion MIT değildir.** Bireyler, en fazla 3 çalışanı olan şirketler ve kâr amacı
gütmeyen kuruluşlar ücretsiz kullanabilir; daha büyük şirketlerin ücretli şirket lisansı
alması gerekir. Güncel koşullar: [remotion.dev/license](https://www.remotion.dev/license).
`x-animasyon` dışındaki skill'ler Remotion kullanmaz.

## Tam sürüm

Kendi kanalımda bunun genişletilmiş hâlini kullanıyorum: kurguyu doğrudan CapCut'a zaman
çizelgesi olarak yazan kısım, tıklanarak anlatılan sunumlar, kapak şablonları gibi ek
parçalar. Onları [YouTube kanalımın](https://www.youtube.com/@UgurKeskekciYazilim) katıl
kısmında paylaşıyorum. Bu repo tek başına çalışır, eksik bir parçası yok.
