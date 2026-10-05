"""Kaba kurgunun kararları: ses zarfından konuşma parçaları, tekrarlar, kare ızgarası, denetim.

Bu dosya SAF Python'dur (numpy yok), testler düz `python3 tests/test_kesim.py` ile koşar.
Ağır işler (wav okuma, Whisper, ffmpeg) medya.py, cek.py ve senkron.py'de.

Temel ilke: kesimi SES verir. Whisper kelimeleri yalnızca "hangi bölge tutulacak" sorusuna
cevap verir; damgaları 0,1-0,5 sn erken olabilir. Kesim noktası her zaman sesin en kısık
karesine oturur. Buradaki sayıların her biri gerçek kayıtlarda ölçüldü
(references/kurallar.md).
"""
from __future__ import annotations

import difflib
import re

# --- zarf ----------------------------------------------------------------------------
KARE = 0.01               # zarfın bir karesi: 10 ms
ESIK_TABAN = 8.0          # eşik >= gürültü tabanı (p10) + 8 dB
ESIK_KONUSMA = 30.0       # eşik >= konuşma seviyesi (p90) - 30 dB

# --- parçalar ------------------------------------------------------------------------
BOSLUK_KAPAT = 12         # kare: 0,12 sn'den kısa sessizlik konuşmayı bölmez
ADA_EN_AZ = 6             # kare: 0,06 sn'den kısa sesli ada atılır (tık, nefes)
SESSIZ_ARA = 0.20         # atılan aralığın sınırı ±0,2 sn içindeki en sessiz kareye oturur
ORTUSME_PAY = 0.30        # kelime-bölge örtüşmesinde pay (Whisper başı 0,1-0,4 sn erken damgalar)
BOS_EN_AZ = 0.20          # kelimesiz bölge en az bu kadar sürerse ...
BOS_GUC = 12.0            # ... ve eşiğin 12 dB üstündeyse, iki komşusu tutuluyorsa tutulur
BAS_PAY = 0.06            # parça sesin başladığı yerden 0,06 sn önce başlar
SON_CUMLE = 0.28          # cümle sonunda sesin bitişinden sonra kalan
SON_ICI = 0.12            # cümle içinde kalan
BIRLESTIR = 0.05          # aradaki boşluk bundan kısaysa iki parça tek parça olur
EN_KISA = 0.10            # bundan kısa parça atılır

# --- blok sınırları ------------------------------------------------------------------
BAS_SABITLE = 0.25        # blok başı ±0,25 sn içindeki en sessiz kareye
UZAT_SESSIZ = 0.30        # blok sonu: sondan sonraki ilk >=0,3 sn sessizliğin başı ...
UZAT_PAY = 0.35           # ... + 0,35 sn (son kelime kesilmesin)
UZAT_EN_COK = 1.5

# --- tekrar --------------------------------------------------------------------------
TEKRAR_ARA = 1.5          # iki kopya arasında bundan az boşluk varsa gerçek tekrar
# Türkçede bilerek tekrarlanan kelimeler (ikileme, vurgu): tek kelimelik tekrarı atılmaz.
# "bir" BİLEREK yok: "bir, bir şey" takılması "birer birer"den çok daha sık.
TEKRAR_SERBEST = frozenset({
    "çok", "daha", "tek", "yavaş", "hızlı", "ayrı", "adım", "sık", "kat", "parça", "ara",
    "zaman", "uzun", "kısa", "güzel", "yeni", "ağır", "derin", "dolu", "ince", "sıra", "yer",
    "hemen", "güle", "evet", "hayır", "tamam", "teker", "tekrar",
})

# --- hızlandırma (ekran-hizli blokları) ----------------------------------------------
HIZ_KOSU = 0.5            # en az bu uzunlukta sessiz koşular ...
HIZ_BIRLESTIR = 0.4       # ... arası 0,4 sn'den kısa gürültüyle bölünmüşse birleşir
HIZ_EN_AZ = 2.4           # bundan uzun konuşmasız aralık hızlanır
HIZ_KENAR = 0.35          # aralığın iki kenarında normal hızda kalan
HIZ_4X = 6.0              # hızlanan kısım bundan uzunsa 4x, değilse 2x

# --- kamera yakınlaşması ---------------------------------------------------------------
ZOOM_ATLAMA = 2.0         # kaynakta 2 sn'den fazla atlanan kesimde yakınlaşma değişir

# --- çıktı ---------------------------------------------------------------------------
SR = 48000
FPS_GECERLI = (24, 25, 30, 48, 50, 60)   # 48000'i tam böler: her kare tam örnek sayısı
GORUNTU_TURLERI = ("kamera", "ekran", "ekran-hizli")
CUMLE_SONU = ".?!…"


# =====================================================================================
# Ses zarfı
# =====================================================================================

def yuzdelik(degerler, q: float) -> float:
    """numpy.percentile (doğrusal ara değer) ile aynı sonuç, numpy'sız."""
    s = sorted(degerler)
    if not s:
        return 0.0
    k = (len(s) - 1) * q / 100.0
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return float(s[f] + (s[c] - s[f]) * (k - f))


def kare(t: float) -> int:
    """Saniye -> zarf karesi (taban). 0.29*100 = 28.999... sorununa karşı küçük pay."""
    return int(t * 100 + 1e-6)


class Enerji:
    """10 ms'lik dB zarfı ve uyarlamalı eşik.

    Eşik = max(gürültü tabanı p10 + 8 dB, konuşma seviyesi p90 - 30 dB). Gürültü kapılı
    kayıtta (sessizlik -120 dB) ilki, gürültülü odada ikincisi belirleyici olur.
    `db` liste ya da numpy dizisi olabilir; wav'dan kurmak medya.zarf() ile.
    """

    def __init__(self, db, esik: float | None = None):
        self.db = [float(v) for v in db]
        if esik is None:
            p10, p90 = yuzdelik(self.db, 10), yuzdelik(self.db, 90)
            esik = max(p10 + ESIK_TABAN, p90 - ESIK_KONUSMA)
        self.esik = float(esik)

    @property
    def sure(self) -> float:
        return len(self.db) * KARE

    def kosular(self, a: float, b: float, en_az: float, esik: float | None = None) -> list[tuple[float, float]]:
        """[a, b] içindeki en az `en_az` sn süren SESSİZ koşular."""
        e = self.esik if esik is None else esik
        out, i, i1 = [], max(0, kare(a)), min(len(self.db), kare(b))
        while i < i1:
            if self.db[i] < e:
                j = i
                while j < i1 and self.db[j] < e:
                    j += 1
                if (j - i) * KARE >= en_az - 1e-9:
                    out.append((round(i * KARE, 2), round(j * KARE, 2)))
                i = j
            else:
                i += 1
        return out

    def konusma(self, a: float, b: float, en_az: float) -> list[tuple[float, float]]:
        """[a, b] içindeki en az `en_az` sn süren SESLİ koşular."""
        out, i, i1 = [], max(0, kare(a)), min(len(self.db), kare(b))
        while i < i1:
            if self.db[i] >= self.esik:
                j = i
                while j < i1 and self.db[j] >= self.esik:
                    j += 1
                if (j - i) * KARE >= en_az - 1e-9:
                    out.append((round(i * KARE, 2), round(j * KARE, 2)))
                i = j
            else:
                i += 1
        return out

    def sessiz_kare(self, t: float, pay: float = SESSIZ_ARA) -> float:
        """t ± pay içindeki en kısık kare (ilk en küçük). Kesim noktası buraya oturur."""
        lo, hi = max(0, kare(t - pay)), min(len(self.db), kare(t + pay))
        if hi <= lo:
            return t
        i = min(range(lo, hi), key=self.db.__getitem__)
        return round(i * KARE, 2)

    def ortalama(self, a: float, b: float) -> float:
        lo, hi = max(0, kare(a)), min(len(self.db), kare(b))
        if hi <= lo:
            return -120.0
        return sum(self.db[lo:hi]) / (hi - lo)

    def sesli_oran(self, a: float, b: float) -> float:
        """[a, b]'nin ne kadarı eşik üstü. Whisper'ın sessizlikte uydurduğu satırı ayıklamak için."""
        lo, hi = max(0, kare(a)), min(len(self.db), kare(b))
        if hi <= lo:
            return 0.0
        return sum(1 for v in self.db[lo:hi] if v >= self.esik) / (hi - lo)


# =====================================================================================
# Kelimeler: normalleştirme, sözlük, tekrar
# =====================================================================================

def norm(w: str) -> str:
    """Karşılaştırma anahtarı. Sayı içeren kelime boş döner: harfiyen döküm "5.5"i "5" + ".5"
    diye yazıyor, tekrar sanılıp "5" atılıyordu. Kesme işaretinden sonrası atılır."""
    if re.search(r"\d", w):
        return ""
    w = w.replace("İ", "i").replace("I", "ı").lower().replace("’", "'").split("'")[0]
    return re.sub(r"[^\wçğıöşüâîû]", "", w)


def benzer(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


_HARF = "0-9A-Za-zÇĞİIÖŞÜçğıöşüÂÎÛâîû"
NOKTALAMA = ".,!?;:…"


def _desen(src: str) -> re.Pattern:
    return re.compile(rf"(?<![{_HARF}])" + re.escape(src) + rf"(?![{_HARF}])")


def duzelt_kelimeler(ws: list[dict], duzeltmeler: list) -> list[dict]:
    """Sözlük düzeltmeleri. Tek kelimelik kalıp kelimenin içinde (sınırlara saygılı) değişir;
    çok kelimeli kalıp ("Cloud Code") eşleşen kelimeleri TEK kelimeye birleştirir, zaman
    aralığı korunur (baş ilk kelimenin, son son kelimenin)."""
    ciftler = [(s, d) for s, d in (c for c in duzeltmeler if isinstance(c, (list, tuple)) and len(c) == 2)]
    coklu = sorted([(s, d) for s, d in ciftler if " " in s.strip()], key=lambda x: -len(x[0].split()))
    tekli = [(_desen(s), d) for s, d in ciftler if " " not in s.strip()]

    def tek(token: str) -> str:
        bas = token[: len(token) - len(token.lstrip())]
        son = token[len(token.rstrip()):]
        govde = token.strip()
        for p, d in tekli:
            govde = p.sub(d, govde)
        return f"{bas}{govde}{son}"

    out, i = [], 0
    while i < len(ws):
        bulunan = None
        for src, dst in coklu:
            n = len(src.split())
            if i + n > len(ws):
                continue
            span = " ".join(w["word"].strip() for w in ws[i:i + n])
            if span.rstrip(NOKTALAMA).lower() == src.lower():
                bulunan = (n, dst + span[len(span.rstrip(NOKTALAMA)):])
                break
        if bulunan:
            n, metin = bulunan
            bas = " " if ws[i]["word"].startswith(" ") else ""
            out.append({**ws[i], "word": bas + metin, "end": ws[i + n - 1]["end"]})
            i += n
        else:
            out.append({**ws[i], "word": tek(ws[i]["word"])})
            i += 1
    return out


def tekrar_bul(ws: list[dict], serbest=TEKRAR_SERBEST) -> tuple[set[int], list[str]]:
    """Art arda aynı 1-3 kelime ve kopyalar arası < 1,5 sn: İLK kopya atılır (son deneme kalır).
    4+ harfli bir kelime 2-5 kelime sonra yeniden geçiyorsa [ADAY] olarak raporlanır: yeniden
    başlama olabilir ("bu videoda gene, bu videoda"), karar Claude'un."""
    t = [norm(w["word"]) for w in ws]
    at: set[int] = set()
    aday: list[str] = []
    for i in range(len(t)):
        for n in (3, 2, 1):
            if i + 2 * n <= len(t) and t[i:i + n] == t[i + n:i + 2 * n] and all(t[i:i + n]):
                if n == 1 and t[i] in serbest:
                    continue
                if ws[i + n]["start"] - ws[i + n - 1]["end"] < TEKRAR_ARA:
                    at.update(range(i, i + n))
                    break
        for j in range(i + 2, min(i + 6, len(t))):
            if t[i] and t[i] == t[j] and len(t[i]) >= 4 and i not in at:
                aday.append(f"{ws[i]['start']:.2f}: " + " ".join(w["word"].strip() for w in ws[i:j + 2]))
                break
    return at, aday


def otomatik_tekrar(ws: list[dict], korunacak=(), serbest=TEKRAR_SERBEST) -> tuple[list[int], list[tuple[float, float]], list[str]]:
    """tekrar_bul + iki istisna: cümle sonu noktalı kelime atılmaz ("yaptık. Yaptık ki"),
    korunacak aralıktaki tekrar atılmaz (bilerek yapılan vurgu). Atılan kelimeler ardışık
    gruplara toplanır; her grubun aralığı ilk kelimenin başından SONRAKİ kelimenin başına kadar
    (kesim noktası iki kopya arasındaki sessizliğe oturur)."""
    at, aday = tekrar_bul(ws, serbest)
    at = {i for i in at
          if ws[i]["word"].strip()[-1:] not in CUMLE_SONU
          and not any(k[0] <= ws[i]["start"] < k[1] for k in korunacak)}
    idx = sorted(at)
    araliklar: list[tuple[float, float]] = []
    j = 0
    while j < len(idx):
        k = j
        while k + 1 < len(idx) and idx[k + 1] == idx[k] + 1:
            k += 1
        son = idx[k]
        y = ws[son + 1]["start"] if son + 1 < len(ws) else ws[son]["end"]
        araliklar.append((ws[idx[j]]["start"], max(y, ws[idx[j]]["start"] + 0.01)))
        j = k + 1
    aday = [a for a in aday if not any(k[0] <= float(a.split(":")[0]) < k[1] for k in korunacak)]
    return idx, araliklar, aday


# =====================================================================================
# Parçalar
# =====================================================================================

def atilmis(w: dict, araliklar) -> bool:
    """Kelimenin ORTASI bir atma aralığındaysa kelime atılmıştır. Başlangıca bakmak yetmiyor:
    Whisper başı erken damgalar, aralığı ses sınırından yazınca sonraki kelimenin damgası
    aralığın içine taşıyordu ("Durdukları" 159,985'te damgalı, sesi 160,12'de)."""
    m = (w["start"] + w["end"]) / 2
    return any(x <= m < y for x, y, *_ in araliklar)


def parcalar(ws: list[dict], en: Enerji, a: float, b: float, atla: list[tuple[float, float]]) -> list[list[float]]:
    """[a, b] bloğunu ENERJİDEN kurar; kelimeler yalnızca hangi bölgenin tutulacağını söyler.

    1. sesli bölgeler: eşik üstü kareler; 0,12 sn'den kısa boşluk kapanır, 0,06'dan kısa ada atılır
    2. atılan aralık sınırları ±0,2 sn içindeki en sessiz kareye oturur, bölge oradan bölünür;
       oturtulmuş aralığın tamamen içinde kalan bölge her zaman atılır
    3. kalan bölge, tutulan kelimelerle örtüşmesi atılanlarla örtüşmesinden büyük ya da eşitse tutulur;
       kelimesiz bölge 0,2 sn'den uzun, konuşma seviyesinde (eşik +12 dB) ve iki komşusu
       tutuluyorsa kalır (Whisper'ın yazmadığı söz)
    4. baş -0,06 sn; son +0,28 (cümle sonu) / +0,12 (cümle içi); komşu bölgeye taşmaz
    """
    db = en.db
    i0, i1 = max(0, kare(a)), min(len(db), kare(b))
    bolge: list[list[int]] = []
    j = i0
    while j < i1:
        if db[j] >= en.esik:
            k = j
            while k < i1 and db[k] >= en.esik:
                k += 1
            if bolge and (j - bolge[-1][1]) < BOSLUK_KAPAT:
                bolge[-1][1] = k
            else:
                bolge.append([j, k])
            j = k
        else:
            j += 1
    bolgeler = [(x * KARE, y * KARE) for x, y in bolge if y - x >= ADA_EN_AZ]

    def oturt(t):
        return en.sessiz_kare(t) if a < t < b else t

    kesik = [(oturt(x), oturt(y)) for x, y in atla]
    kesimler = sorted({x for x, _ in kesik if a < x < b} | {y for _, y in kesik if a < y < b})
    parca: list[tuple[float, float]] = []
    for x, y in bolgeler:
        noktalar = [x] + [c for c in kesimler if x < c < y] + [y]
        parca += list(zip(noktalar, noktalar[1:]))

    def atildi(w):
        return atilmis(w, atla)

    def ortusme(x, y, kume):
        return sum(max(0.0, min(y, w["end"] + ORTUSME_PAY) - max(x, w["start"] - ORTUSME_PAY)) for w in kume)

    icerik = [w for w in ws if a - 0.5 <= w["start"] < b + 0.5]
    tut_w = [w for w in icerik if not atildi(w) and a <= w["start"] < b]
    at_w = [w for w in icerik if atildi(w)]
    karar = []
    for x, y in parca:
        if any(sx - 1e-6 <= x and y <= sy + 1e-6 for sx, sy in kesik):
            karar.append("at")          # atma aralığının içinde: komşu kelimenin erken damgası kurtaramaz
            continue
        k, d = ortusme(x, y, tut_w), ortusme(x, y, at_w)
        karar.append("tut" if k > 0 and k >= d else ("at" if (k > 0 or d > 0) else "bos"))
    for n, (x, y) in enumerate(parca):
        if karar[n] == "bos":
            komsu = 0 < n < len(parca) - 1 and karar[n - 1] == "tut" and karar[n + 1] == "tut"
            guclu = en.ortalama(x, y) >= en.esik + BOS_GUC
            karar[n] = "tut" if (y - x >= BOS_EN_AZ and komsu and guclu) else "at"

    out: list[list[float]] = []
    for n, (x, y) in enumerate(parca):
        if karar[n] != "tut":
            continue
        onceki = parca[n - 1][1] if n > 0 else a
        sonraki = parca[n + 1][0] if n + 1 < len(parca) else b
        son_w = [w for w in tut_w if w["start"] < y + 0.1]
        cumle = bool(son_w) and son_w[-1]["word"].strip()[-1:] in CUMLE_SONU
        s_ = max(a, onceki + 0.01, x - BAS_PAY)
        e_ = min(b, sonraki - 0.01, y + (SON_CUMLE if cumle else SON_ICI))
        if out and s_ - out[-1][1] < BIRLESTIR:
            out[-1][1] = e_
        else:
            out.append([s_, e_])
    return [[round(s, 3), round(e, 3)] for s, e in out if e - s > EN_KISA]


def bas_sabitle(en: Enerji, a: float) -> float:
    """Blok başı kelimenin ortasına düşmesin: ±0,25 sn içindeki en sessiz kare."""
    if a <= 0:
        return 0.0
    return en.sessiz_kare(a, BAS_SABITLE)


def uzat(en: Enerji, b: float) -> float:
    """Blok sonu son kelimeyi kesmesin: b-0,1'den sonraki ilk >=0,3 sn sessizliğin başı + 0,35 sn."""
    i, son = kare(b - 0.1), min(len(en.db), kare(b + UZAT_EN_COK))
    gerek = int(round(UZAT_SESSIZ / KARE))
    while i < son:
        if en.db[i] < en.esik:
            j = i
            while j < len(en.db) and en.db[j] < en.esik:
                j += 1
            if j - i >= gerek or j >= len(en.db):
                return min(en.sure, max(b, i * KARE + UZAT_PAY))
            i = j
        else:
            i += 1
    return min(en.sure, b + UZAT_EN_COK)


def hizlandir(en: Enerji, ws: list[dict], pp: list[list[float]]) -> list[list[float]]:
    """Sürekli parçalarda konuşmasız aralıklar 2x / 4x. Kenarlarda 0,35 sn normal kalır,
    6 sn'den uzun hızlanan kısım 4x. Konuşma yok sayılan yer: ses eşiğin altında VE Whisper
    kelimesi yok. Sessiz koşunun içine damgalanmış kelime (fısıltı ya da erken damga) koşuyu
    böler, kelimenin ±0,1 sn'si hiçbir zaman hızlanmaz. Dönen her öğe [baş, son, hız]."""
    out: list[list[float]] = []
    for s, e in pp:
        kosu: list[list[float]] = []
        for x, y in en.kosular(s, e, HIZ_KOSU):
            if kosu and x - kosu[-1][1] < HIZ_BIRLESTIR:
                kosu[-1][1] = y
            else:
                kosu.append([x, y])
        alt: list[tuple[float, float]] = []
        for x, y in kosu:
            for w in sorted((w for w in ws if w["end"] > x and w["start"] < y), key=lambda w: w["start"]):
                if w["start"] - 0.1 > x:
                    alt.append((x, w["start"] - 0.1))
                x = max(x, w["end"] + 0.1)
            if y > x:
                alt.append((x, y))
        kes = []
        for x, y in alt:
            if y - x < HIZ_EN_AZ:
                continue
            x2, y2 = x + HIZ_KENAR, y - HIZ_KENAR
            if y2 - x2 >= 2.0:
                kes.append((x2, y2, 4 if y2 - x2 >= HIZ_4X else 2))
        bas = s
        for x, y, h in kes:
            if x > bas:
                out.append([round(bas, 3), round(x, 3), 1])
            out.append([round(x, 3), round(y, 3), h])
            bas = y
        if e > bas:
            out.append([round(bas, 3), round(e, 3), 1])
    return out


# =====================================================================================
# Kare ızgarası
# =====================================================================================

def kareye(i: float, o: float, hiz: float = 1, fps: int = 30) -> tuple[float, int]:
    """Parçanın görüntüdeki başı (kareye yuvarlanmış) ve çıktıdaki kare sayısı. Baş ve süre
    AYRI yuvarlanır ama süre tam kare sayısıdır: 200+ parçada ses ile görüntü ayrı ayrı
    yuvarlanırsa kayma birikiyor."""
    return round(i * fps) / fps, max(1, round((o - i) / hiz * fps))


def sure(p: dict, fps: int = 30) -> float:
    return kareye(p["in"], p["out"], p.get("hiz", 1), fps)[1] / fps


def ses_araligi(p: dict, fps: int = 30, sr: int = SR) -> tuple[int, int]:
    """Parçanın sesi: ilk örnek ve örnek sayısı (kare sayısı x sr/fps; hızlanan parçada aralığın
    kendi sesinin başı, normal hızda)."""
    if sr % fps:
        raise ValueError(f"fps {fps} {sr}'i tam bölmüyor; geçerli: {FPS_GECERLI}")
    i, n = kareye(p["in"], p["out"], p.get("hiz", 1), fps)
    return round(i * sr), n * (sr // fps)


def zaman_cizelgesi(pp: list[dict], fps: int = 30) -> list[float]:
    """Her parçanın çıktıdaki başlangıç saniyesi (tam kare)."""
    out, n = [], 0
    for p in pp:
        out.append(n / fps)
        n += kareye(p["in"], p["out"], p.get("hiz", 1), fps)[1]
    return out


def cikti_zamani(x: float, pp: list[dict], fps: int = 30) -> float:
    """Kaynak saniyesi -> çıktı saniyesi. Atılan yere düşen an bir sonraki parçanın başına gider."""
    t = 0.0
    for p in pp:
        d = sure(p, fps)
        if p["in"] <= x < p["out"]:
            return t + min(d, (x - p["in"]) / p.get("hiz", 1))
        if x < p["in"]:
            return t
        t += d
    return t


def kaynak_zamani(t: float, pp: list[dict], fps: int = 30) -> float:
    """Çıktı saniyesi -> kaynak saniyesi."""
    bas = 0.0
    for p in pp:
        d = sure(p, fps)
        if t < bas + d:
            return p["in"] + (t - bas) * p.get("hiz", 1)
        bas += d
    return pp[-1]["out"] if pp else 0.0


# =====================================================================================
# Girdi dosyaları
# =====================================================================================

def aralik_listesi(veri, ad: str = "atilacak.json") -> list[tuple[float, float, str]]:
    """[{bas, son, gerekce}] -> [(bas, son, gerekce)]. Gerekçe ZORUNLU: altı ay sonra "bu neden
    atılmış" sorusunun cevabı orada."""
    if isinstance(veri, dict):
        veri = veri.get("aralik") or veri.get("atilacak") or []
    out = []
    for n, r in enumerate(veri):
        bas, son, ger = float(r["bas"]), float(r["son"]), str(r.get("gerekce", "")).strip()
        if son <= bas:
            raise ValueError(f"{ad} #{n}: son ({son}) baştan ({bas}) büyük olmalı")
        if not ger:
            raise ValueError(f"{ad} #{n} ({bas}-{son}): gerekce boş olamaz")
        out.append((bas, son, ger))
    return sorted(out)


def blok_listesi(veri, sure_: float) -> list[dict]:
    """bloklar.json -> [{etiket, bas, son, goruntu}]. Yoksa tüm kayıt tek 'kamera' bloğu."""
    if not veri:
        return [{"etiket": "kayıt", "bas": 0.0, "son": sure_, "goruntu": "kamera"}]
    out = []
    for n, r in enumerate(veri):
        g = r.get("goruntu", "kamera")
        if g not in GORUNTU_TURLERI:
            raise ValueError(f"bloklar.json #{n}: goruntu '{g}' bilinmiyor; olanlar: {', '.join(GORUNTU_TURLERI)}")
        bas, son = max(0.0, float(r["bas"])), min(sure_, float(r["son"]))
        if son <= bas:
            raise ValueError(f"bloklar.json #{n}: son ({son}) baştan ({bas}) büyük olmalı")
        out.append({"etiket": str(r.get("etiket", f"blok {n + 1}")), "bas": bas, "son": son, "goruntu": g,
                    "kose": r.get("kose", True)})
    return out


# =====================================================================================
# Plan
# =====================================================================================

def kelime_ata(ws: list[dict], pp: list, adaylar) -> dict[int, int]:
    """Kelime -> en çok örtüştüğü parçanın sırası. Kelime aralığı ±0,3 sn genişletilir (Whisper
    başı erken damgalar; parça sesten 0,06 sn önce başlar, damga ondan da önce olabilir).
    Hiçbir parçaya değmeyen kelime atanmaz (düşmüş sayılır). `pp` öğeleri [baş, son, ...]."""
    ata = {}
    for i in adaylar:
        a, b = ws[i]["start"] - ORTUSME_PAY, ws[i]["end"] + ORTUSME_PAY
        en_iyi, en_cok = None, 0.0
        for j, p in enumerate(pp):
            if p[0] > b:
                break
            o = min(b, p[1]) - max(a, p[0])
            if o > en_cok:
                en_iyi, en_cok = j, o
        if en_iyi is not None:
            ata[i] = en_iyi
    return ata


def _mmss(t: float, ondalik: int = 2) -> str:
    g = 3 + ondalik if ondalik else 2
    return f"{int(t // 60):02d}:{t % 60:0{g}.{ondalik}f}"


def plan_kur(ws: list[dict], en: Enerji, bloklar: list[dict], atilacak=(), korunacak=(),
             serbest=TEKRAR_SERBEST, fps: int = 30, zoom: float = 1.06) -> tuple[list[dict], list[str], dict]:
    """Bloklar + gerekçeli atma listesi + otomatik tekrar -> parçalar, döküm satırları, sayılar."""
    if fps not in FPS_GECERLI:
        raise ValueError(f"fps {fps} geçersiz; olanlar: {FPS_GECERLI}")
    oto_idx, oto_aralik, adaylar = otomatik_tekrar(ws, korunacak, serbest)
    oto_kume = set(oto_idx)

    # blok sınırları sessiz kareye; bitişik bloklar birbirine taşmaz
    sinir = []
    for bi, bl in enumerate(bloklar):
        a, b = bas_sabitle(en, bl["bas"]), uzat(en, bl["son"])
        if bi + 1 < len(bloklar) and bloklar[bi + 1]["bas"] >= bl["bas"]:
            b = min(b, bas_sabitle(en, bloklar[bi + 1]["bas"]))
        if sinir and bloklar[bi - 1]["bas"] <= bl["bas"]:
            a = max(a, sinir[-1][1])
        sinir.append((a, max(a, b)))

    parca: list[dict] = []
    satir: list[str] = []
    t, z, onceki_out = 0.0, 1.0, None
    say = {"elle": 0, "elle_sn": 0.0, "tekrar": 0, "aday": 0, "dustu": 0}
    for bi, (bl, (a, b)) in enumerate(zip(bloklar, sinir)):
        gor = bl["goruntu"]
        elle = [(x, y) for x, y, _ in atilacak if x < b and y > a]
        if gor == "ekran-hizli":
            pp0, s_ = [], a
            for x, y in sorted(elle):
                x, y = en.sessiz_kare(x), en.sessiz_kare(y)
                if x > s_:
                    pp0.append([s_, x])
                s_ = max(s_, y)
            if b > s_:
                pp0.append([s_, b])
            pp = hizlandir(en, ws, pp0)
        else:
            otoa = [(x, y) for x, y in oto_aralik if a <= x < b]
            pp = [[s, e, 1] for s, e in parcalar(ws, en, a, b, elle + otoa)]

        satir.append(f"\n## {_mmss(t, 1)}  {bl['etiket']}  (kaynak {a:.2f}–{b:.2f}, {gor})")
        for x, y, neden in atilacak:
            if a <= x < b:
                satir.append(f"   ATILDI {x:.2f}–{y:.2f}: {neden}")
                say["elle"] += 1
                say["elle_sn"] += min(y, b) - x
        if gor != "ekran-hizli":
            for i in oto_idx:
                if a <= ws[i]["start"] < b:
                    satir.append(f"   TEKRAR {ws[i]['start']:.2f}: {ws[i]['word'].strip()}")
                    say["tekrar"] += 1
        for s in adaylar:
            if a <= float(s.split(":")[0]) < b:
                satir.append(f"   [ADAY] {s}")
                say["aday"] += 1

        blok_ws = [(i, w) for i, w in enumerate(ws) if a <= w["start"] < b]
        atilan = {i for i, w in blok_ws if atilmis(w, elle)
                  or (gor != "ekran-hizli" and i in oto_kume)}
        ata = kelime_ata(ws, pp, [i for i, _ in blok_ws if i not in atilan])
        dustu = [(i, w) for i, w in blok_ws if i not in ata and i not in atilan]
        say["dustu"] += len(dustu)
        grup: list[list] = []
        for i, w in dustu:
            if grup and i == grup[-1][-1][0] + 1:
                grup[-1].append((i, w))
            else:
                grup.append([(i, w)])
        for g in grup:
            satir.append(f"   DÜŞTÜ {g[0][1]['start']:.2f}: " + " ".join(w["word"].strip() for _, w in g))

        for j, (s, e, hiz) in enumerate(pp):
            zz = 1.0
            if gor == "kamera" and zoom > 1.0:
                if j == 0 or onceki_out is None or s - onceki_out > ZOOM_ATLAMA:
                    z = zoom if z == 1.0 else 1.0
                onceki_out = e
                zz = z
            kel = sorted(i for i, k in ata.items() if k == j)
            parca.append({"blok": bi, "etiket": bl["etiket"], "in": s, "out": e, "gorsel": gor, "hiz": hiz,
                          "zoom": zz, "kose": bl.get("kose", True), "t": round(t, 3), "kelimeler": kel})
            metin = " ".join(ws[i]["word"].strip() for i in kel)
            satir.append(f"   {_mmss(t)} [{s:7.2f}–{e:7.2f}]{f' {hiz}x' if hiz > 1 else ''} {metin}")
            t += kareye(s, e, hiz, fps)[1] / fps

    kullanilan = sum(b - a for a, b in sinir)
    sayilar = {"kaynak_sn": round(en.sure, 2), "blok_sn": round(kullanilan, 2), "cikti_sn": round(t, 3),
               "parca": len(parca), "blok": len(bloklar), "birlesim": max(0, len(parca) - 1),
               "elle_atma": say["elle"], "elle_sn": round(say["elle_sn"], 2), "oto_tekrar_kelime": say["tekrar"],
               "aday": say["aday"], "dustu_kelime": say["dustu"],
               "hizli_parca": sum(1 for p in parca if p["hiz"] > 1)}
    return parca, satir, sayilar


def dokum_metni(satir: list[str], sayilar: dict, baslik: str = "Kurgu dökümü") -> str:
    k, c = sayilar["kaynak_sn"], sayilar["cikti_sn"]
    oran = (1 - c / k) * 100 if k else 0
    bas = [
        f"# {baslik}",
        "",
        f"Kaynak {_mmss(k, 1)} → kurgu {_mmss(c, 1)} (%{oran:.1f} kısaldı) · {sayilar['parca']} parça · "
        f"{sayilar['blok']} blok · {sayilar['elle_atma']} elle atma ({sayilar['elle_sn']:.1f} sn) · "
        f"{sayilar['oto_tekrar_kelime']} otomatik tekrar kelimesi · {sayilar['aday']} aday · "
        f"{sayilar['dustu_kelime']} düşen kelime · {sayilar['hizli_parca']} hızlı parça",
        "",
        "Okuma: `MM:SS.ss [kaynak baş–son] metin` = çıktıda kalan parça (kaynak saniyesi, atilacak.json bu",
        "saniyelerle yazılır). ATILDI = atilacak.json'dan, TEKRAR = otomatik atılan art arda tekrar,",
        "[ADAY] = yeniden başlama olabilir (karar senin), DÜŞTÜ = sesten ötürü düşen kelime (Whisper",
        "uydurması ya da gerçekten kaybolan söz olabilir; `zarf` ile bak).",
    ]
    return "\n".join(bas + satir) + "\n"


# =====================================================================================
# Harfiyen döküm parçaları
# =====================================================================================

def dokum_parcalari(en: Enerji, en_cok: float = 10.0, sessiz: float = 0.3) -> list[tuple[float, float]]:
    """Kaydı sessizliklerin ortasından <= en_cok sn'lik parçalara böler. Her parça Whisper'a
    BAĞIMSIZ verilir: uzun bağlamda Whisper tekrarları yutuyor ("bu işi, bu işi beş" -> "bu işi
    5"), kısa parçada harfiyen yazıyor. Sınır önce >= 0,3 sn'lik, yoksa >= 0,12 sn'lik bir
    sessizliğin ortası, o da yoksa en kısık kare. Konuşmasız parça atlanır."""
    sure_ = en.sure
    uzun = [(x + y) / 2 for x, y in en.kosular(0, sure_, sessiz)]
    kisa = [(x + y) / 2 for x, y in en.kosular(0, sure_, 0.12)]
    out, bas = [], 0.0
    while sure_ - bas > en_cok:
        aday = ([x for x in uzun if bas + 2 < x <= bas + en_cok]
                or [x for x in kisa if bas + 2 < x <= bas + en_cok])
        son = aday[-1] if aday else en.sessiz_kare(bas + en_cok / 2 + 1, en_cok / 2 - 1)
        out.append((bas, son))
        bas = son
    out.append((bas, sure_))
    return [(round(a, 3), round(b, 3)) for a, b in out if b - a > 0.05 and en.konusma(a, b, 0.15)]


# =====================================================================================
# Birleşim denetimi
# =====================================================================================

def birlesim_denetle(pp: list[dict], ws: list[dict], yeni: list[dict], fps: int = 30,
                     pencere: float = 1.6, esik: float = 0.72) -> tuple[list[dict], dict]:
    """Kesik sesin yeniden çözümü (yeni) ile planın beklediği kelimeleri karşılaştırır.

    Her birleşimde önceki parçanın son 2 ve sonrakinin ilk 2 kelimesi, yeni dökümde birleşim
    anının ±1,6 sn'sinde aranır (benzerlik > 0,72). Bulunamayan = EKSİK (kopan kelime).
    Birleşime 1,5 sn'den yakın ATILAN bir kelime duyuluyorsa ve o çevrede tutulan kelimeler
    arasında yoksa = SIZAN (atılması gereken ses kalmış)."""
    ait: list[list[int]] = [[] for _ in pp]
    if all("kelimeler" in p for p in pp):          # plan_kur'un atadığı kelimeler
        for k, p in enumerate(pp):
            ait[k] = list(p["kelimeler"])
    else:                                           # eski plan: orta noktası parçada olan kelime
        for i, w in enumerate(ws):
            m = (w["start"] + w["end"]) / 2
            for k, p in enumerate(pp):
                if p["in"] <= m < p["out"]:
                    ait[k].append(i)
                    break
    tutulan = {i for a in ait for i in a}
    t0 = zaman_cizelgesi(pp, fps)
    cikti_t = {}
    for k, p in enumerate(pp):
        for i in ait[k]:
            cikti_t[i] = t0[k] + max(0.0, (ws[i]["start"] - p["in"]) / p.get("hiz", 1))
    yeni_n = [(w["start"], norm(w["word"])) for w in yeni]
    rapor = []
    for k in range(1, len(pp)):
        p, q, T = pp[k], pp[k - 1], t0[k]
        once = [norm(ws[i]["word"]) for i in ait[k - 1]][-2:]
        sonra = [norm(ws[i]["word"]) for i in ait[k]][:2]
        duyulan = [x for s, x in yeni_n if T - pencere <= s <= T + pencere and x]
        eksik = [w for w in once + sonra if w and not any(benzer(w, x) > esik for x in duyulan)]
        cevre = {norm(ws[i]["word"]) for i, tt in cikti_t.items() if abs(tt - T) <= pencere + 0.5}
        atilan = [norm(w["word"]) for i, w in enumerate(ws) if i not in tutulan
                  and (abs(w["start"] - p["in"]) < 1.5 or abs(w["start"] - q["out"]) < 1.5)]
        sizan = sorted({w for w in atilan if len(w) > 2 and w in duyulan and w not in cevre})
        if eksik or sizan:
            rapor.append({"no": k, "t": round(T, 3), "etiket": p.get("etiket", ""), "onceki_out": q["out"],
                          "in": p["in"], "once": once, "sonra": sonra, "duyulan": duyulan,
                          "eksik": eksik, "sizan": sizan})
    beklenen = sum(1 for i in tutulan if norm(ws[i]["word"]))
    ozet = {"birlesim": max(0, len(pp) - 1), "supheli": len(rapor),
            "eksik": sum(1 for r in rapor if r["eksik"]), "sizan": sum(1 for r in rapor if r["sizan"]),
            "beklenen_kelime": beklenen, "duyulan_kelime": sum(1 for _, x in yeni_n if x)}
    return rapor, ozet


def dogrula_metni(rapor: list[dict], ozet: dict) -> str:
    satir = [
        f"# Birleşim denetimi — {ozet['birlesim']} birleşim, {ozet['supheli']} şüpheli",
        "",
        f"EKSİK olan {ozet['eksik']}, SIZAN olan {ozet['sizan']}. Beklenen kelime {ozet['beklenen_kelime']}, "
        f"yeniden çözümde duyulan {ozet['duyulan_kelime']}.",
        "",
        "Her satır: çıktı zamanı, parça no, blok, kaynak sınırı (önceki parçanın sonu | bu parçanın başı),",
        "beklenen kelimeler ve yeniden çözümde duyulanlar. Şüpheliyi `pencere` ile yeniden dinlet,",
        "`zarf` ile sese bak; gerçekse atilacak.json'ı düzelt ve `kurgu` + `cek`'i yeniden çalıştır.",
        "EKSİK çoğu zaman Whisper'ın kısa kelimeyi (ve, de, bu) yeniden duymamasıdır; önce dinlet.",
        "",
    ]
    for r in rapor:
        satir.append(
            f"- {_mmss(r['t'])} parça {r['no']} ({r['etiket']}, kaynak {r['onceki_out']:.2f} | {r['in']:.2f}): "
            f"beklenen …{' '.join(r['once'])} | {' '.join(r['sonra'])}… duyulan: {' '.join(r['duyulan'])}"
            + (f"  EKSİK: {', '.join(r['eksik'])}" if r["eksik"] else "")
            + (f"  SIZAN: {', '.join(r['sizan'])}" if r["sizan"] else ""))
    return "\n".join(satir) + "\n"


# =====================================================================================
# Senkron: doğru uydurma (numpy'sız, test edilebilir)
# =====================================================================================

def dogru_uydur(noktalar: list[tuple[float, float, float]], en_az_r: float = 0.3) -> tuple[float, float, list]:
    """[(t, ofset, r)] -> ofset(t) = a + b*t. Ağırlık r; r < en_az_r atılır; artığı medyan
    sapmanın 3 katından (en az 20 ms) büyük nokta aykırı sayılıp bir kez yeniden uydurulur.
    Dönen: (a, b, kullanılan noktalar)."""
    iyi = [(t, o, r) for t, o, r in noktalar if r >= en_az_r]
    if not iyi:
        return 0.0, 0.0, []

    def uydur(ps):
        if len(ps) == 1:
            return ps[0][1], 0.0
        W = sum(r for _, _, r in ps)
        mt = sum(t * r for t, _, r in ps) / W
        mo = sum(o * r for _, o, r in ps) / W
        st = sum(r * (t - mt) ** 2 for t, _, r in ps)
        b = 0.0 if st < 1e-9 else sum(r * (t - mt) * (o - mo) for t, o, r in ps) / st
        return mo - b * mt, b

    a, b = uydur(iyi)
    art = [abs(o - (a + b * t)) for t, o, _ in iyi]
    mad = sorted(art)[len(art) // 2]
    sinir = max(0.02, 3 * mad)
    kalan = [p for p, x in zip(iyi, art) if x <= sinir]
    if len(kalan) >= 2 and len(kalan) < len(iyi):
        a, b = uydur(kalan)
        iyi = kalan
    return a, b, iyi
