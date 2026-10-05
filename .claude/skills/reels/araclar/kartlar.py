"""Kart türleri: üst alanda arayüz benzeri sade kartlar. Her biri `ciz(c, k, t, alan, T)`:

    c     Cizim (kart katmanı, mutlak 1080x1920 koordinatı)
    k     kart sözlüğü; çıpalar çözülmüş: k["_t"] kartın girişi, öğelerde o["_t"], `*_kelime` -> `*_t`
    t     çıktı saniyesi
    alan  (x0, y0, x1, y1): kartın sığması gereken dikdörtgen (düzene göre)
    T     tema renkleri

Her kartın sesi `olaylar(k)` ile aynı zaman hesabından çıkar (yazı yazılırken klavye, öğe girerken pop).
Kartın boyu SON haline göre hesaplanır: öğeler eklendikçe kart büyümez, yerinde dolar.

| tur      | alanlar |
|----------|---------|
| baslik   | etiket?, satirlar [str | {yazi, kelime}] (`*kelime*` vurgu), alt? |
| liste    | baslik?, maddeler [{yazi, kelime?, isaret? (tik/carpi/sayi/nokta), ciz_kelime?}], isaret? |
| sohbet   | baslik?, mesajlar [{kim: sen/ai, yazi, kelime?}] |
| terminal | baslik?, satirlar [{yazi, tur? (komut/cikti/tamam/hata/soluk/vurgu), kelime?}], durum? |
| agac     | kok, satirlar [{yazi ("  " girinti, sonda "/" klasör), vurgu?, kelime?}] |
| dosya    | ad, satirlar [{yazi ("#" başlık), kelime?}], yaz? (harf harf + klavye) |
| sayi     | deger, onek?, sonek?, etiket?, alt?, say? (sayarak gelir) |
| gorsel   | yol (proje klasörüne göre), kesit? [x,y,w,h], vurgu? [x,y,w,h], vurgu_kelime?, etiket? |
| soru     | soru, etiket?, anahtar? (yorum kutusuna yazılır), anahtar_kelime? |
"""
from __future__ import annotations

import math
import pathlib
import zlib

import numpy as np
from PIL import Image, ImageDraw

from cizim import (Cizim, W, carpi, ease, font, golge, karis, katman, q, sar, tik,
                   vurgulu_parcalar)

GIRIS = 0.22          # öğe giriş süresi (kayarak + belirerek)
SATIR, SATIR_PAY = 70, 34   # liste: satır yüksekliği, madde başına dikey pay
PENCERE_GEN = 940     # kart penceresinin genişliği


# ------------------------------------------------------------------ yazma takvimi (görüntü + ses tek kaynak)
def yazma(metin: str, t0: float, cps: float) -> tuple[float, list[float]]:
    """Harf harf yazılan metin: (bitiş süresi, tuş sesi zamanları). Görünen harf sayısı
    `harf_sayisi` ile aynı hızdan hesaplanır; ses insan ritminde (70-130 ms, ara sıra duraksama)."""
    sure = len(metin) / cps
    rng = np.random.default_rng(zlib.crc32(metin.encode("utf-8")))
    zaman, x = [], t0
    while x < t0 + sure:
        zaman.append(x)
        x += rng.uniform(0.07, 0.13) + (rng.uniform(0.06, 0.15) if rng.random() < 0.08 else 0.0)
    return sure, zaman


def harf_sayisi(metin: str, t0: float | None, t: float, cps: float) -> int:
    if t0 is None or t < t0:
        return 0
    return min(len(metin), int((t - t0) * cps) + 1)


CPS = {"komut": 26.0, "sohbet": 22.0, "dosya": 32.0, "anahtar": 9.0}


def buyuk(s: str) -> str:
    """Türkçe büyük harf: str.upper() 'Birincisi'yi 'BIRINCISI' yapıyordu (i -> İ, ı -> I olmalı)."""
    return s.replace("i", "İ").replace("ı", "I").upper()


# ------------------------------------------------------------------ ortak parçalar
def _yatay(alan) -> tuple[float, float]:
    """Pencerenin yatay sınırları: alanın ortasında, en çok PENCERE_GEN genişlikte."""
    g = min(PENCERE_GEN, (alan[2] - alan[0]) - 10)
    cx = (alan[0] + alan[2]) / 2
    return cx - g / 2, cx + g / 2


def _merkez_y(alan, h):
    return (alan[1] + alan[3]) / 2 - h / 2


def pencere(c: Cizim, x0, y0, x1, y1, T, koyu=False, baslik=None, mono_baslik=True) -> float:
    """Gölgeli yuvarlak pencere + başlık şeridi. İçeriğin başladığı y'yi döndürür."""
    golge(c, x0, y0, x1, y1, r=28, guc=70 if not koyu else 90)
    dolgu = T["terminal"] if koyu else T["kart"]
    kenar = karis(dolgu, (128, 128, 128), 0.25) if koyu else T["cizgi"]
    c.kutu(x0, y0, x1, y1, r=28, dolgu=dolgu, cizgi=kenar, w=2)
    nokta = karis(dolgu, (150, 150, 150), 0.55)
    for i in range(3):
        c.elips(x0 + 30 + 28 * i, y0 + 30, x0 + 48 + 28 * i, y0 + 48, dolgu=nokta)
    if baslik:
        f = font("mono" if mono_baslik else "sans", 32, 500)
        c.yazi(((x0 + x1) / 2, y0 + 49), baslik, f, karis(dolgu, (128, 128, 128), 0.8 if koyu else 0.9), anchor="ms")
    cy = y0 + 80
    c.cizgi([(x0 + 2, cy), (x1 - 2, cy)], kenar, 2)
    return cy


def _isaret(c, tur, x, y, u, T, sira=1):
    """Madde işareti (x, y = satırın orta noktasının solu)."""
    if u <= 0:
        return
    if tur == "tik":
        c.elips(x - 27, y - 27, x + 27, y + 27, dolgu=T["vurgu"])
        tik(c, x - 14, y + 1, (255, 255, 255), 0.95, w=5)
    elif tur == "carpi":
        c.elips(x - 27, y - 27, x + 27, y + 27, dolgu=karis(T["kirmizi"], (255, 255, 255), 0.82))
        carpi(c, x, y, T["kirmizi"], 0.78)
    elif tur == "sayi":
        c.elips(x - 28, y - 28, x + 28, y + 28, dolgu=T["vurgu"])
        c.yazi((x, y + 1), str(sira), font("sans", 34, 800), (255, 255, 255), anchor="mm")
    else:
        c.elips(x - 11, y - 11, x + 11, y + 11, dolgu=T["vurgu"])


# ------------------------------------------------------------------ baslik
def baslik(c: Cizim, k, t, alan, T):
    cx = (alan[0] + alan[2]) / 2
    satirlar = k.get("satirlar", [])
    # boy: en uzun satır alana sığacak kadar büyük (tek kelimelik başlık 200 px'e kadar)
    boy = 200
    while boy > 90:
        f, fi = font("serif", boy, 500), font("serif_i", boy, 500)
        en_genis = max([sum(c.uzunluk(s_, fi if v else f) for s_, v in vurgulu_parcalar(o["yazi"])) for o in satirlar] or [0])
        if en_genis <= (alan[2] - alan[0]) - 80:
            break
        boy -= 8
    ara = int(boy * 1.12)
    h = (100 if k.get("etiket") else 0) + ara * len(satirlar) + (90 if k.get("alt") else 0)
    y = _merkez_y(alan, h)
    if k.get("etiket"):
        et = buyuk(k["etiket"])
        fe = font("mono_kalin", 38)
        katman(c, (alan[0], y, alan[2], y + 60), lambda cc: aralikli(cc, (cx, y + 42), et, fe, T["vurgu"], 6),
               q(t, k["_t"], GIRIS))
        y += 100
    for o in satirlar:
        parcalar = vurgulu_parcalar(o["yazi"])
        gen = sum(c.uzunluk(s, fi if v else f) for s, v in parcalar)
        yb = y + boy * 0.86

        def ciz(cc, parcalar=parcalar, gen=gen, yb=yb):
            x = cx - gen / 2
            for s, v in parcalar:
                cc.yazi((x, yb), s, fi if v else f, T["vurgu"] if v else T["murekkep"])
                x += cc.uzunluk(s, fi if v else f)
        katman(c, (cx - gen / 2 - 10, y, cx + gen / 2 + 10, y + ara + 10), ciz, q(t, o["_t"], GIRIS + 0.08), dy=18)
        y += ara
    if k.get("alt"):
        fa = font("sans", 44, 500)
        katman(c, (alan[0], y, alan[2], y + 80), lambda cc: cc.yazi((cx, y + 60), k["alt"], fa, T["soluk"], anchor="ms"),
               q(t, k.get("alt_t", k["_t"] + 0.35), GIRIS))


def aralikli(c: Cizim, xy, s, f, renk_, aralik=4, anchor="ms"):
    """Harf aralıklı küçük etiket (mono, büyük harf)."""
    gen = sum(c.uzunluk(ch, f) for ch in s) + aralik * (len(s) - 1)
    x = xy[0] - gen / 2 if anchor == "ms" else xy[0]
    for ch in s:
        c.yazi((x, xy[1]), ch, f, renk_)
        x += c.uzunluk(ch, f) + aralik


# ------------------------------------------------------------------ liste
def liste(c: Cizim, k, t, alan, T):
    f = font("sans", 58, 600)
    fb = font("serif", 74, 600)
    x0, x1 = _yatay(alan)
    tx = x0 + 136
    maddeler = k.get("maddeler", [])
    satirlar = [sar(c, o["yazi"], f, x1 - tx - 50) for o in maddeler]
    bas_h = 140 if k.get("baslik") else 44
    h = bas_h + sum(SATIR_PAY + SATIR * len(s) for s in satirlar) + 44
    y0 = _merkez_y(alan, h)
    golge(c, x0, y0, x1, y0 + h)
    c.kutu(x0, y0, x1, y0 + h, r=28, dolgu=T["kart"], cizgi=T["cizgi"], w=2)
    y = y0 + 44
    if k.get("baslik"):
        c.yazi((x0 + 54, y + 66), k["baslik"], fb, T["murekkep"])
        c.cizgi([(x0 + 54, y + 100), (x1 - 54, y + 100)], T["cizgi"], 2)
        y += 100
    for i, (o, ss) in enumerate(zip(maddeler, satirlar)):
        yh = SATIR_PAY + SATIR * len(ss)
        u = q(t, o["_t"], GIRIS)
        isaret = o.get("isaret", k.get("isaret", "tik"))
        cizik = o.get("ciz_t") is not None and t >= o["ciz_t"]
        renk_ = T["soluk"] if cizik else T["murekkep"]
        ym = y + SATIR_PAY / 2 + SATIR * len(ss) / 2

        def ciz(cc, ss=ss, y=y, ym=ym, isaret=isaret, i=i, renk_=renk_, u=u):
            _isaret(cc, isaret, x0 + 84, ym, 1, T, i + 1)
            for j, s in enumerate(ss):
                cc.yazi((tx, y + SATIR_PAY / 2 + SATIR * j + 56), s, f, renk_)
        katman(c, (x0 + 30, y, x1 - 20, y + yh), ciz, u, dy=16)
        if cizik:
            v = ease(q(t, o["ciz_t"], 0.25))
            for j, s in enumerate(ss):
                yy = y + SATIR_PAY / 2 + SATIR * j + 36
                c.cizgi([(tx - 6, yy + 2), (tx - 6 + (c.uzunluk(s, f) + 12) * v, yy - 2)], T["kirmizi"], 7)
        y += yh


def liste_olay(k):
    ev = [(o["_t"], "pop") for o in k.get("maddeler", [])]
    ev += [(o["ciz_t"], "cizik") for o in k.get("maddeler", []) if o.get("ciz_t") is not None]
    return ev


# ------------------------------------------------------------------ sohbet
def sohbet(c: Cizim, k, t, alan, T):
    f = font("sans", 52, 500)
    x0, x1 = _yatay(alan)
    mesajlar = k.get("mesajlar", [])
    ic_gen = 660
    bloklar = []
    for m in mesajlar:
        ss = sar(c, m["yazi"], f, ic_gen)
        bloklar.append((m, ss, 50 + 66 * len(ss)))
    icerik = sum(b[2] + 26 for b in bloklar)
    h = min(alan[3] - alan[1], 140 + icerik + 34)
    y0 = _merkez_y(alan, h)
    golge(c, x0, y0, x1, y0 + h)
    c.kutu(x0, y0, x1, y0 + h, r=28, dolgu=T["kart"], cizgi=T["cizgi"], w=2)
    c.elips(x0 + 36, y0 + 30, x0 + 96, y0 + 90, dolgu=T["vurgu"])
    c.yazi((x0 + 66, y0 + 61), buyuk((k.get("baslik") or "S")[:1]), font("sans", 34, 700), (255, 255, 255), anchor="mm")
    c.yazi((x0 + 118, y0 + 76), k.get("baslik", "Sohbet"), font("sans", 42, 650), T["murekkep"])
    c.cizgi([(x0 + 2, y0 + 120), (x1 - 2, y0 + 120)], T["cizgi"], 2)
    # görünen mesajlar; taşarsa eskiler yukarı kayar (pencere içinde kırpılır)
    gorunen = [(m, ss, yh) for m, ss, yh in bloklar if m.get("_t") is not None and t >= m["_t"]]
    toplam = sum(yh + 24 for _, _, yh in gorunen)
    alan_h = h - 120 - 34
    kay = max(0.0, toplam - alan_h)
    ic = Image.new("RGBA", (int(x1 - x0 - 4), int(alan_h + 10)), (0, 0, 0, 0))
    cc = Cizim(ic, x0 + 2, y0 + 140)
    y = y0 + 140 - kay
    for m, ss, yh in gorunen:
        sen = m.get("kim", "sen") == "sen"
        gen = max(cc.uzunluk(s, f) for s in ss) + 64
        bx0 = x1 - 36 - gen if sen else x0 + 36
        u = q(t, m["_t"], 0.18)
        dolgu = T["balon_sen"] if sen else T["balon_ai"]
        if sen:
            n = harf_sayisi(m["yazi"], m["_t"], t, CPS["sohbet"])
            kalan = n
        else:
            kalan = 10 ** 6 if t >= m["_t"] + 0.45 else -1

        def ciz(k2, bx0=bx0, y=y, gen=gen, yh=yh, ss=ss, kalan=kalan, dolgu=dolgu):
            k2.kutu(bx0, y, bx0 + gen, y + yh, r=30, dolgu=dolgu)
            if kalan < 0:
                for j in range(3):
                    k2.elips(bx0 + 32 + 28 * j, y + yh / 2 - 8, bx0 + 48 + 28 * j, y + yh / 2 + 8, dolgu=T["vurgu"])
                return
            kk = kalan
            for j, s in enumerate(ss):
                k2.yazi((bx0 + 32, y + 25 + 66 * j + 48), s[:max(0, kk)], f, T["murekkep"])
                kk -= len(s) + 1
        katman(cc, (bx0, y, bx0 + gen, y + yh), ciz, u, dy=12)
        y += yh + 26
    c.yapistir(ic, x0 + 2, y0 + 140)


def sohbet_olay(k):
    ev = []
    for m in k.get("mesajlar", []):
        if m.get("kim", "sen") == "sen":
            _, z = yazma(m["yazi"], m["_t"], CPS["sohbet"])
            ev += [(x, "tus") for x in z]
        else:
            ev.append((m["_t"] + 0.45, "pop"))
    return ev


# ------------------------------------------------------------------ terminal
def terminal(c: Cizim, k, t, alan, T):
    f = font("mono", 44)
    x0, x1 = _yatay(alan)
    satirlar = k.get("satirlar", [])
    # satır başı payı: komutta "> " (vurgu renginde), tamam/hata'da işaret; metin bu payın sağından sarılır
    pay = {"komut": c.uzunluk("> ", f), "tamam": 56, "hata": 56}
    sarili = [(o, sar(c, o["yazi"], f, x1 - x0 - 100 - pay.get(o.get("tur", "komut"), 0))) for o in satirlar]
    h = 104 + sum(66 * len(ss) + 12 for _, ss in sarili) + 44 + (70 if k.get("durum") else 0)
    h = max(h, 340)
    y0 = _merkez_y(alan, h)
    pencere(c, x0, y0, x1, y0 + h, T, koyu=True, baslik=k.get("baslik", "terminal"))
    renkler = {"komut": T["terminal_yazi"], "cikti": karis(T["terminal_yazi"], T["terminal"], 0.35),
               "soluk": karis(T["terminal_yazi"], T["terminal"], 0.55), "tamam": T["yesil"],
               "hata": T["kirmizi"], "vurgu": T["vurgu_acik"]}
    y = y0 + 116
    for o, ss in sarili:
        tur = o.get("tur", "komut")
        if o.get("_t") is None or t < o["_t"]:
            break
        # komut harf harf yazılır (ses: terminal_olay, aynı metin ve hız); "> " de yazılan metne dahil
        kk = harf_sayisi("> " + o["yazi"], o["_t"], t, CPS["komut"]) - 2 if tur == "komut" else 10 ** 6
        tx = x0 + 48 + pay.get(tur, 0)
        if tur == "komut":
            c.yazi((x0 + 48, y + 48), ">", f, T["vurgu_acik"])
        elif tur == "tamam":
            tik(c, x0 + 52, y + 31, T["yesil"], 1.0)
        elif tur == "hata":
            carpi(c, x0 + 66, y + 33, T["kirmizi"], 0.8)
        for s_ in ss:
            c.yazi((tx, y + 48), s_[:max(0, kk)], f, renkler.get(tur, renkler["komut"]))
            kk -= len(s_) + 1
            y += 66
        y += 12
    if k.get("durum"):
        yd = y0 + h - 46
        c.cizgi([(x0 + 30, yd - 42), (x1 - 30, yd - 42)], karis(T["terminal"], (128, 128, 128), 0.3), 2)
        c.yazi((x0 + 48, yd), k["durum"], font("mono", 32), T["vurgu_acik"])


def terminal_olay(k):
    ev = []
    for o in k.get("satirlar", []):
        if o.get("_t") is None:
            continue
        tur = o.get("tur", "komut")
        if tur == "komut":
            _, z = yazma("> " + o["yazi"], o["_t"], CPS["komut"])
            ev += [(x, "tus") for x in z]
        elif tur in ("tamam", "hata"):
            ev.append((o["_t"], "pop"))
    return ev


# ------------------------------------------------------------------ agac
def _klasor(c, x, y, s, renk_):
    c.kutu(x, y - 14 * s, x + 18 * s, y - 6 * s, r=3, dolgu=renk_)
    c.kutu(x, y - 9 * s, x + 40 * s, y + 18 * s, r=5, dolgu=renk_)


def _dosya_ikon(c, x, y, s, renk_, zemin):
    c.cokgen([(x + 4 * s, y - 16 * s), (x + 24 * s, y - 16 * s), (x + 34 * s, y - 6 * s), (x + 34 * s, y + 20 * s),
              (x + 4 * s, y + 20 * s)], dolgu=zemin, cizgi=renk_)
    for r in range(3):
        c.cizgi([(x + 10 * s, y - 2 * s + r * 7 * s), (x + 28 * s, y - 2 * s + r * 7 * s)], renk_, 2)


def agac(c: Cizim, k, t, alan, T):
    f = font("mono", 48)
    fk = font("mono_kalin", 48)
    x0, x1 = _yatay(alan)
    satirlar = k.get("satirlar", [])
    sat_h = min(88, int(((alan[3] - alan[1]) - 150) / max(1, len(satirlar))))
    h = 100 + 20 + sat_h * len(satirlar) + 30
    y0 = _merkez_y(alan, h)
    pencere(c, x0, y0, x1, y0 + h, T, baslik=k.get("kok", "proje/"))
    y = y0 + 110
    klasor_renk = karis(T["vurgu"], T["kart"], 0.45)
    for o in satirlar:
        ham = o["yazi"]
        girinti = (len(ham) - len(ham.lstrip(" "))) // 2
        ad = ham.strip()
        x = x0 + 56 + girinti * 56
        vurgu = o.get("vurgu")
        u = q(t, o["_t"], GIRIS)

        def ciz(cc, x=x, y=y, ad=ad, vurgu=vurgu, girinti=girinti):
            if vurgu:
                cc.kutu(x0 + 22, y + 6, x1 - 22, y + sat_h - 6, r=14, dolgu=karis(T["vurgu"], T["kart"], 0.86))
                cc.kutu(x0 + 22, y + 14, x0 + 30, y + sat_h - 14, r=3, dolgu=T["vurgu"])
            if girinti:
                cc.cizgi([(x - 30, y + 4), (x - 30, y + sat_h / 2), (x - 10, y + sat_h / 2)], T["cizgi"], 2)
            if ad.endswith("/"):
                _klasor(cc, x, y + sat_h / 2 - 4, 1.25, klasor_renk)
            else:
                _dosya_ikon(cc, x, y + sat_h / 2 - 2, 1.25, T["soluk"], T["kart"])
            cc.yazi((x + 76, y + sat_h / 2 + 16), ad, fk if vurgu else f, T["vurgu"] if vurgu else T["murekkep"])
        katman(c, (x0 + 10, y, x1 - 10, y + sat_h), ciz, u, dy=12)
        y += sat_h


def agac_olay(k):
    return [(o["_t"], "pop") for o in k.get("satirlar", []) if o.get("kelime")]


# ------------------------------------------------------------------ dosya
def dosya(c: Cizim, k, t, alan, T):
    f = font("mono", 42)
    fh = font("mono_kalin", 50)
    x0, x1 = _yatay(alan)
    satirlar = k.get("satirlar", [])
    sarili = [(o, sar(c, o["yazi"], fh if o["yazi"].startswith("#") else f, x1 - x0 - 100)) for o in satirlar]
    h = 100 + 24 + sum((76 if o["yazi"].startswith("#") else 62) * len(ss) + 8 for o, ss in sarili) + 34
    y0 = _merkez_y(alan, h)
    pencere(c, x0, y0, x1, y0 + h, T, baslik=k.get("ad", "dosya.md"))
    y = y0 + 114
    for o, ss in sarili:
        if o.get("_t") is None or t < o["_t"]:
            break
        bas = o["yazi"].startswith("#")
        ff = fh if bas else f
        n = harf_sayisi(o["yazi"], o["_t"], t, CPS["dosya"]) if k.get("yaz") else 10 ** 6
        u = 1.0 if k.get("yaz") else q(t, o["_t"], GIRIS)
        yh = (76 if bas else 62) * len(ss)

        def ciz(cc, ss=ss, y=y, ff=ff, bas=bas, n=n):
            kk = n
            for j, s in enumerate(ss):
                cc.yazi((x0 + 54, y + (76 if bas else 62) * j + 50), s[:max(0, kk)], ff,
                        T["vurgu"] if bas else T["murekkep"])
                kk -= len(s) + 1
        katman(c, (x0 + 30, y, x1 - 20, y + yh + 10), ciz, u, dy=10)
        y += yh + 8


def dosya_olay(k):
    ev = []
    for o in k.get("satirlar", []):
        if k.get("yaz"):
            _, z = yazma(o["yazi"], o["_t"], CPS["dosya"])
            ev += [(x, "tus") for x in z]
        elif o.get("kelime"):
            ev.append((o["_t"], "pop"))
    return ev


# ------------------------------------------------------------------ sayi
def _sayi_metni(k, u):
    d = str(k["deger"])
    if k.get("say"):
        try:
            hedef = float(d.replace(",", "."))
            ondalik = len(d.split(",")[1]) if "," in d else (len(d.split(".")[1]) if "." in d else 0)
            v = hedef * ease(u)
            d = f"{v:.{ondalik}f}".replace(".", ",") if ondalik else str(int(round(v)))
        except ValueError:
            pass
    return f"{k.get('onek', '')}{d}{k.get('sonek', '')}"


def sayi(c: Cizim, k, t, alan, T):
    cx = (alan[0] + alan[2]) / 2
    u_say = q(t, k["_t"] + 0.1, 0.7) if k.get("say") else 1.0
    metin = _sayi_metni(k, u_say)
    boy = 360
    f = font("sans", boy, 800)
    while c.uzunluk(_sayi_metni(k, 1.0), f) > (alan[2] - alan[0]) - 60 and boy > 120:
        boy -= 20
        f = font("sans", boy, 800)
    h = boy * 0.9 + (110 if k.get("etiket") else 0) + (70 if k.get("alt") else 0)
    y = _merkez_y(alan, h)
    katman(c, (alan[0], y - 20, alan[2], y + boy), lambda cc: cc.yazi((cx, y + boy * 0.78), metin, f, T["murekkep"], anchor="ms"),
           q(t, k["_t"], GIRIS), dy=20)
    y += boy * 0.9
    if k.get("etiket"):
        fe = font("sans", 62, 600)
        katman(c, (alan[0], y, alan[2], y + 100),
               lambda cc: cc.yazi((cx, y + 70), k["etiket"], fe, T["soluk"], anchor="ms"),
               q(t, k.get("etiket_t", k["_t"] + 0.2), GIRIS), dy=12)
        y += 110
    if k.get("alt"):
        fa = font("mono_kalin", 36)
        katman(c, (alan[0], y, alan[2], y + 60),
               lambda cc: aralikli(cc, (cx, y + 40), buyuk(k["alt"]), fa, T["vurgu"], 4),
               q(t, k.get("alt_t", k["_t"] + 0.4), GIRIS), dy=8)


def sayi_olay(k):
    return [(k["_t"] + (0.8 if k.get("say") else 0.0), "pop")]


# ------------------------------------------------------------------ gorsel
_RESIM: dict = {}


def _resim(yol):
    if yol not in _RESIM:
        _RESIM[yol] = Image.open(yol).convert("RGB")
    return _RESIM[yol]


def gorsel(c: Cizim, k, t, alan, T):
    yol = pathlib.Path(k["_yol"])
    im = _resim(str(yol))
    kx, ky, kw, kh = k.get("kesit") or [0, 0, im.width, im.height]
    ust_pay = 60 if k.get("etiket") else 0
    mg, mh = (alan[2] - alan[0]) - 20, (alan[3] - alan[1]) - 20 - ust_pay
    oran = min(mg / kw, mh / kh)
    gw, gh = int(kw * oran), int(kh * oran)
    cx = (alan[0] + alan[2]) / 2
    x0 = int(cx - gw / 2)
    y0 = int(_merkez_y(alan, gh + ust_pay) + ust_pay)
    z = 1 + 0.035 * min(1.0, max(0.0, t - k["_t"]) / 4.0)          # yavaş yakınlaşma
    dw, dh = kw / z, kh / z
    kutu = (kx + (kw - dw) / 2, ky + (kh - dh) / 2, kx + (kw + dw) / 2, ky + (kh + dh) / 2)
    parca = im.resize((gw, gh), Image.BILINEAR, box=kutu)
    if k.get("etiket"):
        katman(c, (alan[0], y0 - ust_pay, alan[2], y0), lambda cc: aralikli(cc, (cx, y0 - 22), buyuk(k["etiket"]),
                                                                            font("mono_kalin", 30), T["vurgu"], 4),
               q(t, k["_t"], GIRIS), dy=8)
    golge(c, x0, y0, x0 + gw, y0 + gh, r=22)
    maske = Image.new("L", (gw, gh), 0)
    ImageDraw.Draw(maske).rounded_rectangle([0, 0, gw - 1, gh - 1], radius=22, fill=255)
    c.yapistir(parca.convert("RGBA"), x0, y0, maske)
    c.kutu(x0, y0, x0 + gw, y0 + gh, r=22, cizgi=T["cizgi"], w=2)
    v = k.get("vurgu")
    if v and k.get("vurgu_t") is not None and t >= k["vurgu_t"]:
        uu = ease(q(t, k["vurgu_t"], 0.35))
        sx = x0 + (v[0] - kutu[0]) * gw / dw
        sy = y0 + (v[1] - kutu[1]) * gh / dh
        sw, sh = v[2] * gw / dw, v[3] * gh / dh
        kat = Image.new("RGBA", (max(1, int(sw * uu)), max(1, int(sh))), T["vurgu"] + (70,))
        c.yapistir(kat, sx, sy)
        c.kutu(sx - 4, sy - 4, sx + sw * uu + 4, sy + sh + 4, r=8, cizgi=T["vurgu"], w=4)


def gorsel_olay(k):
    return [(k["vurgu_t"], "pop")] if k.get("vurgu_t") is not None else []


# ------------------------------------------------------------------ soru (kapanış)
def soru(c: Cizim, k, t, alan, T):
    cx = (alan[0] + alan[2]) / 2
    duz = k["soru"].replace("*", "")
    # boy: soru en çok iki satıra sığsın (104 -> 80 px)
    for boy in (104, 96, 88, 80):
        fs, fi = font("serif", boy, 500), font("serif_i", boy, 500)
        satirlar = []
        for p in duz.split("\n"):
            satirlar += sar(c, p, fs, (alan[2] - alan[0]) - 60)
        if len(satirlar) <= 2:
            break
    ara = int(boy * 1.16)
    h = (90 if k.get("etiket", "x") else 0) + ara * len(satirlar) + 70 + 140
    y = _merkez_y(alan, h)
    et = k.get("etiket", "yorumlara yaz")
    if et:
        katman(c, (alan[0], y, alan[2], y + 64), lambda cc: aralikli(cc, (cx, y + 44), buyuk(et), font("mono_kalin", 38),
                                                                     T["vurgu"], 6), q(t, k["_t"], GIRIS), dy=8)
        y += 90
    vurgular = sorted({p for p, v in vurgulu_parcalar(k["soru"]) if v}, key=len, reverse=True)
    for i, s in enumerate(satirlar):
        yb = y + boy * 0.92

        def ciz(cc, s=s, yb=yb):
            # *vurgu* kelimenin başıysa (effort'u) yalnız o kısım italik + vurgu rengi, ek düz kalır
            parca = []
            for j, w in enumerate(s.split(" ")):
                v = next((v for v in vurgular if w.startswith(v)), None)
                on = " " if j else ""
                parca += [(on + v, fi, T["vurgu"]), (w[len(v):], fs, T["murekkep"])] if v else [(on + w, fs, T["murekkep"])]
            gen = sum(cc.uzunluk(x, f) for x, f, _ in parca)
            x = cx - gen / 2
            for yz, f, r in parca:
                cc.yazi((x, yb), yz, f, r)
                x += cc.uzunluk(yz, f)
        katman(c, (alan[0], y, alan[2], y + ara + 4), ciz, q(t, k["_t"] + 0.08 * (i + 1), GIRIS), dy=16)
        y += ara
    y += 70
    # yorum kutusu
    bx0, bx1 = cx - min(430, (alan[2] - alan[0]) / 2 - 5), cx + min(430, (alan[2] - alan[0]) / 2 - 5)
    ua = q(t, k["_t"] + 0.3, GIRIS)
    anahtar = k.get("anahtar", "")
    at = k.get("anahtar_t", k["_t"] + 0.7)
    n = harf_sayisi(anahtar, at, t, CPS["anahtar"]) if anahtar else 0

    def kutu_ciz(cc):
        cc.kutu(bx0, y, bx1, y + 128, r=64, dolgu=T["kart"], cizgi=T["cizgi"], w=3)
        cc.elips(bx0 + 24, y + 24, bx0 + 104, y + 104, dolgu=karis(T["vurgu"], T["kart"], 0.55))
        if n:
            cc.yazi((bx0 + 134, y + 84), anahtar[:n], font("sans", 58, 700), T["murekkep"])
            if n >= len(anahtar):
                cc.elips(bx1 - 108, y + 20, bx1 - 20, y + 108, dolgu=T["vurgu"])
                cc.cokgen([(bx1 - 82, y + 42), (bx1 - 40, y + 64), (bx1 - 82, y + 86), (bx1 - 72, y + 64)], dolgu=(255, 255, 255))
        else:
            cc.yazi((bx0 + 134, y + 82), k.get("yer_tutucu", "Yorum ekle…"), font("sans", 48, 500), T["soluk"])
    katman(c, (bx0 - 4, y - 4, bx1 + 4, y + 132), kutu_ciz, ua, dy=14)


def soru_olay(k):
    anahtar = k.get("anahtar", "")
    if not anahtar:
        return []
    at = k.get("anahtar_t", k["_t"] + 0.7)
    _, z = yazma(anahtar, at, CPS["anahtar"])
    return [(x, "tus") for x in z][:len(anahtar)] + [(at + len(anahtar) / CPS["anahtar"] + 0.05, "pop")]


CIZ = {"baslik": baslik, "liste": liste, "sohbet": sohbet, "terminal": terminal, "agac": agac, "dosya": dosya,
       "sayi": sayi, "gorsel": gorsel, "soru": soru}
OLAY = {"liste": liste_olay, "sohbet": sohbet_olay, "terminal": terminal_olay, "agac": agac_olay,
        "dosya": dosya_olay, "sayi": sayi_olay, "gorsel": gorsel_olay, "soru": soru_olay}


def olaylar(k) -> list[tuple[float, str]]:
    fn = OLAY.get(k.get("tur"))
    return fn(k) if fn else []
