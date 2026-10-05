"""'Bir haftadır sosyal medyadayım' — mürekkep çizgili 7 günlük zaman atlaması (4:5, X/Instagram akışı).

Görsel dil: kâğıt zemin, siyah mürekkep, çizgiler 10 fps'te "kaynar" (her 3 karede bir hafif
titreşim). Tek renk vurgu: bildirim kırmızısı. Çizim motoru: `.claude/skills/animasyon/kit/murekkep.py`.

  Gün 1-7 (her biri 2,1 sn)  karakter masada telefon kaydırıyor; her gün: daha çok gönderi,
                             daha çok bildirim, kahve bardağı birikir, saç dağılır, göz altı
                             çöker, bitki solar, karakter ekrana eğilir. Gece-gündüz pencerede.
  Gün 5-7                    gönderiler yere yağıp yığılıyor, 7. günün sonunda karakteri gömüyor
  Gün 8 (bitiş)              yığından bir el çıkıyor, kaydırmaya devam; "Bugün az kullanacağım."

Zamanlama tek yerde (`program()`); ses de aynı programdan üretilir (ses.py), senkron kaymaz.
PIL ile 2x çizilip küçültülür (yumuşak kenar). Deterministik: aynı kare hep aynı.

    python3 ornekler/animasyon-bir-hafta/anim.py                  # ses + görüntü -> calisma/animasyon/bir-hafta.mp4
    python3 ornekler/animasyon-bir-hafta/anim.py --kare 2,7.5,15.5   # önizleme kareleri (PNG)
    python3 ornekler/animasyon-bir-hafta/anim.py --sessiz         # yalnız görüntü
"""
from __future__ import annotations

import argparse
import math
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent
KOK = HERE.parents[1]
sys.path.insert(0, str(KOK / ".claude" / "skills" / "animasyon" / "kit"))
import murekkep as M  # noqa: E402

FONT = KOK / "fontlar" / "Caveat.ttf"          # el yazısı, Türkçe harfler tam (OFL)
CIKTI = KOK / "calisma" / "animasyon"
W, H, FPS, S = 1080, 1350, 30, 2
GUN = 2.1
GUN_SAYI = 7
BITIS = GUN * GUN_SAYI            # 14.7
SURE = BITIS + 3.0                # 17.7
KAGIT = (236, 229, 216)
MUREKKEP = (24, 22, 20)
KIRMIZI = (214, 52, 42)
GRI = (120, 114, 106)
ZEMIN_Y = 960

ALTYAZI = ["Sadece takip edeyim dedim.", "Birkaç hesap daha…", "Bildirimleri açtım.",
           "Şu thread'i bitirip yatacağım.", "Uyku? Yeni model çıktı.", "Hepsini okumam lazım.", "…",
           "Bugün az kullanacağım."]
BALONLAR = ["SON DAKİKA", "Yeni model çıktı!", "Bu her şeyi değiştirecek", "Yeni sürüm sızdı",
            "Büyük güncelleme geldi", "Bu hesap kimin?", "Thread 1/47", "Bunu kaçırma",
            "Yazılımcıların işi bitti", "+99 yeni gönderi", "Herkes bunu konuşuyor", "Az önce: yeni model"]


_FONTLAR: dict[int, object] = {}


def font(boy):
    if boy not in _FONTLAR:
        _FONTLAR[boy] = M.font(FONT, boy, S)
    return _FONTLAR[boy]


# ---------------------------------------------------------------- zaman programı
def program():
    """Uçan gönderiler, bildirim balonları, yığın kartları — hepsi deterministik."""
    rng = np.random.default_rng(11)
    oran = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 18.0]          # gönderi / sn
    balon_say = [1, 1, 2, 3, 4, 6, 9]
    kartlar, balonlar = [], []
    sira = list(rng.permutation(len(BALONLAR))) * 4          # ard arda ayni balon cikmasin
    for g in range(GUN_SAYI):
        t = g * GUN + 0.15
        while t < (g + 1) * GUN:
            kartlar.append({"t": t, "vx": rng.uniform(-40, 230), "vy": -(240 + 70 * g) * rng.uniform(0.85, 1.15),
                            "rot": rng.uniform(-25, 25), "drot": rng.uniform(-40, 40), "seed": int(rng.integers(1e6))})
            t += rng.exponential(1 / oran[g])
        for k in range(balon_say[g]):
            tb = g * GUN + 0.25 + (k + rng.uniform(0.1, 0.9)) * (GUN - 0.5) / balon_say[g]
            bolge = rng.integers(3)
            x, y = [(rng.uniform(40, 250), rng.uniform(330, 560)), (rng.uniform(220, 560), rng.uniform(300, 420)),
                    (rng.uniform(560, 760), rng.uniform(560, 700))][bolge]
            balonlar.append({"t": tb, "x": x, "y": y, "yazi": BALONLAR[int(sira.pop(0))],
                             "omur": max(0.7, 1.4 - 0.1 * g)})
    # yığın: gün 5 ortasından 7. günün sonuna, sonlara doğru hızlanan
    yigin = []
    N = 240
    for i in range(N):
        u = (i + 0.5) / N
        t = 4.5 * GUN + (BITIS - 0.1 - 4.5 * GUN) * u ** 0.6
        cx, w = 400, 360
        x = cx + w * rng.uniform(-1, 1) * math.sqrt(rng.uniform(0.2, 1))
        tepe = ZEMIN_Y - 520 * u * max(0.0, 1 - ((x - cx) / (w * 1.05)) ** 2) - 10
        y = rng.uniform(tepe, ZEMIN_Y - 10 * (1 - u)) if u < 0.97 else tepe
        yigin.append({"t": t, "x": x, "y": min(y, ZEMIN_Y - 18), "rot": rng.uniform(-40, 40), "seed": int(rng.integers(1e6))})
    # son kat: basin oldugu bolge (x 330-520, y 450-640) — rastgele yigin araliklarindan kafa gorunuyordu
    for i in range(34):
        yigin.append({"t": BITIS - 0.9 + 0.8 * i / 34, "x": rng.uniform(330, 520), "y": rng.uniform(450, 650),
                      "rot": rng.uniform(-40, 40), "seed": int(rng.integers(1e6))})
    return kartlar, balonlar, yigin


KARTLAR, BALONLAR_P, YIGIN = program()


# ---------------------------------------------------------------- mürekkep yardımcıları
# Sahne kendi koordinatlarinda (0-1010 x 200-960) cizilir, tuvale bu donusumle oturur.
# Ilk surumde sahne tuvalin ust %70'inde kaliyordu (4:5'te alt 390 px bostu).
SC, OX, OY = 1.1, -40.0, 99.0
Kalem = M.Kalem
dondur = M.dondur


def kalem(d: ImageDraw.ImageDraw, kare: int) -> M.Kalem:
    return M.Kalem(d, kare, s=S, sc=SC, ox=OX, oy=OY)


def kart(k: Kalem, cx, cy, rot, olcek=1.0, seed=0):
    w, h = 108 * olcek, 70 * olcek
    kose = dondur([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)], cx, cy, rot)
    k.poligon(kose, w=2.6 * olcek)
    a = dondur([(cx - w / 2 + 16 * olcek, cy - h / 2 + 16 * olcek)], cx, cy, rot)[0]
    k.daire(a[0], a[1], 7 * olcek, w=2.2 * olcek)
    rnd = (seed % 97) / 97
    for i, uz in enumerate((0.55 + 0.3 * rnd, 0.75, 0.45 + 0.4 * (1 - rnd))):
        y0 = cy - h / 2 + (16 + 16 * i) * olcek + (0 if i else 0)
        x0 = cx - w / 2 + (30 if i == 0 else 12) * olcek
        k.cizgi(dondur([(x0, y0), (x0 + (w - 44 * olcek) * uz, y0)], cx, cy, rot), w=2.2 * olcek, renk=GRI, amp=0.6)


# ---------------------------------------------------------------- sahne parçaları
def pencere(k: Kalem, t):
    x0, y0, x1, y1 = 610, 210, 950, 500
    g = min(int(t // GUN), GUN_SAYI - 1)
    p = (t % GUN) / GUN if t < BITIS else 0.3
    gece = 0.0 if p < 0.45 else min(1.0, (p - 0.45) / 0.15) if p < 0.9 else max(0.0, 1 - (p - 0.9) / 0.1)
    ic = tuple(int(KAGIT[i] * (1 - gece) + 58 * gece) for i in range(3))
    k.poligon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], w=4, dolgu=ic)
    if gece < 0.5:     # güneş yayı
        a = math.pi * (p / 0.5)
        sx, sy = x0 + 40 + (x1 - x0 - 80) * (p / 0.5), y1 - 40 - 170 * math.sin(a)
        k.daire(sx, sy, 26, w=3)
        for i in range(8):
            aa = i * math.pi / 4 + k.k * 0.08
            k.cizgi([(sx + 36 * math.cos(aa), sy + 36 * math.sin(aa)), (sx + 48 * math.cos(aa), sy + 48 * math.sin(aa))], w=2.5)
    else:              # ay + yıldız
        mx, my = x1 - 90, y0 + 80
        k.dolu(mx, my, 26, KAGIT)
        k.dolu(mx + 12, my - 8, 26, ic)
        for sx, sy in ((x0 + 60, y0 + 60), (x0 + 150, y0 + 110), (x0 + 110, y0 + 200), (x0 + 220, y0 + 50)):
            k.cizgi([(sx - 5, sy), (sx + 5, sy)], w=2, renk=KAGIT)
            k.cizgi([(sx, sy - 5), (sx, sy + 5)], w=2, renk=KAGIT)
    k.cizgi([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], w=3.5)
    k.cizgi([(x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2)], w=3.5)


def saat(k: Kalem, t):
    cx, cy, r = 520, 330, 46
    k.daire(cx, cy, r, w=4)
    a1 = t / GUN * 2 * math.pi * 2
    a2 = t / GUN * 2 * math.pi * 24
    k.cizgi([(cx, cy), (cx + 24 * math.sin(a1), cy - 24 * math.cos(a1))], w=4)
    k.cizgi([(cx, cy), (cx + 36 * math.sin(a2), cy - 36 * math.cos(a2))], w=2.5)


def masa(k: Kalem, g_f):
    k.cizgi([(440, 760), (1010, 760)], w=5)
    k.cizgi([(440, 774), (1010, 774)], w=3)
    k.cizgi([(470, 774), (470, ZEMIN_Y)], w=4)
    k.cizgi([(980, 774), (980, ZEMIN_Y)], w=4)
    # kahve bardakları: her gün bir tane
    n = min(int(g_f), 6)
    for i in range(n):
        x = 700 + i * 42 - (i % 2) * 6
        k.poligon([(x, 724), (x + 28, 724), (x + 24, 758), (x + 4, 758)], w=3)
        k.cizgi([(x + 28, 732), (x + 36, 736), (x + 34, 748), (x + 26, 750)], w=2.5)
        if i == n - 1:
            for j in range(2):
                ox = x + 8 + j * 10
                k.cizgi([(ox, 718), (ox - 5, 706), (ox + 3, 694), (ox - 3, 682)], w=2, renk=GRI)
    # bitki: günler geçtikçe solar
    solma = min(1.0, max(0.0, (g_f - 1) / 5.5))
    px = 920
    k.poligon([(px - 24, 716), (px + 24, 716), (px + 18, 758), (px - 18, 758)], w=3)
    tip = (px + 70 * solma, 640 + 60 * solma)
    orta = (px + 10 * solma, 670)
    k.cizgi([(px, 716), orta, tip], w=3)
    for i, (u, s) in enumerate(((0.45, -1), (0.7, 1), (0.95, -1))):
        bx = px + (orta[0] - px) * u * 2 if u < 0.5 else orta[0] + (tip[0] - orta[0]) * (u - 0.5) * 2
        by = 716 + (orta[1] - 716) * u * 2 if u < 0.5 else orta[1] + (tip[1] - orta[1]) * (u - 0.5) * 2
        sark = 22 * solma
        k.cizgi([(bx, by), (bx + s * 26, by - 14 + sark), (bx + s * 34, by + sark)], w=2.5)


def sandalye(k: Kalem):
    k.cizgi([(250, 800), (400, 800)], w=5)
    k.cizgi([(262, 800), (250, 610)], w=5)
    k.cizgi([(270, 800), (270, ZEMIN_Y)], w=4)
    k.cizgi([(385, 800), (385, ZEMIN_Y)], w=4)


def karakter(k: Kalem, t, g_f, telefon_cizgi=True):
    lean = min(1.0, max(0.0, (g_f - 0.5) / 6)) ** 1.2
    titre = 0.0 if g_f < 5 else 2.0 * (g_f - 5) * math.sin(t * 47)
    hip = (330, 786)
    a = math.radians(-4 + 28 * lean)                   # öne eğilme (saat yönü)
    boyun = (hip[0] + 175 * math.sin(a), hip[1] - 175 * math.cos(a))
    bas = (boyun[0] + 44 * math.sin(a + 0.15 * lean) + titre, boyun[1] - 44 * math.cos(a + 0.15 * lean))
    # bacaklar
    diz = (hip[0] + 118, hip[1] + 2)
    k.cizgi([hip, diz, (diz[0] + 14, ZEMIN_Y - 4), (diz[0] + 40, ZEMIN_Y - 4)], w=5)
    k.cizgi([hip, (diz[0] - 8, diz[1] + 8), (diz[0] - 2, ZEMIN_Y - 2), (diz[0] + 22, ZEMIN_Y - 2)], w=4.5)
    k.cizgi([hip, boyun], w=5.5)
    # telefon: yüze yaklaşıyor
    tel = (bas[0] + 92 - 38 * lean, bas[1] + 58 - 22 * lean)
    omuz = (hip[0] + 150 * math.sin(a), hip[1] - 150 * math.cos(a))
    dirsek = (omuz[0] + 30, omuz[1] + 78)
    k.cizgi([omuz, dirsek, (tel[0] - 6, tel[1] + 18)], w=4.5)
    k.cizgi([omuz, (dirsek[0] + 14, dirsek[1] + 4), (tel[0] + 4, tel[1] + 22)], w=4.5)
    tw, th = 34, 60
    kose = dondur([(tel[0] - tw / 2, tel[1] - th / 2), (tel[0] + tw / 2, tel[1] - th / 2),
                   (tel[0] + tw / 2, tel[1] + th / 2), (tel[0] - tw / 2, tel[1] + th / 2)], tel[0], tel[1], -18)
    k.poligon(kose, w=3.5)
    if telefon_cizgi:
        hiz = [1, 1.5, 2.2, 3, 4.5, 6, 8][min(int(g_f), 6)]
        for i in range(3):
            yy = ((t * 40 * hiz + i * 18) % 50) - 25
            k.cizgi(dondur([(tel[0] - 10, tel[1] + yy), (tel[0] + 10, tel[1] + yy)], tel[0], tel[1], -18), w=2, renk=GRI, amp=0.3)
    # baş
    k.daire(bas[0], bas[1], 38, w=5, dolgu=KAGIT)
    yon = 1
    goz = (bas[0] + 14 * yon, bas[1] - 4)
    buyuk = 3.5 + 3.0 * min(1, max(0, (g_f - 3) / 3))
    k.dolu(goz[0], goz[1], buyuk)
    if g_f >= 3.5:     # göz altı torbaları
        for i in range(1 + int(g_f >= 5.5)):
            yy = goz[1] + 9 + i * 6
            k.cizgi([(goz[0] - 9, yy), (goz[0], yy + 4), (goz[0] + 9, yy)], w=2, renk=GRI, amp=0.4)
    m = (bas[0] + 18, bas[1] + 16)
    if g_f < 2:
        k.cizgi([(m[0] - 8, m[1] - 2), (m[0], m[1] + 4), (m[0] + 8, m[1] - 2)], w=2.5)
    elif g_f < 4:
        k.cizgi([(m[0] - 7, m[1] + 2), (m[0] + 7, m[1] + 2)], w=2.5)
    else:
        k.cizgi([(m[0] - 8, m[1] + 2), (m[0] - 3, m[1] - 1), (m[0] + 2, m[1] + 3), (m[0] + 8, m[1])], w=2.5)
    # saç: 1. gün düzgün, sonra dağılır
    dag = min(1.0, max(0.0, (g_f - 2) / 4))
    # duzgun sac: basin ustunde kalin bir kep (1-2. gun yalnizca bu)
    kep = [(bas[0] + 40 * math.cos(aa), bas[1] + 40 * math.sin(aa)) for aa in np.linspace(-2.9, -0.25, 9)]
    k.cizgi(kep, w=9)
    for i in range(int(14 * dag)):
        aa = -2.4 + 1.9 * i / (5 + 8 * dag) + dag * 0.35 * math.sin(i * 7.1 + k.k * 0.9)
        r0, r1 = 38, 44 + 26 * dag * (0.6 + 0.4 * math.sin(i * 3.3))
        k.cizgi([(bas[0] + r0 * math.cos(aa), bas[1] + r0 * math.sin(aa)),
                 (bas[0] + r1 * math.cos(aa + 0.15 * dag), bas[1] + r1 * math.sin(aa + 0.15 * dag))], w=3)
    if g_f >= 5.2:     # ter damlası
        dx, dy = bas[0] - 34, bas[1] - 20 + (t * 30 % 20)
        k.poligon([(dx, dy - 10), (dx + 6, dy + 2), (dx, dy + 8), (dx - 6, dy + 2)], w=2)
    return tel


def balon(k: Kalem, b, t):
    yas = t - b["t"]
    if yas < 0 or yas > b["omur"]:
        return
    gir = min(1, yas / 0.12)
    cik = 1 - max(0, (yas - b["omur"] + 0.15) / 0.15)
    if cik <= 0:
        return
    f = font(round(34 * SC))
    tw = k.d.textlength(b["yazi"], font=f) / S / SC
    x, y = b["x"], b["y"] - 10 * (1 - gir)
    w, h = tw + 44, 50
    k.poligon([(x, y), (x + w, y), (x + w, y + h), (x + 36, y + h), (x + 22, y + h + 14), (x + 24, y + h), (x, y + h)], w=3)
    k.dolu(x + 14, y + 23, 6, KIRMIZI)
    k.yazi(x + 28, y + 6, b["yazi"], f)


def kare(t: float, n: int) -> Image.Image:
    img, d = TUVAL.yeni()
    k = kalem(d, n)
    g_f = min(t / GUN, GUN_SAYI - 0.001) + (0 if t < BITIS else 1)     # 0..7 (+1 bitiş)
    gun = min(int(t // GUN) + 1, GUN_SAYI) if t < BITIS else 8
    # zemin
    k.cizgi([(0, ZEMIN_Y), (1080, ZEMIN_Y)], w=4)
    for i in range(12):
        x = 60 + i * 90
        k.cizgi([(x, ZEMIN_Y + 30 + (i % 3) * 18), (x + 40, ZEMIN_Y + 30 + (i % 3) * 18)], w=2, renk=GRI)
    pencere(k, t)
    saat(k, t)
    masa(k, min(g_f, 7))
    sandalye(k)
    tel = karakter(k, t, min(g_f, 6.99))
    # uçan gönderiler (bitişte dur)
    for c in KARTLAR:
        yas = t - c["t"]
        if yas < 0 or yas > 3.5 or t >= BITIS + 0.3:
            continue
        cx = tel[0] + c["vx"] * yas
        cy = tel[1] - 30 + c["vy"] * yas - 10 * yas
        # GUN sayaci ve altyazi tuvalin ust 300 px'inde: kartlar oraya varmadan kuculup sonuyor
        sonum = min(1.0, max(0.0, (cy - 200) / 120))
        if sonum <= 0.05:
            continue
        olcek = min(1.0, 0.3 + yas * 3) * sonum
        kart(k, cx, cy, c["rot"] + c["drot"] * yas, olcek, c["seed"])
    # yığın
    for c in YIGIN:
        yas = t - c["t"]
        if yas < 0:
            continue
        dus = min(1, yas / 0.28)
        cy = c["y"] - 260 * (1 - dus) ** 2
        kart(k, c["x"], cy, c["rot"] * dus, 1.0, c["seed"])
    # bitiş: yığından el + telefon (espri bu, o yüzden büyük)
    if t >= BITIS:
        u = min(1, (t - BITIS - 0.35) / 0.5)
        if u > 0:
            ex, ey = 395, 470 - 95 * u
            k.cizgi([(ex - 8, 505), (ex - 4, ey + 44)], w=7)
            k.daire(ex - 2, ey + 34, 16, w=5, dolgu=KAGIT)
            tx, ty = ex + 4, ey - 26
            k.poligon([(tx - 26, ty - 46), (tx + 26, ty - 46), (tx + 26, ty + 46), (tx - 26, ty + 46)], w=4.5)
            for i in range(4):
                yy = ((t * 160 + i * 20) % 76) - 38
                k.cizgi([(tx - 15, ty + yy), (tx + 15, ty + yy)], w=2.5, renk=GRI, amp=0.3)
            bas_p = min(1, (t - BITIS - 0.35) / 0.25)
            k.cizgi([(ex + 10, ey + 28), (ex + 18, ey + 8 - 12 * abs(math.sin(t * 9)) * bas_p)], w=5)   # başparmak
            # kolun dibi yığının İÇİNDE kalsın: iki kart üstüne (kol önceden kartların üstünden iniyordu)
            kart(k, 372, 505, -14, 1.0, 11)
            kart(k, 432, 500, 17, 1.0, 29)
        if t >= BITIS + 1.2:
            balon(k, {"t": BITIS + 1.2, "x": 430, "y": 190, "yazi": "+1 yeni gönderi", "omur": 99}, t)
    # balonlar
    for b in BALONLAR_P:
        if t < BITIS:
            balon(k, b, t)
    # gün sayacı + altyazı
    gun_bas = (gun - 1) * GUN if gun <= 7 else BITIS
    zıpla = max(0, 1 - (t - gun_bas) / 0.25)
    k.yazi(64, 44 - 14 * zıpla, f"GÜN {gun}", font(118), sahne=False)
    alt = ALTYAZI[gun - 1]
    ga = min(1, (t - gun_bas - 0.1) / 0.3)
    if ga > 0:
        renk = tuple(int(KAGIT[i] + (MUREKKEP[i] - KAGIT[i]) * ga) for i in range(3))
        k.yazi(70, 186, alt, font(58), renk, sahne=False)
    return TUVAL.bitir(img)


TUVAL = M.Tuval(W, H, S, zemin=KAGIT, tohum=3)     # kâğıt dokusu + kenar kararması, bir kez üretilir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kare", type=str, help="virgüllü saniyeler: önizleme PNG")
    ap.add_argument("--sessiz", action="store_true", help="ses üretme, yalnız görüntü")
    ap.add_argument("--out", default=str(CIKTI / "bir-hafta.mp4"))
    a = ap.parse_args()
    if a.kare:
        (CIKTI / "kontrol").mkdir(parents=True, exist_ok=True)
        for s_ in a.kare.split(","):
            t = float(s_)
            yol = CIKTI / "kontrol" / f"kare-{t}.png"
            kare(t, int(t * FPS)).save(yol)
            print("kare:", yol)
        return
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    wav = None
    if not a.sessiz:
        sys.path.insert(0, str(HERE))
        import ses
        wav = ses.uret(sys.modules[__name__], pathlib.Path(a.out).with_suffix(".wav"))
        print("ses:", wav)
    M.yaz_mp4(kare, SURE, a.out, W, H, FPS, crf=17, ses=str(wav) if wav else None)
    if wav:
        pathlib.Path(wav).unlink()
    print("yazildi", a.out)


if __name__ == "__main__":
    main()
