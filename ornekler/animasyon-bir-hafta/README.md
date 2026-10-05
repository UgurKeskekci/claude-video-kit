# Örnek: "Bir haftadır sosyal medyadayım"

`animasyon` skill'inin çalışan örneği. Mürekkep çizgili, 7 günlük zaman atlaması:
1080×1350 (4:5), 30 fps, 17,7 sn. Görüntü PIL, ses numpy sentezi; dış dosya olarak yalnız
`fontlar/Caveat.ttf` kullanır.

```bash
.venv/bin/python ornekler/animasyon-bir-hafta/anim.py                    # -> calisma/animasyon/bir-hafta.mp4
.venv/bin/python ornekler/animasyon-bir-hafta/anim.py --kare 2,7.5,15.5  # önizleme kareleri
.venv/bin/python .claude/skills/animasyon/kit/denetim.py calisma/animasyon/bir-hafta.mp4
```

```
anim.py   görüntü: zamanlama program()'da; karakter, pencere, saat, uçan gönderiler, yığın
ses.py    ses: aynı programdan (balon -> ding, yığın kartı -> hışırtı, gün -> tik), -15 LUFS
```

Kurgu: 7 gün × 2,1 sn, her güne tek cümle. 5. günden itibaren gönderiler yere yığılır, 7. günün
sonunda karakteri gömer. 8. gün yığından bir el çıkar, kaydırmaya devam eder: "Bugün az
kullanacağım." Müzik 90'dan ~380 BPM'e hızlanır, 14,7 sn'de keskin kesilir, 1,2 sn
sessizlikten sonra "+1 yeni gönderi" ile tek ding.

Ölçülüp düzeltilenler: sahne ilk sürümde tuvalin üst %70'indeydi (`SC/OX/OY` dönüşümü); uçan
kartlar GÜN sayacının üstünden geçiyordu (y < 320'de sönüyorlar); sonda baş, yığının
aralığından görünüyordu (baş bölgesine 34 kartlık son kat).
