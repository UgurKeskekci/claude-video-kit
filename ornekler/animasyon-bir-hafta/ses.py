"""Ses — anim.py'nin programından (aynı kartlar, balonlar, yığın) üretilir; senkron kaymaz.

  melodi   pentatonik arp motifi; tempo 1. gün 90 BPM -> 7. gün sonu ~380 BPM (üstel), perde +3 yarım ton
  tik      her gün başında tahta tik
  ding     her bildirim balonunda (balonun x'ine göre pan)
  hışırtı  yığına düşen her kartta kâğıt sesi
  bitiş    7. günün sonunda HER ŞEY kesilir; 1,2 sn sessizlik; "+1 yeni gönderi" ile tek ding
Tamamen numpy sentezi (telifsiz): `.claude/skills/animasyon/kit/sentez.py`.

    python3 ornekler/animasyon-bir-hafta/ses.py        # yalnız ses -> calisma/animasyon/bir-hafta.wav
    (anim.py bunu kendisi çağırır; ayrıca çalıştırmak gerekmez)
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
KOK = HERE.parents[1]
sys.path.insert(0, str(KOK / ".claude" / "skills" / "animasyon" / "kit"))
import sentez as Z  # noqa: E402

MOTIF = [0, 4, 7, 9, 12, 9, 7, 4, 2, 4, 7, 12, 14, 12, 9, 7]      # Do majör pentatonik (kök 60)
BAS_N = [36, 36, 33, 33, 29, 29, 31, 31]


def uret(A, yol) -> pathlib.Path:
    """A: anim modülü (SURE, BITIS, GUN, GUN_SAYI, BALONLAR_P, YIGIN). -15 LUFS wav yazar."""
    SR = Z.SR
    n = int((A.SURE + 0.5) * SR)
    muz = np.zeros((n, 2))
    efekt = np.zeros((n, 2))
    # melodi: üstel hızlanan sekizlikler
    t, i = 0.35, 0
    while t < A.BITIS - 0.02:
        bpm = 90 * 2 ** (t / A.BITIS * 2.08)          # 90 -> ~380
        perde = int(3 * t / A.BITIS)
        m = 60 + MOTIF[i % len(MOTIF)] + perde
        Z.ekle(muz, Z.harp(m, 1.2, parlak=0.6), t, 0.3 + 0.4 * ((i * 5) % 7) / 7, 0.8)
        if i % 4 == 0:
            Z.ekle(muz, Z.harp(BAS_N[(i // 4) % 8] + 12 + perde, 1.4, parlak=0.3), t, 0.5, 0.9)
        t += 60 / bpm / 2
        i += 1
    for g in range(A.GUN_SAYI):
        Z.ekle(efekt, Z.tik(), g * A.GUN + 0.02, 0.5)
    for b in A.BALONLAR_P:
        Z.ekle(efekt, Z.ding(), b["t"], min(0.9, max(0.1, b["x"] / 900)))
    for c in A.YIGIN:
        Z.ekle(efekt, Z.hisirti(), c["t"] + 0.28, min(0.9, max(0.1, c["x"] / 800)))
    # bitiş: keskin kesim (15 ms), sessizlik, tek ding — en güçlü an sessizlik
    Z.kes(muz, A.BITIS)
    Z.kes(efekt, A.BITIS)
    Z.ekle(efekt, Z.ding(1.3), A.BITIS + 1.2, 0.5)
    Z.ekle(efekt, Z.tik(), A.BITIS + 0.02, 0.5, 0.6)
    mix = Z.yanki(muz, 1.8, 0.25) + efekt
    yol = pathlib.Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    Z.yaz_wav(mix, str(yol), lufs=-15)
    return yol


if __name__ == "__main__":
    sp = importlib.util.spec_from_file_location("anim", HERE / "anim.py")
    A = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(A)
    print("ses yazıldı:", uret(A, KOK / "calisma" / "animasyon" / "bir-hafta.wav"))
