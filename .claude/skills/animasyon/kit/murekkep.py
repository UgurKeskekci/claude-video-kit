"""Mürekkep-kâğıt çizim motoru + eklemli karakter iskeleti (PIL, 2x süper örnekleme).

Yayınlanmış bir animasyonda kanıtlanan parçaların genelleştirilmiş hâli; çalışan örnek
`ornekler/animasyon-bir-hafta/anim.py`. Yeni bir animasyon bu dosyayı import eder, sahneyi
kendisi kurar.

    import sys; sys.path.insert(0, ".claude/skills/animasyon/kit")
    from murekkep import Tuval, Kalem, Iskelet, poz_karistir, yuru, yaz_mp4

Kurallar (ölçülerek bulundu, bkz. references/tarifler.md):
- Çizgiler her 3 karede bir "kaynar" (10 fps titreşim) — el çizimi hissi. Titreşim NOKTAYA
  bağlı hash'tir; aynı kare hep aynı çıkar (deterministik render).
- Sahne kendi koordinatında çizilir, `Kalem(sc, ox, oy)` tuvale oturtur. Kompozisyonu
  sonradan büyütmek/kaydırmak tek satır.
- Yazı titremez (kaynatılmaz); metin kaynarsa okunmuyor.
"""
from __future__ import annotations

import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

KAGIT = (236, 229, 216)
MUREKKEP = (24, 22, 20)
GRI = (120, 114, 106)
KIRMIZI = (214, 52, 42)


class Tuval:
    def __init__(self, w=1080, h=1350, s=2, zemin=KAGIT, doku=True, tohum=3):
        self.w, self.h, self.s = w, h, s
        rng = np.random.default_rng(tohum)
        a = np.zeros((h * s, w * s, 3), np.float32) + np.array(zemin, np.float32)
        if doku:
            lif = rng.normal(0, 3.0, (h * s // 4, w * s // 4, 1)).repeat(4, 0).repeat(4, 1)
            a += lif + rng.normal(0, 1.5, a.shape)
            y, x = np.mgrid[0:h * s, 0:w * s].astype(np.float32)
            v = (x / (w * s) - 0.5) ** 2 + (y / (h * s) - 0.5) ** 2
            a *= (1 - 0.12 * v)[..., None]
        self.zemin = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def yeni(self):
        img = self.zemin.copy()
        return img, ImageDraw.Draw(img)

    def bitir(self, img):
        return img.resize((self.w, self.h), Image.LANCZOS)


class Kalem:
    def __init__(self, d: ImageDraw.ImageDraw, kare: int, s=2, sc=1.0, ox=0.0, oy=0.0, kaynama=3):
        self.d, self.s, self.sc, self.ox, self.oy = d, s, sc, ox, oy
        self.k = kare // kaynama

    def j(self, x, y, amp=1.3):
        h = math.sin(x * 12.9898 + y * 78.233 + self.k * 37.719) * 43758.5453
        h2 = math.sin(x * 39.346 + y * 11.135 + self.k * 91.113) * 23421.631
        return ((x * self.sc + self.ox + amp * (2 * (h % 1) - 1)) * self.s,
                (y * self.sc + self.oy + amp * (2 * (h2 % 1) - 1)) * self.s)

    def _w(self, w):
        return max(1, int(w * self.sc * self.s))

    def cizgi(self, pts, w=4.0, renk=MUREKKEP, amp=1.3):
        self.d.line([self.j(x, y, amp) for x, y in pts], fill=renk, width=self._w(w), joint="curve")

    def daire(self, cx, cy, r, w=4.0, dolgu=None, renk=MUREKKEP):
        x, y = self.j(cx, cy, 1.0)
        r = r * self.sc * self.s
        self.d.ellipse([x - r, y - r, x + r, y + r], outline=renk, width=self._w(w), fill=dolgu)

    def dolu(self, cx, cy, r, renk=MUREKKEP):
        x, y = self.j(cx, cy, 0.6)
        r = r * self.sc * self.s
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=renk)

    def poligon(self, pts, w=3.0, dolgu=KAGIT, renk=MUREKKEP, amp=1.0):
        p = [self.j(x, y, amp) for x, y in pts]
        self.d.polygon(p, fill=dolgu)
        self.d.line(p + [p[0]], fill=renk, width=self._w(w), joint="curve")

    def yazi(self, x, y, s, f, renk=MUREKKEP, anchor="la", sahne=True):
        """sahne=False: tuval koordinatı (sayaç, başlık — dönüşümden etkilenmez)."""
        if sahne:
            x, y = x * self.sc + self.ox, y * self.sc + self.oy
        self.d.text((x * self.s, y * self.s), s, font=f, fill=renk, anchor=anchor)


def font(yol, boy, s=2):
    return ImageFont.truetype(str(yol), int(boy * s))


def dondur(pts, cx, cy, a_derece):
    c, s = math.cos(math.radians(a_derece)), math.sin(math.radians(a_derece))
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


# ------------------------------------------------------------------ yumuşatma
def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def yay(x, sonum=6.5, frekans=7.5):
    """Hafif aşan giriş (Remotion spring benzeri)."""
    x = min(max(x, 0.0), 1.0)
    return 1 - math.exp(-sonum * x) * math.cos(frekans * x) if x < 1 else 1.0


# ------------------------------------------------------------------ iskelet
# Açılar DERECE, 0 = aşağı, pozitif = saat yönü (ekranda sağa/öne). Her uzuv iki parça:
# üst (uyluk/kol) açısı gövdeye değil DÜNYAYA göre, alt (baldır/ön kol) açısı üst parçaya göre.
VARSAYILAN_POZ = {
    "govde": 0.0,        # kalçadan boyuna; 0 dik, + öne eğik
    "bas": 0.0,          # boyuna göre
    "kol_on_ust": 10.0, "kol_on_alt": 20.0,      # dirsek İLERİ bükülür (+), diz GERİ (-)
    "kol_arka_ust": -10.0, "kol_arka_alt": 15.0,
    "bacak_on_ust": 0.0, "bacak_on_alt": 0.0,
    "bacak_arka_ust": 0.0, "bacak_arka_alt": 0.0,
    "kalca_y": 0.0,      # zıplama/sekme (piksel, - yukarı)
}


class Iskelet:
    def __init__(self, boy=1.0, govde=150, boyun=18, bas_r=30, ust_kol=62, alt_kol=58, uyluk=80, baldir=78):
        b = boy
        self.L = dict(govde=govde * b, boyun=boyun * b, bas_r=bas_r * b, ust_kol=ust_kol * b, alt_kol=alt_kol * b,
                      uyluk=uyluk * b, baldir=baldir * b)

    @staticmethod
    def _uc(p, uzunluk, aci):
        a = math.radians(aci)
        return (p[0] + uzunluk * math.sin(a), p[1] + uzunluk * math.cos(a))

    def noktalar(self, kalca, poz):
        P = dict(VARSAYILAN_POZ, **poz)
        L = self.L
        kx, ky = kalca[0], kalca[1] + P["kalca_y"]
        k = (kx, ky)
        omuz = self._uc(k, L["govde"], 180 - P["govde"])        # yukarı doğru
        boyun = self._uc(omuz, L["boyun"], 180 - P["govde"] - P["bas"] * 0.3)
        bas = self._uc(boyun, L["bas_r"], 180 - P["govde"] - P["bas"])
        out = {"kalca": k, "omuz": omuz, "boyun": boyun, "bas": bas}
        for taraf in ("on", "arka"):
            dirsek = self._uc(omuz, L["ust_kol"], P[f"kol_{taraf}_ust"])
            el = self._uc(dirsek, L["alt_kol"], P[f"kol_{taraf}_ust"] + P[f"kol_{taraf}_alt"])
            diz = self._uc(k, L["uyluk"], P[f"bacak_{taraf}_ust"])
            ayak = self._uc(diz, L["baldir"], P[f"bacak_{taraf}_ust"] + P[f"bacak_{taraf}_alt"])
            out.update({f"dirsek_{taraf}": dirsek, f"el_{taraf}": el, f"diz_{taraf}": diz, f"ayak_{taraf}": ayak})
        return out

    def ciz(self, kalem: Kalem, kalca, poz, w=5.0, dolgu=KAGIT, yuz=None):
        n = self.noktalar(kalca, poz)
        for taraf, kalin in (("arka", w * 0.85), ("on", w)):
            kalem.cizgi([n["kalca"], n[f"diz_{taraf}"], n[f"ayak_{taraf}"],
                         (n[f"ayak_{taraf}"][0] + 18 * self.L["bas_r"] / 30, n[f"ayak_{taraf}"][1])], w=kalin)
        kalem.cizgi([n["kalca"], n["omuz"], n["boyun"]], w=w * 1.1)
        kalem.cizgi([n["omuz"], n["dirsek_arka"], n["el_arka"]], w=w * 0.85)
        kalem.daire(n["bas"][0], n["bas"][1], self.L["bas_r"], w=w, dolgu=dolgu)
        kalem.cizgi([n["omuz"], n["dirsek_on"], n["el_on"]], w=w)
        if yuz:
            yuz(kalem, n)
        return n


def poz_karistir(a: dict, b: dict, u: float) -> dict:
    """İki poz arasında yumuşak geçiş (anahtar kare)."""
    u = ease_io(u)
    A, B = dict(VARSAYILAN_POZ, **a), dict(VARSAYILAN_POZ, **b)
    return {k: A[k] + (B[k] - A[k]) * u for k in A}


def yuru(faz: float, adim=28.0, diz=38.0, kol=24.0, sekme=3.0, bacak=158.0) -> dict:
    """Prosedürel yürüme döngüsü. faz: 0..1 bir tam adım çifti (sağ+sol).
    Uyluk sinüsle ileri-geri; diz yalnız bacak GERİDEYKEN büker (ayak yerden kalkar);
    kollar bacaklara ters.
    Kalça adım açıldıkça İNER: düz bacak açılınca dikey boyu bacak*cos(açı)'ya düşüyor,
    inmezse basan ayak havada kalıyordu (ölçüldü: 28°'de 19 px). `bacak` = uyluk+baldır."""
    p = 2 * math.pi * faz
    on = adim * math.sin(p)
    arka = -on
    inis = bacak * (1 - math.cos(math.radians(abs(on))))
    return {
        "govde": 4.0,
        "bacak_on_ust": on, "bacak_on_alt": -diz * max(0.0, math.sin(p - 1.2)),
        "bacak_arka_ust": arka, "bacak_arka_alt": -diz * max(0.0, math.sin(p + math.pi - 1.2)),
        "kol_on_ust": -kol * math.sin(p), "kol_on_alt": 18.0 + 10 * max(0.0, -math.sin(p)),
        "kol_arka_ust": kol * math.sin(p), "kol_arka_alt": 18.0 + 10 * max(0.0, math.sin(p)),
        "kalca_y": inis - sekme * abs(math.cos(p)),
    }


# ------------------------------------------------------------------ çıktı
def yaz_mp4(kare_fn, sure: float, yol: str, w: int, h: int, fps: int = 30, crf: int = 17, ses: str | None = None):
    """kare_fn(t, n) -> PIL.Image (w x h). Ham kareleri ffmpeg'e borular; ses verilirse ekler."""
    girdi = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if ses:
        girdi += ["-i", ses]
    cikis = ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    if ses:
        cikis += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", *girdi, *cikis, "-movflags", "+faststart", yol],
                           stdin=subprocess.PIPE)
    n = int(round(sure * fps))
    for i in range(n):
        enc.stdin.write(kare_fn(i / fps, i).tobytes())
        if i % (fps * 2) == 0:
            print(f"  {i}/{n}", flush=True)
    enc.stdin.close()
    if enc.wait():
        raise RuntimeError(f"ffmpeg hata verdi ({enc.returncode}): {yol}")
    return yol


# ------------------------------------------------------------------ ortak nesneler
_FONT_ONBELLEK = {}


def olcekli_font(k: Kalem, yol, boy):
    """DÜNYA içi yazı için: kamera ölçeğiyle büyür/küçülür (sabit boyda kalan yazılar kamera
    geri çekilince kenardan taşıyordu). Ekran yazısı (sayaç/başlık) için `font` kullan."""
    anahtar = (str(yol), max(4, round(boy * k.sc)))
    if anahtar not in _FONT_ONBELLEK:
        _FONT_ONBELLEK[anahtar] = font(yol, anahtar[1], k.s)
    return _FONT_ONBELLEK[anahtar]


def gonderi_karti(k: Kalem, cx, cy, rot=0.0, olcek=1.0, seed=0):
    """Sosyal medya gönderisi: avatar + 3 gri satır. Yığın, akış, bildirim yağmuru."""
    w, h = 108 * olcek, 70 * olcek
    kose = dondur([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)],
                  cx, cy, rot)
    k.poligon(kose, w=2.6 * olcek)
    a = dondur([(cx - w / 2 + 16 * olcek, cy - h / 2 + 16 * olcek)], cx, cy, rot)[0]
    k.daire(a[0], a[1], 7 * olcek, w=2.2 * olcek)
    for i in range(3):
        y0 = cy - h / 2 + (16 + 16 * i) * olcek
        x0 = cx - w / 2 + (30 if i == 0 else 12) * olcek
        uz = (50 + 10 * ((seed + i) % 3)) * olcek
        k.cizgi(dondur([(x0, y0), (x0 + uz, y0)], cx, cy, rot), w=2.2 * olcek, renk=GRI, amp=0.6)


def bildirim_balonu(k: Kalem, x, y, yazi, font_yolu, boy=32):
    """Kırmızı noktalı konuşma balonu (sahne koordinatı, sol üst köşe)."""
    f = olcekli_font(k, font_yolu, boy)
    tw = k.d.textlength(yazi, font=f) / k.s / k.sc
    k.poligon([(x, y), (x + tw + 44, y), (x + tw + 44, y + 50), (x + 36, y + 50), (x + 22, y + 64), (x + 24, y + 50),
               (x, y + 50)], w=3)
    k.dolu(x + 14, y + 25, 6, KIRMIZI)
    k.yazi(x + 28, y + 7, yazi, f)
