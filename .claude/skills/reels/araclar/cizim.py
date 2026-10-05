"""Reels çizim temeli: tuval ölçüleri, düzen sabitleri, tema renkleri, yazı tipleri, kaydırmalı çizim.

Yalnız repo kökündeki `fontlar/` klasörünün OFL yazı tipleri kullanılır (Inter, Newsreader,
IBM Plex Mono). İşletim sisteminin fontlarına hiç başvurulmaz: her makinede aynı görüntü.

Düzen (1080x1920, 30 fps) ve Instagram/TikTok arayüzünün kapattığı yerler:

    y 0-220      üst bant: "Reels" başlığı, kamera simgesi        -> yazı/kart girmez
    y 1536-1920  alt %20: kullanıcı adı, açıklama, müzik, menü    -> yazı/kart girmez
    x 940-1080   sağ sütun (y 1000-1536): beğen/yorum/paylaş      -> yazı girmez

    bol     üst 0-960 kart alanı, y ~1008 altyazı (dikiş), y 1070'ten başlayan yuvarlak yüz kartı (kenarlardan
            24 px içeride; boyu kaynağa göre: yüz alt %20'nin üstünde kalacak kadar)
    yuz     tam ekran yüz, altyazı y ~1290 (beyaz, koyu kontur)
    grafik  tam ekran kart, yüz yok, altyazı y ~1330
"""
from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

KOK = pathlib.Path(__file__).resolve().parents[4]          # repo kökü
FONTLAR = KOK / "fontlar"

W, H, FPS = 1080, 1920, 30

# --- güvenli alan (platform arayüzü) -------------------------------------------------------
UST_BANT = 220
ALT_BANT = 1536            # 1920 * 0.80
SAG_SUTUN_X = 940
SAG_SUTUN_Y = (1000, ALT_BANT)
KENAR = 40

# --- düzen ---------------------------------------------------------------------------------
KART_ALANI = {             # kartın çizilebileceği dikdörtgen (x0, y0, x1, y1)
    "bol": (60, 230, 1020, 940),
    "grafik": (70, 250, 940, 1240),      # alt kısmı sağ sütuna denk gelir: sağ kenar 940
}
ZEMIN_ALT = {"bol": 960, "grafik": H}     # zemin renginin kapladığı yükseklik
YUZ_KARTI_UST = 1070       # bol düzende yüz kartının üst kenarı
YUZ_KARTI_X = 24           # yüz kartının yan payı
YUZ_KARTI_ALT_EN_COK = 1896
YUZ_KARTI_R = 44
ALTYAZI_Y = {"bol": 1008, "grafik": 1330, "yuz": 1290}
ALTYAZI_GEN = 760          # altyazı satırının en geniş hali (sağ sütuna girmesin)

# --- tema ----------------------------------------------------------------------------------
TEMALAR = {
    "acik": {"zemin": "#EEE8DE", "kart": "#FFFFFF", "murekkep": "#18181B", "soluk": "#7D7870",
             "cizgi": "#DDD5C8", "vurgu": "#1E6FD9", "vurgu_acik": "#7CC8F8", "terminal": "#18181B",
             "terminal_yazi": "#ECE7DF", "yesil": "#2F9E5B", "kirmizi": "#C8402F", "balon_sen": "#ECE8E1",
             "balon_ai": "#E6F0FB"},
    "koyu": {"zemin": "#111113", "kart": "#1C1C1F", "murekkep": "#ECE7DF", "soluk": "#8B8883",
             "cizgi": "#2E2E33", "vurgu": "#38BDF8", "vurgu_acik": "#7DD3FC", "terminal": "#0B0B0D",
             "terminal_yazi": "#ECE7DF", "yesil": "#4ADE80", "kirmizi": "#F87171", "balon_sen": "#2A2A2E",
             "balon_ai": "#15283A"},
}


def renk(s) -> tuple:
    if isinstance(s, (list, tuple)):
        return tuple(int(v) for v in s[:3])
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def tema_kur(spec) -> dict:
    """senaryo `tema`: "acik" | "koyu" | {"ad": "acik", "vurgu": "#..."}. Renkler (r, g, b) döner."""
    if isinstance(spec, str) or spec is None:
        spec = {"ad": spec or "acik"}
    ad = spec.get("ad", "acik")
    if ad not in TEMALAR:
        raise SystemExit(f"tema '{ad}' yok; seçenekler: {', '.join(TEMALAR)}")
    t = {k: renk(v) for k, v in TEMALAR[ad].items()}
    for k, v in spec.items():
        if k != "ad":
            t[k] = renk(v)
    t["ad"] = ad
    t["koyu"] = ad == "koyu"
    return t


# --- yazı tipleri --------------------------------------------------------------------------
# aile -> (dosya, değişken eksen ayarı). Inter ve Newsreader değişken fonttur: ağırlık eksenle verilir.
AILE = {
    "sans": "Inter.ttf",
    "serif": "Newsreader.ttf",
    "serif_i": "Newsreader-Italic.ttf",
    "mono": "IBMPlexMono-Medium.ttf",
    "mono_kalin": "IBMPlexMono-SemiBold.ttf",
    "mono_ince": "IBMPlexMono-Regular.ttf",
}
_F: dict = {}


def font(aile: str, boy: float, agirlik: int = 400) -> ImageFont.FreeTypeFont:
    """aile: sans | serif | serif_i | mono | mono_kalin | mono_ince. agirlik yalnız değişken fontlarda."""
    k = (aile, int(boy), agirlik)
    if k in _F:
        return _F[k]
    yol = FONTLAR / AILE[aile]
    if not yol.exists():
        raise SystemExit(f"yazı tipi yok: {yol} (repo kökündeki fontlar/ klasörü)")
    f = ImageFont.truetype(str(yol), int(boy))
    try:
        eksenler = f.get_variation_axes()
    except OSError:
        eksenler = []
    if eksenler:
        degerler = []
        for e in eksenler:
            ad = e["name"].decode() if isinstance(e["name"], bytes) else str(e["name"])
            ad = ad.lower()
            if ad.startswith("weight"):
                degerler.append(max(e["minimum"], min(e["maximum"], agirlik)))
            elif ad.startswith("optical"):
                # büyük yazıda "display" kesimi: daha sıkı, daha zarif
                degerler.append(max(e["minimum"], min(e["maximum"], boy * 0.6)))
            else:
                degerler.append(e["default"])
        f.set_variation_by_axes(degerler)
    _F[k] = f
    return f


# --- zaman yardımcıları --------------------------------------------------------------------
def q(t: float, t0: float | None, sure: float) -> float:
    """t0'dan başlayan `sure`lik geçişin ilerlemesi 0..1 (t0 None ise 0)."""
    if t0 is None or t < t0:
        return 0.0
    return min(1.0, (t - t0) / max(sure, 1e-6))


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def karis(a, b, u: float) -> tuple:
    return tuple(int(round(a[i] + (b[i] - a[i]) * u)) for i in range(3))


# --- kaydırmalı çizim -----------------------------------------------------------------------
class Cizim:
    """Mutlak tuval koordinatıyla çizer; görüntü tuvalin bir parçasıysa (ox, oy) kaydırması uygulanır.
    Böylece kart fonksiyonları her zaman 1080x1920 koordinatında düşünür."""

    def __init__(self, img: Image.Image, ox: float = 0, oy: float = 0):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.ox, self.oy = ox, oy

    def _x(self, x):
        return x - self.ox

    def _y(self, y):
        return y - self.oy

    def kutu(self, x0, y0, x1, y1, r=0, dolgu=None, cizgi=None, w=2):
        b = [self._x(x0), self._y(y0), self._x(x1), self._y(y1)]
        if r:
            self.d.rounded_rectangle(b, radius=r, fill=dolgu, outline=cizgi, width=w if cizgi else 0)
        else:
            self.d.rectangle(b, fill=dolgu, outline=cizgi, width=w if cizgi else 0)

    def yazi(self, xy, s, f, renk_, anchor="ls", **kw):
        self.d.text((self._x(xy[0]), self._y(xy[1])), s, font=f, fill=renk_, anchor=anchor, **kw)

    def cizgi(self, noktalar, renk_, w=2, joint="curve"):
        self.d.line([(self._x(x), self._y(y)) for x, y in noktalar], fill=renk_, width=int(w), joint=joint)

    def elips(self, x0, y0, x1, y1, dolgu=None, cizgi=None, w=2):
        self.d.ellipse([self._x(x0), self._y(y0), self._x(x1), self._y(y1)], fill=dolgu, outline=cizgi,
                       width=w if cizgi else 0)

    def cokgen(self, noktalar, dolgu=None, cizgi=None):
        self.d.polygon([(self._x(x), self._y(y)) for x, y in noktalar], fill=dolgu, outline=cizgi)

    def yapistir(self, im: Image.Image, x, y, maske=None):
        x, y = int(round(self._x(x))), int(round(self._y(y)))
        if im.mode == "RGBA" and self.img.mode == "RGBA" and maske is None:
            self.img.alpha_composite(im, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
        else:
            self.img.paste(im, (x, y), maske)

    def uzunluk(self, s, f) -> float:
        return self.d.textlength(s, font=f)


def katman(c: Cizim, kutu, fn, u: float, dy: float = 14.0) -> None:
    """Bir öğeyi (kutu = mutlak x0, y0, x1, y1) u ile kayarak + belirerek çizer. u>=1 ise doğrudan çizer.
    Öğe küçük bir tuvale çizilir; tam ekran katman açılmaz (kare başına maliyet düşük kalır)."""
    if u <= 0:
        return
    if u >= 1:
        fn(c)
        return
    x0, y0, x1, y1 = (int(math.floor(kutu[0])) - 4, int(math.floor(kutu[1])) - 4,
                      int(math.ceil(kutu[2])) + 4, int(math.ceil(kutu[3])) + 4)
    gec = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
    fn(Cizim(gec, x0, y0))
    a = gec.getchannel("A").point(lambda v, u=ease(u): int(v * u))
    gec.putalpha(a)
    c.yapistir(gec, x0, y0 + dy * (1 - ease(u)))


_GOLGE: dict = {}


def golge(c: Cizim, x0, y0, x1, y1, r=28, guc=60, bul=18, dy=10) -> None:
    """Kartın altına yumuşak gölge (önbellekli). Hale/ışıma değil: aşağı kaymış, düşük opaklık."""
    w, h = int(x1 - x0), int(y1 - y0)
    k = (w, h, r, guc, bul)
    if k not in _GOLGE:
        p = bul * 3
        g = Image.new("L", (w + 2 * p, h + 2 * p), 0)
        ImageDraw.Draw(g).rounded_rectangle([p, p, p + w, p + h], radius=r, fill=guc)
        g = g.filter(ImageFilter.GaussianBlur(bul))
        im = Image.new("RGBA", g.size, (0, 0, 0, 0))
        im.putalpha(g)
        _GOLGE[k] = (im, p)
    im, p = _GOLGE[k]
    c.yapistir(im, x0 - p, y0 - p + dy)


def tik(c: Cizim, x, y, renk_, s=1.0, w=None) -> None:
    """Onay işareti çizgiyle (font glifine güvenilmez)."""
    c.cizgi([(x, y), (x + 10 * s, y + 11 * s), (x + 28 * s, y - 13 * s)], renk_, w or max(3, int(5 * s)))


def carpi(c: Cizim, x, y, renk_, s=1.0) -> None:
    a = 11 * s
    w = max(3, int(5 * s))
    c.cizgi([(x - a, y - a), (x + a, y + a)], renk_, w)
    c.cizgi([(x - a, y + a), (x + a, y - a)], renk_, w)


def sar(c: Cizim, yazi: str, f, gen: float) -> list[str]:
    """Kelime kelime satıra sarar."""
    satir, out = "", []
    for w in yazi.split():
        dene = (satir + " " + w).strip()
        if c.uzunluk(dene, f) > gen and satir:
            out.append(satir)
            satir = w
        else:
            satir = dene
    return out + ([satir] if satir else [])


def vurgulu_parcalar(s: str) -> list[tuple[str, bool]]:
    """'İşini kolaylaştıran *üç* şey' -> [('İşini kolaylaştıran ', False), ('üç', True), (' şey', False)]."""
    out, vurgu, buf = [], False, ""
    for ch in s:
        if ch == "*":
            if buf:
                out.append((buf, vurgu))
            buf, vurgu = "", not vurgu
        else:
            buf += ch
    if buf:
        out.append((buf, vurgu))
    return out
