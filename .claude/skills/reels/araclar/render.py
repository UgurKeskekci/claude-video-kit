"""Kare kurma ve render: düzen (bol / yuz / grafik) + kart katmanı + yüz kartı + kelime kelime altyazı.

Altyazı Pillow ile çizilir (libass'lı ffmpeg gerekmez). Her 5 karede bir altyazının, kartın ve yüzün
piksel kutusu ölçülüp `kontrol/olcum.json`'a yazılır; denetim güvenli alanı bu ölçümden kontrol eder.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw

import cizim as C
import kartlar
from cizim import ALTYAZI_GEN, ALTYAZI_Y, FPS, H, W, YUZ_KARTI_R, YUZ_KARTI_UST, YUZ_KARTI_X, font
from kadraj import Kadraj, Okuyucu
from proje import json_yaz, norm

OLCUM_ARALIK = 5           # kaç karede bir piksel kutusu ölçülsün


class Sahne:
    """Bir render için sabitler: tema, zeminler, maske, kadraj, vurgu kelimeleri."""

    def __init__(self, P):
        self.P = P
        self.T = C.tema_kur(P.sen.get("tema"))
        self.zemin = Image.new("RGB", (W, H), self.T["zemin"])
        self.vurgu = tuple(norm(x) for x in P.sen.get("vurgu", []) if len(norm(x)) >= 2)
        kamerali = any(v["_duzen"] in ("bol", "yuz") for v in P.V)
        self.kd = Kadraj(P) if kamerali else None
        self.maske = None
        if self.kd:
            kw, kh = self.kd.hedef["bol"]["cikis"]
            m = Image.new("L", (kw, kh), 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, kw - 1, kh - 1], radius=YUZ_KARTI_R, fill=255)
            self.maske = m
        for v in P.V:
            k = v.get("kart")
            if k and k.get("tur") == "gorsel":
                yol = pathlib.Path(k["yol"])
                k["_yol"] = str(yol if yol.is_absolute() else (P.d / yol))
                if not pathlib.Path(k["_yol"]).exists():
                    raise SystemExit(f"görsel yok: {k['_yol']} (yol proje klasörüne göredir)")
            if k and k.get("tur") not in kartlar.CIZ:
                raise SystemExit(f"kart türü '{k.get('tur')}' yok; seçenekler: {', '.join(kartlar.CIZ)}")

    def istekler(self, kareler) -> list[tuple[str, float, float]]:
        out = []
        for n in kareler:
            v = self.P.vurus(n / FPS)
            if v["_duzen"] in ("bol", "yuz"):
                _, ts, z = self.P.kare_kaynagi(n)
                out.append((v["_duzen"], ts, z))
        return out


def _alfa_kutusu(im: Image.Image, oy: int = 0, esik: int = 100):
    b = im.getchannel("A").point(lambda v: 255 if v > esik else 0).getbbox()
    return None if b is None else [b[0], b[1] + oy, b[2], b[3] + oy]


def altyazi(S: Sahne, img: Image.Image, t: float, duzen: str, y: float | None = None):
    """Grubun söylenmiş kelimeleri; grup yerini ilk kelimede alır (kelimeler belirdikçe kaymaz)."""
    g = S.P.grup(t)
    if g is None:
        return None
    T = S.T
    boy_n, boy_v = 80, 94
    for _ in range(6):
        fn, fv = font("sans", boy_n, 800), font("serif_i", boy_v, 600)
        parca = [(w, fv if n.startswith(S.vurgu) else fn, n.startswith(S.vurgu), s) for w, s, n in g["kel"]]
        d = ImageDraw.Draw(img)
        bosluk = boy_n * 0.28
        gen = sum(d.textlength(w, font=f) for w, f, _, _ in parca) + bosluk * (len(parca) - 1)
        if gen <= ALTYAZI_GEN:
            break
        boy_n, boy_v = boy_n * 0.9, boy_v * 0.9
    yuz = duzen == "yuz"
    kat = Image.new("RGBA", (W, 240), (0, 0, 0, 0))
    kd = ImageDraw.Draw(kat)
    taban = 120 + boy_n * 0.36                      # yazı tabanı: büyük harf yüksekliğinin yarısı aşağıda
    x = W / 2 - gen / 2
    for w, f, vurgulu, s in parca:
        if s <= t + 1e-6:
            if yuz:
                renk_ = T["vurgu_acik"] if vurgulu else (255, 255, 255)
                kd.text((x, taban), w, font=f, fill=renk_, anchor="ls", stroke_width=7, stroke_fill=(18, 18, 20))
            else:
                renk_ = T["vurgu"] if vurgulu else T["murekkep"]
                kd.text((x, taban), w, font=f, fill=renk_, anchor="ls")
        x += kd.textlength(w, font=f) + bosluk
    oy = int((y or ALTYAZI_Y[duzen]) - 120)
    img.paste(kat, (0, oy), kat)
    return kat, oy


def kare_kur(S: Sahne, n: int, kaynak_kare, R: Okuyucu | None, olc: bool = False):
    """Çıktı karesi n -> (PIL RGB, ölçüm sözlüğü ya da None)."""
    P, T = S.P, S.T
    t = n / FPS
    v = P.vurus(t)
    duzen = v["_duzen"]
    _, ts, zoom = P.kare_kaynagi(n)
    olcum = {"t": round(t, 3), "duzen": duzen} if olc else None
    alt_y = None
    if duzen == "yuz":
        img = R.kes(kaynak_kare, "yuz", ts, zoom)
        yk = S.kd.cikti_kutusu("yuz", ts, zoom)
        # altyazı çenenin altına: yatay kayıttan dikey tam yüzde yüz büyük kalır, ağza binmesin
        alt_y = min(C.ALT_BANT - 70, max(ALTYAZI_Y["yuz"], yk[3] + 75))
        if olc:
            olcum["yuz"] = [round(x) for x in yk]
    else:
        img = S.zemin.copy()
        k = v["kart"]
        alan = C.KART_ALANI[duzen]
        ust = alan[3] + 60
        kat = Image.new("RGBA", (W, ust), (0, 0, 0, 0))
        c = C.Cizim(kat)
        kartlar.CIZ[k["tur"]](c, k, t, alan, T)
        u = C.ease(C.q(t, k["_t"], 0.24))
        if u < 1:                                   # kart girişi: kayarak + belirerek
            kat.putalpha(kat.getchannel("A").point(lambda a, u=u: int(a * u)))
        dy = int(round(26 * (1 - u)))
        img.paste(kat, (0, dy), kat)
        if olc:
            olcum["kart"] = _alfa_kutusu(kat, dy)
        if duzen == "bol":
            img.paste(R.kes(kaynak_kare, "bol", ts, zoom), (YUZ_KARTI_X, YUZ_KARTI_UST), S.maske)
            if olc:
                olcum["yuz"] = [round(x) for x in S.kd.cikti_kutusu("bol", ts, zoom)]
    a = altyazi(S, img, t, duzen, alt_y)
    if olc and a:
        olcum["altyazi"] = _alfa_kutusu(a[0], a[1])
    return img, olcum


# ------------------------------------------------------------------ önizleme kareleri
def varsayilan_kareler(P) -> list[float]:
    """Her vuruştan bir kare: kart dolmuş haliyle, değişimden hemen önce (girişi değil SONUCU gösterir)."""
    out = []
    for v in P.V:
        t = max(v["_t"] + 0.5, v["_bit"] - 0.35)
        out.append(round(min(t, v["_bit"] - 1 / FPS, P.sure - 1 / FPS), 2))
    return out


def kareler(P, zamanlar: list[float]) -> pathlib.Path:
    S = Sahne(P)
    kon = P.d / "kontrol"
    kon.mkdir(exist_ok=True)
    ns = [min(P.toplam_kare - 1, int(round(t * FPS))) for t in zamanlar]
    R = Okuyucu(P, S.kd, S.istekler(range(0, P.toplam_kare, 3))) if S.kd else None
    resimler = []
    for t, n in zip(zamanlar, ns):
        _, ts, _ = P.kare_kaynagi(n)
        v = P.vurus(n / FPS)
        kk = R.tek(ts) if (R and v["_duzen"] in ("bol", "yuz")) else None
        img, _ = kare_kur(S, n, kk, R)
        img.save(kon / f"kare-{t:.2f}.png")
        resimler.append((t, v, img))
    yol = kon / "kareler.jpg"
    temas_sayfasi(resimler, yol, P)
    print(f"{len(resimler)} kare -> {yol}  (Read ile bak; kırmızı taralı yerler platform arayüzünün altında)")
    return yol


def guvenli_alan_ciz(im: Image.Image, olcek: float) -> None:
    """Platform arayüzünün kapattığı yerleri ince kırmızı taramayla gösterir (yalnız kontrol resimlerinde)."""
    k = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(k)
    dolgu, cizgi = (230, 40, 40, 34), (235, 50, 50, 200)
    for b in ([0, 0, im.width - 1, C.UST_BANT * olcek], [0, C.ALT_BANT * olcek, im.width - 1, im.height - 1],
              [C.SAG_SUTUN_X * olcek, C.SAG_SUTUN_Y[0] * olcek, im.width - 1, C.SAG_SUTUN_Y[1] * olcek]):
        d.rectangle(b, fill=dolgu, outline=cizgi, width=1)
    im.paste(k, (0, 0), k)


def temas_sayfasi(resimler, yol: pathlib.Path, P, sutun: int = 6) -> None:
    tw, th = 300, 534
    satir = (len(resimler) + sutun - 1) // sutun
    sayfa = Image.new("RGB", (sutun * (tw + 12) + 12, satir * (th + 52) + 12), (24, 24, 27))
    d = ImageDraw.Draw(sayfa)
    f = font("mono", 17)
    for i, (t, v, img) in enumerate(resimler):
        kucuk = img.convert("RGB").resize((tw, th), Image.BILINEAR)
        guvenli_alan_ciz(kucuk, tw / W)
        x, y = 12 + (i % sutun) * (tw + 12), 12 + (i // sutun) * (th + 52)
        sayfa.paste(kucuk, (x, y))
        tur = (v.get("kart") or {}).get("tur", "yüz")
        d.text((x, y + th + 6), f"{t:5.2f} sn  {v['_duzen']}", font=f, fill=(235, 235, 235))
        d.text((x, y + th + 26), f"{tur}  '{v.get('kelime', '')}'"[:30], font=f, fill=(160, 160, 165))
    yol.parent.mkdir(parents=True, exist_ok=True)
    sayfa.save(yol, quality=86)


# ------------------------------------------------------------------ render
def kodlayici_arg(ad: str) -> list[str]:
    if ad == "videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", "12M"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "4"]


def render(P, kodlayici: str = "x264", cikti: str | None = None) -> pathlib.Path:
    import karisim
    t_bas = time.time()
    S = Sahne(P)
    cik, kon = P.d / "cikti", P.d / "kontrol"
    cik.mkdir(exist_ok=True)
    kon.mkdir(exist_ok=True)
    son = pathlib.Path(cikti) if cikti else cik / f"{P.ad}.mp4"
    print(f"render: {P.toplam_kare} kare ({P.sure:.2f} sn), {len(P.V)} vuruş", flush=True)
    # ses önce (hızlı): ölçüm ve efekt sayıları
    ses = karisim.karistir(P, kon, float(P.sen.get("efekt_fark", karisim.EFEKT_FARK)))
    t_ses = time.time() - t_bas
    R = Okuyucu(P, S.kd, S.istekler(range(0, P.toplam_kare, 2))) if S.kd else None
    if R:
        print(f"  kaynak bölgesi {R.u}, çalışma ölçeği {R.s:.3f} -> {R.ww}x{R.wh}", flush=True)
    sessiz = kon / "video-sessiz.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", *kodlayici_arg(kodlayici), "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(sessiz)], stdin=subprocess.PIPE)
    olcumler = []
    t_kare = time.time()
    try:
        for n in range(P.toplam_kare):
            v = P.vurus(n / FPS)
            kk = None
            if R and v["_duzen"] in ("bol", "yuz"):
                _, ts, _ = P.kare_kaynagi(n)
                kk = R.kare(int(round(ts * FPS)))
            img, olcum = kare_kur(S, n, kk, R, olc=(n % OLCUM_ARALIK == 0))
            if olcum:
                olcumler.append(olcum)
            enc.stdin.write(img.tobytes())
            if n % (FPS * 5) == 0:
                gecen = time.time() - t_kare
                print(f"  {n}/{P.toplam_kare} kare · {gecen:.0f} sn", flush=True)
    finally:
        enc.stdin.close()
        enc.wait()
        if R:
            R.kapat()
    t_goruntu = time.time() - t_kare
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(sessiz), "-i", str(kon / "ses.wav"), "-map", "0:v:0",
                    "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{P.sure:.3f}",
                    "-movflags", "+faststart", str(son)], check=True)
    sure = time.time() - t_bas
    json_yaz(kon / "olcum.json", {"video": str(son), "sure": P.sure, "kare": P.toplam_kare, "render_sn": round(sure, 1),
                                  "ses_sn": round(t_ses, 1), "goruntu_sn": round(t_goruntu, 1), "ses": ses,
                                  "olcumler": olcumler})
    print(f"yazıldı: {son}  ({P.sure:.2f} sn video, render {sure:.0f} sn: ses {t_ses:.0f}, görüntü {t_goruntu:.0f} "
          f"= {t_goruntu / max(P.toplam_kare, 1) * 1000:.0f} ms/kare)", flush=True)
    return son
