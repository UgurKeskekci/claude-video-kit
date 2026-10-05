"""Yüz kadrajı: yüz kutusu (kaynak pikseli), düzene göre kırpma, kaynak kare okuyucu.

Yüz kutusu iki yoldan gelir:
  1. `reels.py yuz` — hızlı otomatik tahmin (model YOK: ten rengi + merkez önceliği, numpy). Kaba bir
     tahmindir; `kontrol/kadraj.jpg`'de kutuyu ve kırpmaları çizer. Claude bu resme BAKAR.
  2. Claude ya da kullanıcı `kadraj.json`'u elle yazar/düzeltir (kareye bakıp piksel okuyarak).

kadraj.json:
    {"kaynak": [3840, 2160], "kutu": [x, y, w, h]}                    # sabit kamera
    {"kaynak": [...], "anahtarlar": [{"t": 0.0, "kutu": [...]}, ...]}  # kişi kayıyorsa: t kaynak saniyesi,
                                                                       # aradaki kareler doğrusal izler
    isteğe bağlı: "bol": {"yuz_boy": 330, "merkez_y": 235}, "yuz": {"yuz_boy": 560, "merkez_y": 800}
Kutu = alından çeneye, kulaktan kulağa yüz (saç ve boyun hariç).
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from cizim import FPS, H, W, YUZ_KARTI_ALT_EN_COK, YUZ_KARTI_UST, YUZ_KARTI_X, font
from proje import json_oku, json_yaz

KART_W = W - 2 * YUZ_KARTI_X                      # bol düzende yüz kartı: 1032 genişlik
KART_H_EN_COK = YUZ_KARTI_ALT_EN_COK - YUZ_KARTI_UST  # en çok 826 yükseklik (gerçeği kaynağa göre)
KART_H_EN_AZ = 560
HEDEF = {
    # çıktı boyutu, yüzün çıktıdaki yüksekliği (px), yüz merkezinin çıktıdaki y'si
    "bol": {"cikis": (KART_W, KART_H_EN_COK), "yuz_boy": 380, "merkez_y": 240},
    "yuz": {"cikis": (W, H), "yuz_boy": 560, "merkez_y": 800},
}


# ------------------------------------------------------------------ video bilgisi
def video_bilgi(yol) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:stream_side_data=rotation:format=duration",
                        "-of", "json", str(yol)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    s = j["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) % 180 == 90:          # telefon dikey kaydı: ffmpeg çözerken döndürür
        w, h = h, w
    return {"w": w, "h": h, "sure": float(j["format"]["duration"])}


# ------------------------------------------------------------------ kadraj
class Kadraj:
    def __init__(self, P):
        self.P = P
        vb = video_bilgi(P.video)
        self.SW, self.SH = vb["w"], vb["h"]
        kj = json_oku(P.d / "kadraj.json")
        if not kj:
            raise SystemExit(f"{P.d / 'kadraj.json'} yok. Önce: reels.py yuz {P.d}  (sonra kontrol/kadraj.jpg'ye bak)")
        if kj.get("kaynak") and list(kj["kaynak"]) != [self.SW, self.SH]:
            raise SystemExit(f"kadraj.json {kj['kaynak']} kaynak için yazılmış, video {self.SW}x{self.SH}")
        if kj.get("anahtarlar"):
            a = sorted(kj["anahtarlar"], key=lambda x: x["t"])
            self.ta = np.array([x["t"] for x in a], float)
            self.ka = np.array([x["kutu"] for x in a], float)
        else:
            self.ta = np.array([0.0])
            self.ka = np.array([kj["kutu"]], float)
        self.hedef = {d: {**HEDEF[d], **kj.get(d, {})} for d in HEDEF}
        # Yüz kartının boyu: yüz kartın üstünde (merkez_y) dururken altında kaynakta kalan görüntü kadar.
        # Yatay kayıtta yüz karenin ortasındaysa altta az görüntü vardır; kart uzun tutulursa kırpma
        # aşağı kayar ve çene platformun alt %20'sine iner (ölçüldü: 1611 > 1536). Kart kısalır.
        hb = self.hedef["bol"]
        oda = []
        for x, y, w, h in self.ka:
            s = hb["yuz_boy"] / max(h, 1.0)
            oda.append((self.SH - (y + h / 2)) * s + hb["merkez_y"])
        kh = int(max(KART_H_EN_AZ, min(KART_H_EN_COK, min(oda))))
        hb["cikis"] = (KART_W, kh - kh % 2)

    def kutu(self, ts: float) -> np.ndarray:
        if len(self.ta) == 1:
            return self.ka[0]
        return np.array([np.interp(ts, self.ta, self.ka[:, i]) for i in range(4)])

    def kirp(self, duzen: str, ts: float, zoom: float = 1.0) -> tuple[float, float, float, float]:
        """Kaynakta kırpılacak dikdörtgen (x0, y0, x1, y1) ve ölçek: yüz hedef boya, hedef yere."""
        x, y, w, h = self.kutu(ts)
        hd = self.hedef[duzen]
        ow, oh = hd["cikis"]
        s = hd["yuz_boy"] / max(h, 1.0) * zoom
        s = max(s, ow / self.SW, oh / self.SH)              # kaynaktan büyük kırpılamaz
        cw, ch = ow / s, oh / s
        x0 = x + w / 2 - (ow / 2) / s
        y0 = y + h / 2 - hd["merkez_y"] / s
        x0 = min(max(x0, 0.0), self.SW - cw)
        y0 = min(max(y0, 0.0), self.SH - ch)
        return x0, y0, x0 + cw, y0 + ch

    def cikti_kutusu(self, duzen: str, ts: float, zoom: float = 1.0) -> tuple[float, float, float, float]:
        """Yüz kutusunun çıktı karesindeki yeri (bol düzende yüz kartı ofsetiyle)."""
        x0, y0, x1, y1 = self.kirp(duzen, ts, zoom)
        ow, _ = self.hedef[duzen]["cikis"]
        s = ow / (x1 - x0)
        x, y, w, h = self.kutu(ts)
        ox, oy = (YUZ_KARTI_X, YUZ_KARTI_UST) if duzen == "bol" else (0, 0)
        return (x - x0) * s + ox, (y - y0) * s + oy, (x + w - x0) * s + ox, (y + h - y0) * s + oy


# ------------------------------------------------------------------ kaynak kare okuyucu
class Okuyucu:
    """Kaynağı 30 fps ızgarasında, gereken bölgeyi kırpıp çalışma ölçeğine indirerek SIRAYLA okur.
    Çalışma ölçeği = karelerin isteyeceği en büyük ölçek (en çok 1): 4K'yı tam çözüp boru hattına
    25 MB/kare basmak yerine yalnız kullanılan bölge, gereken çözünürlükte gelir."""

    def __init__(self, P, kd: Kadraj, istekler: list[tuple[str, float, float]]):
        self.P, self.kd = P, kd
        kutular = [kd.kirp(d, ts, z) for d, ts, z in istekler] or [(0, 0, kd.SW, kd.SH)]
        ux0 = max(0, int(min(b[0] for b in kutular)) - 8)
        uy0 = max(0, int(min(b[1] for b in kutular)) - 8)
        ux1 = min(kd.SW, int(max(b[2] for b in kutular)) + 8)
        uy1 = min(kd.SH, int(max(b[3] for b in kutular)) + 8)
        olcek = 0.0
        for (d, _, _), b in zip(istekler, kutular):
            olcek = max(olcek, kd.hedef[d]["cikis"][0] / (b[2] - b[0]))
        self.s = min(1.0, olcek or 1.0)
        self.u = (ux0, uy0, ux1, uy1)
        self.ww = int(round((ux1 - ux0) * self.s / 2)) * 2
        self.wh = int(round((uy1 - uy0) * self.s / 2)) * 2
        self.akis = None
        self.sira = -1
        self.son = None
        self.son_ts = max([ts for _, ts, _ in istekler] or [0.0]) + 0.5     # okuma burada biter

    def _filtre(self) -> str:
        ux0, uy0, ux1, uy1 = self.u
        return f"fps={FPS},crop={ux1 - ux0}:{uy1 - uy0}:{ux0}:{uy0},scale={self.ww}:{self.wh}:flags=area"

    def ac(self):
        self.akis = subprocess.Popen(["ffmpeg", "-v", "error", "-hwaccel", "auto", "-i", str(self.P.video),
                                      "-t", f"{self.son_ts:.3f}", "-vf", self._filtre(), "-f", "rawvideo",
                                      "-pix_fmt", "rgb24", "-"],
                                     stdout=subprocess.PIPE, bufsize=self.ww * self.wh * 3 * 2)

    def kare(self, idx: int) -> Image.Image:
        """30 fps ızgarasında idx'inci kare (sırayla artan idx beklenir; geri gidilmez)."""
        if self.akis is None:
            self.ac()
        n = self.ww * self.wh * 3
        while self.sira < idx:
            buf = self.akis.stdout.read(n)
            if len(buf) < n:
                break                      # kaynak bitti: son kare tekrar
            self.sira += 1
            if self.sira >= idx:
                self.son = Image.frombuffer("RGB", (self.ww, self.wh), buf, "raw", "RGB", 0, 1)
        if self.son is None:
            raise RuntimeError("kaynaktan kare okunamadı")
        return self.son

    def tek(self, ts: float) -> Image.Image:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, ts):.3f}", "-i", str(self.P.video),
                            "-frames:v", "1", "-vf", self._filtre(), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True, check=True)
        n = self.ww * self.wh * 3
        if len(r.stdout) < n:
            raise RuntimeError(f"{ts:.2f} sn'de kare okunamadı")
        return Image.frombuffer("RGB", (self.ww, self.wh), r.stdout[:n], "raw", "RGB", 0, 1)

    def kes(self, im: Image.Image, duzen: str, ts: float, zoom: float) -> Image.Image:
        x0, y0, x1, y1 = self.kd.kirp(duzen, ts, zoom)
        ux0, uy0 = self.u[0], self.u[1]
        kutu = ((x0 - ux0) * self.s, (y0 - uy0) * self.s, (x1 - ux0) * self.s, (y1 - uy0) * self.s)
        # Kırpma kaynağın kenarına dayanınca (yüz karenin altına yakın) ww/wh çifte yuvarlandığı için kutu
        # resmi piksel altı aşabiliyor (ölçüldü: 1928,01 > 1928) ve PIL resize hata veriyordu. 1 px'e kadar
        # taşma kenara sabitlenir; daha büyüğü gerçek hatadır, PIL yine yakalar.
        w, h = im.size
        if kutu[0] > -1 and kutu[1] > -1 and kutu[2] < w + 1 and kutu[3] < h + 1:
            kutu = (max(0.0, kutu[0]), max(0.0, kutu[1]), min(w, kutu[2]), min(h, kutu[3]))
        return im.resize(self.kd.hedef[duzen]["cikis"], Image.BILINEAR, box=kutu)

    def kapat(self):
        """Kalan birkaç kareyi boşaltıp kapatır (öldürülen ffmpeg 'Broken pipe' yazıyordu)."""
        if self.akis:
            while self.akis.stdout.read(1 << 20):
                pass
            self.akis.stdout.close()
            self.akis.wait()


# ------------------------------------------------------------------ otomatik tahmin
def _kare_kucuk(video, ts, gen=480) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={gen}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, check=True)
    import io
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB"))


def _deri(rgb: np.ndarray) -> np.ndarray:
    x = rgb.astype(np.float32)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cr = (r - y) * 0.713 + 128
    cb = (b - y) * 0.564 + 128
    return (cr > 136) & (cr < 175) & (cb > 85) & (cb < 128) & (y > 55) & (y < 240) & (r > g + 6) & (r > b + 10)


def _bilesenler(m: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """4 komşulu bağlı bileşenler: (alan, x0, y0, x1, y1). Küçük ızgarada (BFS)."""
    h, w = m.shape
    gor = np.zeros_like(m, bool)
    out = []
    for yy in range(h):
        for xx in range(w):
            if not m[yy, xx] or gor[yy, xx]:
                continue
            yigin = [(yy, xx)]
            gor[yy, xx] = True
            alan, x0, y0, x1, y1 = 0, xx, yy, xx, yy
            while yigin:
                cy, cx = yigin.pop()
                alan += 1
                x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not gor[ny, nx]:
                        gor[ny, nx] = True
                        yigin.append((ny, nx))
            out.append((alan, x0, y0, x1 + 1, y1 + 1))
    return out


def _tahmin1(rgb: np.ndarray) -> tuple[float, float, float, float] | None:
    """Tek karede yüz kutusu (oran olarak 0..1). Ten rengi bloğu + merkez/üst öncelik."""
    m = _deri(rgb)
    h, w = m.shape
    hucre = 6
    gh, gw = h // hucre, w // hucre
    yog = m[:gh * hucre, :gw * hucre].reshape(gh, hucre, gw, hucre).mean(axis=(1, 3))
    iz = yog > 0.45
    en_iyi, puan = None, 0.0
    for alan, x0, y0, x1, y1 in _bilesenler(iz):
        if alan < 6:
            continue
        cx, cy = (x0 + x1) / 2 / gw, (y0 + y1) / 2 / gh
        bw, bh = (x1 - x0) / gw, (y1 - y0) / gh
        doluluk = alan / max(1, (x1 - x0) * (y1 - y0))
        oncelik = np.exp(-((cx - 0.5) / 0.28) ** 2 - ((cy - 0.38) / 0.3) ** 2)
        en_boy = (bh * h) / max(bw * w, 1e-6)        # piksel oranı: yüz ~1,1-1,6, boyunla ~2
        sekil = 1.0 if 0.8 <= en_boy <= 2.6 else 0.4
        p = alan * oncelik * sekil * (0.5 + doluluk)
        if p > puan:
            en_iyi, puan = (x0 / gw, y0 / gh, bw, bh), p
    if not en_iyi:
        return None
    x, y, bw, bh = en_iyi
    # boyun ve göğüs aynı bloğa karışırsa: yüz en fazla genişliğin ~1,35 katı yükseklikte (piksel oranıyla)
    oran = (bh * h) / max(bw * w, 1e-6)
    if oran > 1.45:
        bh = 1.35 * bw * w / h
    return x, y, bw, bh


def tahmin_et(proje: pathlib.Path, ornek: int = 8, zorla: bool = False) -> None:
    from proje import Proje
    P = Proje(proje, senaryo=False)
    kj_yol = proje / "kadraj.json"
    vb = video_bilgi(P.video)
    SW, SH = vb["w"], vb["h"]
    if kj_yol.exists() and not zorla:
        print(f"{kj_yol} zaten var (elle yazılmış olabilir); üzerine yazmak için --zorla. Kontrol resmi yenileniyor.")
        kj = json_oku(kj_yol)
    else:
        # örnek zamanlar: kurguda KALAN parçalardan, eşit aralıklı
        zamanlar = []
        for i in range(ornek):
            n = int((i + 0.5) / ornek * P.konusma_kare)
            zamanlar.append(P.kare_kaynagi(n)[1])
        kutular = []
        for ts in zamanlar:
            rgb = _kare_kucuk(P.video, ts)
            b = _tahmin1(rgb)
            if b:
                kutular.append((ts, [b[0] * SW, b[1] * SH, b[2] * SW, b[3] * SH]))
        if not kutular:
            print("UYARI: yüz bulunamadı (ten rengi bloğu yok). Orta-üst varsayılan kutu yazıldı; "
                  "kontrol/kadraj.jpg'ye bakıp kadraj.json'u ELLE düzelt.")
            kutular = [(0.0, [SW * 0.42, SH * 0.22, SW * 0.16, SH * 0.3])]
        dizi = np.array([k for _, k in kutular])
        med = np.median(dizi, axis=0)
        # aykırı tahmini at (merkezi medyandan yüz genişliğinin 1,2 katından uzak)
        merk = dizi[:, :2] + dizi[:, 2:] / 2
        mm = med[:2] + med[2:] / 2
        iyi = [i for i in range(len(dizi)) if np.hypot(*(merk[i] - mm)) < 1.2 * med[2]]
        atilan = len(dizi) - len(iyi)
        kutular = [kutular[i] for i in iyi]
        dizi = dizi[iyi]
        med = np.median(dizi, axis=0)
        merk = dizi[:, :2] + dizi[:, 2:] / 2
        oynama = float(np.ptp(merk[:, 0])) / SW if len(dizi) > 1 else 0.0
        kj = {"_not": "reels.py yuz tahmini (ten rengi, model yok). kontrol/kadraj.jpg'ye bak; yanlışsa kutu'yu elle düzelt. "
                      "kutu = [x, y, genişlik, yükseklik] kaynak pikseli, alından çeneye yüz.",
              "kaynak": [SW, SH]}
        boy = float(np.median(dizi[:, 3]))
        gen = float(np.median(dizi[:, 2]))
        if oynama > 0.05 and len(dizi) >= 3:
            # kişi kayıyor: anahtar kareler (boyut sabit = medyan; yalnız merkez izlenir, titreme olmasın)
            kj["anahtarlar"] = [{"t": round(ts, 2), "kutu": [round(float(c[0] - gen / 2)), round(float(c[1] - boy / 2)),
                                                            round(gen), round(boy)]}
                                for (ts, _), c in zip(kutular, merk)]
        else:
            kj["kutu"] = [round(float(med[0])), round(float(med[1])), round(gen), round(boy)]
        json_yaz(kj_yol, kj)
        print(f"kadraj.json: {len(kutular)} karede yüz bulundu" + (f", {atilan} aykırı atıldı" if atilan else "")
              + (f", kişi yatayda %{oynama * 100:.0f} kayıyor -> anahtar kareler" if "anahtarlar" in kj else
                 f", sabit kutu {kj['kutu']}"))
    kontrol_resmi(P, kj_yol)


def kontrol_resmi(P, kj_yol) -> None:
    """kontrol/kadraj.jpg: örnek kareler + yüz kutusu (yeşil) + 'bol' (mavi) ve 'yuz' (turuncu) kırpmaları,
    kenarlarda kaynak pikseli cetveli. Claude bu resme bakıp kutuyu onaylar ya da düzeltir."""
    kd = Kadraj(P)
    zamanlar = [P.kare_kaynagi(int((i + 0.5) / 4 * P.konusma_kare))[1] for i in range(4)]
    gen = 720
    olc = gen / kd.SW
    yuk = int(kd.SH * olc)
    sayfa = Image.new("RGB", (gen * 2 + 30, (yuk + 40) * 2 + 10), (24, 24, 27))
    d = ImageDraw.Draw(sayfa)
    f = font("mono", 16)
    for i, ts in enumerate(zamanlar):
        im = Image.fromarray(_kare_kucuk(P.video, ts, gen))
        dd = ImageDraw.Draw(im)
        for duzen, renk_ in (("bol", (56, 140, 255)), ("yuz", (255, 150, 40))):
            b = kd.kirp(duzen, ts)
            dd.rectangle([b[0] * olc, b[1] * olc, b[2] * olc, b[3] * olc], outline=renk_, width=3)
        x, y, w, h = kd.kutu(ts)
        dd.rectangle([x * olc, y * olc, (x + w) * olc, (y + h) * olc], outline=(60, 230, 120), width=3)
        for k in range(1, 10):                      # cetvel: kaynak pikseli
            px = kd.SW * k / 10
            dd.line([(px * olc, 0), (px * olc, 10)], fill=(255, 255, 255), width=2)
            dd.text((px * olc + 3, 12), str(int(px)), font=f, fill=(255, 255, 255))
            py = kd.SH * k / 10
            dd.line([(0, py * olc), (10, py * olc)], fill=(255, 255, 255), width=2)
            dd.text((13, py * olc - 8), str(int(py)), font=f, fill=(255, 255, 255))
        ox, oy = 10 + (i % 2) * (gen + 10), 10 + (i // 2) * (yuk + 40)
        sayfa.paste(im, (ox, oy))
        d.text((ox, oy + yuk + 6), f"kaynak {ts:.2f} sn · yeşil yüz kutusu · mavi 'bol' · turuncu 'yuz'", font=f,
               fill=(230, 230, 230))
    yol = P.d / "kontrol" / "kadraj.jpg"
    yol.parent.mkdir(exist_ok=True)
    sayfa.save(yol, quality=88)
    print(f"kontrol resmi: {yol}  (Read ile bak: yeşil kutu yüzü sarmalı, kırpmalar başı kesmemeli)")
