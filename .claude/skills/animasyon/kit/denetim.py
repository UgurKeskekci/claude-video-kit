"""Bitmiş animasyonu ÖLÇEREK denetler — izleyemeyen/dinleyemeyen biri için göz ve kulak.

    python3 .claude/skills/animasyon/kit/denetim.py video.mp4            # hepsi
    python3 .claude/skills/animasyon/kit/denetim.py video.mp4 --sayfa    # yalnız temas sayfası
    python3 .claude/skills/animasyon/kit/denetim.py video.mp4 --lufs     # yalnız ses yüksekliği
    python3 .claude/skills/animasyon/kit/denetim.py --perde              # sentez notalarının perdesi

  sayfa    her N sn'den kare -> <video>-sayfa.jpg (zaman damgalı); KOMPOZİSYON ve metin
           çakışması buradan görülür (örnekteki ilk sürümde sahne tuvalin üst %70'ine sıkışmıştı,
           uçan kartlar başlığı örtüyordu — ikisi de yalnızca bu sayfada göründü)
  lufs     entegre ses yüksekliği (LUFS), gerçek tepe (dBTP), LRA — hedefe uyuyor mu
  ses      0,5 sn'lik dilimlerde dBFS; sessizlik/vuruş anları plana uyuyor mu
  gecis    görsel geçişler (kare farkı tepeleri) + verilen BPM ızgarasına sapma
  perde    harp()/flut() notalarının ölçülen perdesi (cent) ve temel/2. harmonik oranı
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw


def sayfa(video, adim=1.5, sutun=6, gen=320):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                               capture_output=True, text=True).stdout)
    ts = np.arange(adim / 2, dur, adim)
    ims = []
    for t in ts:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf",
                            f"scale={gen}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        from io import BytesIO
        if not r.stdout:          # son kare sınırında ffmpeg boş dönebiliyor (ölçüldü)
            continue
        im = Image.open(BytesIO(r.stdout)).convert("RGB")
        ImageDraw.Draw(im).text((4, 4), f"{t:.1f}", fill=(220, 30, 30))
        ims.append(im)
    w, h = ims[0].size
    sat = (len(ims) + sutun - 1) // sutun
    s = Image.new("RGB", (w * sutun, h * sat), (20, 20, 20))
    for i, im in enumerate(ims):
        s.paste(im, ((i % sutun) * w, (i // sutun) * h))
    yol = str(pathlib.Path(video).with_suffix("")) + "-sayfa.jpg"
    s.save(yol, quality=85)
    print("sayfa:", yol)


def lufs(video):
    """ffmpeg ebur128: entegre LUFS, LRA, gerçek tepe. Ses yoksa None."""
    import re
    r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", video, "-vn", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    ozet = r.stderr[r.stderr.rfind("Summary:"):]
    if "Summary:" not in r.stderr:
        print("ses yok")
        return None
    bul = lambda d: float(m.group(1)) if (m := re.search(d, ozet)) else float("nan")  # noqa: E731
    o = {"I": bul(r"I:\s+(-?[\d.]+) LUFS"), "LRA": bul(r"LRA:\s+(-?[\d.]+) LU"), "TP": bul(r"Peak:\s+(-?[\d.]+) dBFS")}
    print(f"ses yüksekliği: {o['I']:.1f} LUFS · gerçek tepe {o['TP']:.1f} dBTP · LRA {o['LRA']:.1f} LU")
    return o


def ses(video, dilim=0.5):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                       capture_output=True).stdout
    a = np.frombuffer(r, np.int16).astype(float) / 32768
    if not len(a):
        print("ses yok")
        return
    n = int(8000 * dilim)
    for i in range(0, len(a), n):
        db = 20 * np.log10(np.sqrt((a[i:i + n] ** 2).mean()) + 1e-9)
        print(f"{i / 8000:6.1f} {db:6.1f} {'#' * int(max(0, db + 50))}")


def gecis(video, bpm=None):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", "fps=10,scale=96:54", "-f", "rawvideo",
                        "-pix_fmt", "gray", "-"], capture_output=True).stdout
    k = np.frombuffer(r, np.uint8).reshape(-1, 54, 96).astype(float)
    d = np.abs(np.diff(k, axis=0)).mean(axis=(1, 2))
    esik = np.percentile(d, 92)
    tepe = [i / 10 + 0.1 for i in range(1, len(d) - 1) if d[i] > esik and d[i] >= d[i - 1] and d[i] >= d[i + 1]]
    g = []
    for x in tepe:
        if not g or x - g[-1] > 0.6:
            g.append(x)
    g = np.array(g)
    print(f"{len(g)} geçiş, aralık medyan {np.median(np.diff(g)) if len(g) > 1 else 0:.2f} sn:", np.round(g, 1))
    if bpm and len(g):
        vur = 60 / bpm
        off = np.abs(g / vur - np.round(g / vur))
        print(f"{bpm} BPM ızgarası: sapma medyan {np.median(off):.2f} vuruş; <0,15 olan {(off < 0.15).sum()}/{len(g)}")


def perde():
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import sentez as Z
    for m in (45, 57, 62, 69, 74, 81, 93):
        for ad, x in (("harp", Z.harp(m)), ("flut", Z.flut(m, 1.0))):
            x = x[: Z.SR]
            X = np.abs(np.fft.rfft(x * np.hanning(len(x)), 8 * len(x)))
            f = np.fft.rfftfreq(8 * len(x), 1 / Z.SR)
            f0 = Z.hz(m)
            h = f[np.argmax(X)]
            h1, h2 = (X[np.argmin(abs(f - k * f0))] for k in (1, 2))
            print(f"{ad} {m:3d} {f0:7.1f} Hz  ölçülen {h:7.1f}  {1200 * np.log2(h / f0):+6.1f} cent  h2/h1 {h2 / h1:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--sayfa", action="store_true")
    ap.add_argument("--ses", action="store_true")
    ap.add_argument("--lufs", action="store_true")
    ap.add_argument("--gecis", action="store_true")
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--perde", action="store_true")
    a = ap.parse_args()
    if a.perde:
        perde()
    if a.video:
        hepsi = not (a.sayfa or a.ses or a.gecis or a.lufs)
        if a.sayfa or hepsi:
            sayfa(a.video)
        if a.lufs or hepsi:
            lufs(a.video)
        if a.ses or hepsi:
            ses(a.video)
        if a.gecis or hepsi:
            gecis(a.video, a.bpm)
