---
name: animasyon
description: Kodla (görsel üretim modeli OLMADAN) hikâye anlatan kısa mürekkep çizgi animasyonu üretir — X/Twitter gönderisi, Reels/Shorts, YouTube video arası ya da soğuk açılış. Görüntü PIL mürekkep motoruyla, müzik ve efektler numpy sentezi ile aynı zaman programından üretilir, sonuç ölçülerek denetlenir. Şu durumlarda kullan: "animasyon yap", "çizgi animasyon", "halimi anlat", "durumumu göster", "twitter için animasyon", "reels animasyonu", "araya animasyon", "çöp adam animasyonu", "kodla video", "one-shot animasyon".
---

# Kodla mürekkep animasyonu

Kullanıcı bir DURUM ya da HİKÂYE anlatır ("bir haftadır sosyal medyadayım, delirdim"), sen onu
kısa, tek fikirli bir animasyona çevirirsin. Görsel üretim modeli yok: her çizgi kod, her ses
sentez. Telif derdi yok, sonuç deterministik ve kare kare düzeltilebilir.

Çalışan örnek (şablon olarak aç): `ornekler/animasyon-bir-hafta/` — 7 günlük zaman atlaması,
4:5, 17,7 sn, programla senkron müzik ve efektler.

Önce oku: [references/ilkeler.md](references/ilkeler.md) (neden işe yarar, platform tablosu,
konu bulma, dürüstlük) ve [references/tarifler.md](references/tarifler.md) (motor seçimi,
kompozisyon, karakter, ses, denetim — hepsi ölçülerek bulunmuş tuzaklar).

Komutlarda Python olarak `.venv/bin/python` kullan (Windows: `.venv\Scripts\python`).
Bağımlılık: numpy, Pillow, ffmpeg.

## Akış

### 1. Kısa tartış
Fikir belirsizse ya da kullanıcı "önce konuşalım" derse: **3-4 kavram** öner (her biri tek
cümle espri + neden işe yarar), birini öner. Tek soru turunda sor: fikir, oran (X 4:5 / 16:9,
Reels 9:16), süre. Kullanıcı "üretme, önce konuşalım" dediyse kod yazma.

### 2. Beat sheet — kod yazmadan önce
Saniye saniye plan: her vuruş = **tek görsel fikir + en fazla tek kısa cümle**.
- Süre: X 15-30 sn, Reels 20-40 sn, YouTube arası 3-8 sn. Kullanıcı kısa istiyorsa alt sınır.
- Yapı: **çapa** (köşede sabit sayaç: gün/yıl) + **tekrar eden karakter** + **sahne başına tek
  nesne** + **tırmanma** + **geri çağıran bitiş**. Bitiş başa bağlanırsa video döngüye girer.
- Sesin büyük anları (vuruş, kesim, sessizlik) plana o an yazılır, sonradan eklenmez.

### 3. Motor
- Çizim, karakter, parçacık, yığın → **bu skill**: `kit/murekkep.py` + `kit/sentez.py`.
- Sayı, yazı, grafik ağırlıklı hareketli grafik (sayaç, sütun, karşılaştırma) → **`x-animasyon`**
  skill'i (Remotion).

```python
import sys; sys.path.insert(0, ".claude/skills/animasyon/kit")
import murekkep as M, sentez as Z
```

Proje klasörü `calisma/<ad>/`: `anim.py` (görüntü + `program()`), `ses.py` (aynı programı okur).
Örneği kopyalayarak başla; yolları `KOK` ve `CIKTI` sabitlerinden değiştir.

| Parça | Ne verir |
|---|---|
| `M.Tuval(w, h)` | kâğıt dokulu zemin (2x çizilir, `bitir()` küçültür: yumuşak kenar) |
| `M.Kalem(d, kare, s, sc, ox, oy)` | kaynayan mürekkep çizgisi, daire, poligon, yazı; sahne dönüşümü |
| `M.Iskelet`, `M.yuru`, `M.poz_karistir` | eklemli karakter, prosedürel yürüme, poz geçişi |
| `M.yaz_mp4(kare_fn, sure, yol, w, h, ses=wav)` | kareleri ffmpeg'e borular, sesi ekler |
| `Z.harp/yayli/bas/flut/taiko` | enstrümanlar (perde ölçülerek düzeltildi) |
| `Z.whoosh/tus/yazma/ding/tik/hisirti/swell` | efektler (whoosh yumuşak, klavye insan ritminde) |
| `Z.yanki`, `Z.kes`, `Z.yaz_wav(buf, yol, lufs)` | yankı, komedi kesimi, hedef LUFS'ta wav |

### 4. Önizle → düzelt → render
Tam render'dan önce 4-6 anahtar kareyi PNG bas (örnekte `--kare 2,7.5,15.5`) ve kendin bak.
İlk turda hep bir şey çıkar: sıkışmış kompozisyon, metni örten nesne, tekrar eden metin,
görünmemesi gereken şeyin aralıktan görünmesi. Düzelt, sonra tam render. Önizlemeyi tam
render'la aynı komuta zincirleme: kare görülmeden uzun render biter.

### 5. Ölç — izleyemezsin, dinleyemezsin
```bash
.venv/bin/python .claude/skills/animasyon/kit/denetim.py calisma/<ad>/<ad>.mp4
```
Temas sayfası + LUFS/gerçek tepe + 0,5 sn ses profili + görsel geçişler. Sentez notası
değiştiyse `--perde`. Plan edilen sessizlik, vuruş ve kesim yerinde mi bak. Ölçemediğin şeyi
(tını güzel mi, espri komik mi) kullanıcıya açıkça bırak.

### 6. Teslim + gönderi metni
Dosya yolunu, süreyi, boyutu ve ölçüm özetini ver. Gönderi metni 2-3 satır: hikâyenin cümlesi.
**Dürüstlük:** "tek prompt / one-shot" iddiası YALNIZCA gerçekten tek seferde üretildiyse
yazılır; turlarla düzeltildiyse "tek seferde" deme. Hangi modelin ürettiğini doğru söyle.

## Kurallar

- Metin kaynatılmaz, ölçeklenmez; sahne başına tek satır. Emoji fontta yok.
- Hareketli nesne başlık/sayaç bandına girmez (girmeden söner).
- Tek vurgu rengi (mürekkep işinde bildirim kırmızısı); gerisi kâğıt + mürekkep.
- Dikey işte alt ~520 px ve sağ x > 900 platform arayüzü: oraya metin koyma.
- Ses: tek başına video -15 LUFS; altında konuşma olacaksa müzik konuşmanın belirgin altında.
  Müzik yalnız sentez ya da lisansı kullanıcı tarafından kontrol edilmiş kaynak.
- Ekranda ölçülmemiş sayı yok; örnek sayıysa bunu belli et.
- Yeni bir tuzak ölçtüysen `references/tarifler.md`'ye yaz; yeni kalıcı parça (geçiş, rig
  eklentisi) çıktıysa `kit/`'e al.
