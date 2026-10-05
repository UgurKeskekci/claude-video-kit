"""Bitmiş x-animasyon videosunu ÖLÇER — izleyemeyen biri için göz ve kulak.

    python3 olc.py video.mp4 --json sahneler.json            # rapor + temas sayfası
    python3 olc.py video.mp4 --json sahneler.json --profil   # + 0,5 sn'lik ses profili

  süre      video/ses süresi ve kare sayısı, JSON'dan beklenenle karşılaştırılır
  sayfa     her sahneden iki kare (ortası ve çıkıştan hemen önce) -> <video>-sayfa.jpg
            taşan yazı, çakışan öğe, okunmayan etiket buradan görülür
  ses       entegre LUFS, gerçek tepe; her kesimde whoosh, çevresindeki yataktan kaç dB yukarıda
"""
from __future__ import annotations

import argparse
import io
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ortak as O  # noqa: E402
from ses import ebur128  # noqa: E402


def _kare(video, t, gen):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={gen}:-2", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def sayfa(video, z, dikey: bool) -> str:
    gen, sutun = (270, 8) if dikey else (480, 4)
    yazi = ImageFont.truetype(str(O.KOK / "fontlar" / "IBMPlexMono-Medium.ttf"), 15)
    kareler = []
    for x in z:
        son = x is z[-1]
        for t, ad in ((x["bas_sn"] + 0.45 * (x["bit_sn"] - x["bas_sn"]), "orta"),
                      (x["bit_sn"] - (0.08 if son else 0.36), "son")):
            im = _kare(video, t, gen)
            if im is None:
                continue
            d = ImageDraw.Draw(im)
            etiket = f"{x['i'] + 1:02d} {x['tur']} {ad} {t:.2f}s"
            d.rectangle([0, 0, d.textlength(etiket, font=yazi) + 10, 22], fill=(0, 0, 0))
            d.text((5, 2), etiket, font=yazi, fill=(255, 210, 60))
            kareler.append(im)
    w, h = kareler[0].size
    sat = (len(kareler) + sutun - 1) // sutun
    s = Image.new("RGB", (w * sutun + 4 * (sutun - 1), h * sat + 4 * (sat - 1)), (60, 60, 60))
    for i, im in enumerate(kareler):
        s.paste(im, ((i % sutun) * (w + 4), (i // sutun) * (h + 4)))
    yol = str(pathlib.Path(video).with_suffix("")) + "-sayfa.jpg"
    s.save(yol, quality=88)
    return yol


def _ses(video, sr=16000):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True).stdout
    return np.frombuffer(r, np.int16).astype(float) / 32768


def _db(a):
    return 20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-9) if len(a) else -99.0


def whoosh_kontrol(a, z, sr=16000):
    """Kesim anındaki pencere [-0,3, +0,05] ile önceki yatağın [-1,2, -0,5] farkı (dB)."""
    out = []
    for x in z[1:]:
        c = x["bas_sn"]
        on = a[int((c - 1.2) * sr):int((c - 0.5) * sr)]
        an = a[int((c - 0.3) * sr):int((c + 0.05) * sr)]
        out.append((c, _db(an) - _db(on)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--json", required=True)
    ap.add_argument("--profil", action="store_true", help="0,5 sn'lik ses profili de bas")
    ap.add_argument("--sayfasiz", action="store_true")
    a = ap.parse_args()
    js = O.oku(a.json)
    vb = O.video_bilgi(a.video)
    fps = int(round(vb["fps"]))
    z = O.zamanla(js["sahneler"], fps)
    beklenen_kare = z[-1]["bas"] + z[-1]["uz"]
    satir = []
    satir.append(f"video   {vb['w']}x{vb['h']} @ {vb['fps']:.2f} fps · {vb['kare']} kare (beklenen {beklenen_kare}) · "
                 f"görüntü {vb['v_sure']:.3f} sn · ses {vb['a_sure'] if vb['a_sure'] is not None else '-'} sn")
    if vb["kare"] is not None and vb["kare"] != beklenen_kare:
        satir.append(f"  UYARI: kare sayısı tutmuyor ({vb['kare']} != {beklenen_kare})")
    if vb["a_sure"] is not None and abs(vb["a_sure"] - vb["v_sure"]) > 0.05:
        satir.append(f"  UYARI: ses ve görüntü süresi farklı ({vb['a_sure']:.3f} / {vb['v_sure']:.3f})")
    satir.append("sahneler " + " | ".join(f"{x['i'] + 1}:{x['tur']} {x['bas_sn']:.2f}-{x['bit_sn']:.2f}" for x in z))
    if not a.sayfasiz:
        satir.append("sayfa   " + sayfa(a.video, z, vb["h"] > vb["w"]))
    if vb["a_sure"] is not None:
        e = ebur128(a.video)
        satir.append(f"ses     {e['I']:.1f} LUFS · gerçek tepe {e['TP']:.1f} dBTP · LRA {e['LRA']:.1f} LU")
        sr = 16000
        ses = _ses(a.video, sr)
        wk = whoosh_kontrol(ses, z, sr)
        zayif = [c for c, d in wk if d < 2.0]
        satir.append("whoosh  " + " ".join(f"{c:.2f}s:+{d:.1f}dB" if d >= 0 else f"{c:.2f}s:{d:.1f}dB" for c, d in wk)
                     + ("" if not zayif else f"   UYARI: {len(zayif)} kesimde whoosh duyulmuyor (<2 dB)"))
        harf = sum(len(x["sahne"]["metin"]) for x in z if x["tur"] == "yazi")
        if harf:
            satir.append(f"klavye  {harf} harf, ilk tuş {next(x['bas_sn'] for x in z if x['tur'] == 'yazi') + O.YAZ_BASLA:.2f} sn")
        if a.profil:
            n = sr // 2
            for i in range(0, len(ses), n):
                db = _db(ses[i:i + n])
                satir.append(f"  {i / sr:6.1f} {db:6.1f} {'#' * int(max(0, db + 60) / 1.5)}")
    rapor = "\n".join(satir)
    print(rapor)
    pathlib.Path(str(pathlib.Path(a.video).with_suffix("")) + "-olcum.txt").write_text(rapor + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
