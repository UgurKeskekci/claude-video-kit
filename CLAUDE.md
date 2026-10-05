# Claude Video Kit — Claude için kurallar

Bu repo, konuşmalı videoları Claude Code ile kurgulamak için skill'ler içerir. Kullanıcı genelde
kendi kaydını verir ve "şunu kurgula", "bundan Reels çıkar", "X için animasyon yap" der.

- Skill'ler `.claude/skills/` altında. İşe başlamadan ilgili `SKILL.md`'yi oku.
- Her iş `calisma/<proje-adı>/` altında yürür (döküm, plan, ara dosyalar, çıktı). Bu klasör git'e girmez.
  Kullanıcının ham dosyalarını taşıma, silme, üzerine yazma; yalnız oku.
- Kararı ses verir: kesim noktaları sesin enerjisinden bulunur, Whisper kelimeleri yalnız neyin
  tutulacağını söyler (Whisper damgaları ~0,5 sn kayabilir).
- Bitti demeden ölç: çıktının süresini, sesini, birleşimlerini araçların denetim komutlarıyla doğrula;
  izleyemediğin şeyi ölçerek kontrol et (temas sayfası, ses seviyesi, yeniden çözülmüş döküm).
- Kullanıcının dili Türkçe ise Türkçe konuş. Ekrana yazı basılacaksa doğal, sade Türkçe kullan.
