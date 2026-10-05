"""x-animasyon sesi: sahne JSON'undan yumuşak whoosh + gerçekçi klavye + sakin müzik yatağı.

Tamamen numpy sentezi, dış örnek yok (telif derdi yok). Zamanlar görüntüyle AYNI hesaptan gelir
(ortak.py <-> remotion/src/x/zaman.ts): whoosh her sahne kesiminde, klavye her harfte.

    python3 ses.py <sahneler.json> --video sessiz.mp4 --cikti son.mp4            # sesi üret + videoya ekle
    python3 ses.py <sahneler.json> --oran 16x9 --wav ses.wav                     # yalnız wav

Seviye: varsayılan -26 LUFS. Konuşma genelde -14..-16 LUFS'tadır; bu yatak onun 10-12 dB
altında kalır, üstüne ses kaydı ya da konuşan kafa gelirse boğmaz. Tek başına (sessiz bir
X gönderisi gibi) kullanılacaksa `--lufs -18` ver.

  whoosh  frekansı süpürülen bant geçiren gürültü + çan zarfı: "pıssst" değil hava geçişi.
          Tepesi kesim anına oturur (tepe zarfın %45'inde).
  klavye  basış tıkı + dibe vuruş + bırakma tıkı; her tuş farklı ton (tohumlu, deterministik).
  yatak   yumuşak pad akoru (her sahnede akor değişir, son sahne başa döner) + alçak bas
          + çok hafif arp. Başta 0,3 sn açılır, sonda 1 sn kapanır.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import re
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ortak as O  # noqa: E402

SR = 48000


# ------------------------------------------------------------------ temel
def fft_filtre(x, alt=None, ust=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    if ust:
        X *= 1 / np.sqrt(1 + (f / ust) ** 4)
    if alt:
        X *= 1 / np.sqrt(1 + (alt / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(X, len(x))


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def ekle(buf, x, t0, pan=0.5, g=1.0):
    i = int(round(t0 * SR))
    if x.ndim == 1:
        x = np.stack([x * math.sqrt(1 - pan), x * math.sqrt(pan)], 1)
    if i < 0:
        x, i = x[-i:], 0
    n = min(len(x), len(buf) - i)
    if n > 0:
        buf[i:i + n] += x[:n] * g


# ------------------------------------------------------------------ whoosh (yumuşak)
def _bant(x, merkez, q):
    """Zamanla değişen biquad bant geçiren; merkez örnek başına Hz."""
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for n in range(len(x)):
        w = 2 * math.pi * merkez[n] / SR
        a = math.sin(w) / (2 * q)
        a0, a1, a2 = 1 + a, -2 * math.cos(w), 1 - a
        v = (a * x[n] - a * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1 = x1, x[n]
        y2, y1 = y1, v
        y[n] = v
    return y


def whoosh(sure=0.6, alt=380.0, ust=1900.0, tohum=7):
    """Bant alt->ust->alt süpürülür, zarf çan eğrisi (tepe %45). Merkez ~1-1,5 kHz: tıslamaz."""
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.arange(n) / n
    tepe = 0.45
    zarf = np.where(t < tepe, np.sin(0.5 * np.pi * t / tepe) ** 2,
                    np.cos(0.5 * np.pi * (t - tepe) / (1 - tepe)) ** 1.6)
    merkez = alt + (ust - alt) * np.sin(np.pi * np.clip(t / 0.9, 0, 1)) ** 1.5
    v = _bant(_bant(rng.standard_normal(n), merkez, 1.1), merkez, 1.1) * 0.6 \
        + _bant(_bant(rng.standard_normal(n), merkez * 0.5, 0.8), merkez * 0.5, 0.8) * 0.4
    v = fft_filtre(v, ust=3200) * zarf
    v = v / max(np.abs(v).max(), 1e-9) * 0.5
    pan = 0.38 + 0.24 * t                      # soldan sağa hafif geçer
    return np.stack([v * np.sqrt(1 - pan), v * np.sqrt(pan)], 1)


# ------------------------------------------------------------------ klavye
def _gurultu_bant(rng, n, alt, ust):
    x = rng.standard_normal(n)
    f = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / SR)
    f[(fr < alt) | (fr > ust)] = 0
    return np.fft.irfft(f, n)


def tus(rng, bosluk=False):
    """Tek dizüstü klavye tuşu. Boşluk tuşu daha tok."""
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    v = np.zeros(n)
    k = int(0.004 * SR)
    v[:k] += _gurultu_bant(rng, k, 2000, 6000) * np.exp(-np.arange(k) / SR / 0.0012) * 0.5
    f0 = rng.uniform(170, 240) if bosluk else rng.uniform(300, 560)
    v += np.sin(2 * np.pi * f0 * t) * np.exp(-t / (0.026 if bosluk else 0.018)) * 0.55 * (t > 0.002)
    v += _gurultu_bant(rng, n, 500, 2500) * np.exp(-t / 0.01) * 0.25
    r = int(rng.uniform(0.06, 0.09) * SR)
    kr = int(0.003 * SR)
    if r + kr < n:
        v[r:r + kr] += _gurultu_bant(rng, kr, 2500, 7000) * np.exp(-np.arange(kr) / SR / 0.001) * 0.3
    return fft_filtre(v, ust=6000) * rng.uniform(0.7, 1.0) * 0.5


# ------------------------------------------------------------------ müzik yatağı
AKORLAR = [  # (pad notaları, bas) — La minör: Am F C G; sakin, editoryal
    ([57, 60, 64], 45),
    ([53, 57, 60], 41),
    ([52, 55, 60], 48),
    ([55, 59, 62], 43),
]


def pad(notalar, sure, atak=0.5, birak=0.6, kesim=1100, tohum=0):
    rng = np.random.default_rng(100 + tohum)
    n = int(sure * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for m in notalar:
        for k, det in enumerate((-0.07, 0.0, 0.07)):
            faz = np.cumsum(np.full(n, hz(m) * 2 ** (det / 12))) / SR + rng.random()
            v = 2 * (faz % 1) - 1
            p = (k + 0.5) / 3
            out[:, 0] += v * math.sqrt(1 - p)
            out[:, 1] += v * math.sqrt(p)
    for c in range(2):
        out[:, c] = fft_filtre(out[:, c], alt=110, ust=kesim)
    env = np.minimum(1, t / atak) * np.clip((sure - t) / birak, 0, 1)
    return out * env[:, None] / (len(notalar) * 3)


def bas(m, sure):
    n = int(sure * SR)
    t = np.arange(n) / SR
    v = np.sin(2 * np.pi * hz(m) * t) + 0.15 * np.sin(4 * np.pi * hz(m) * t)
    return v * np.minimum(1, t / 0.08) * np.clip((sure - t) / 0.4, 0, 1) * 0.6


def pluk(m, sure=0.7):
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = hz(m)
    v = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) * np.exp(-t / 0.08) + 0.1 * np.sin(6 * np.pi * f * t)
    return v * np.exp(-t / 0.22) * np.minimum(1, t / 0.004) * 0.5


def yatak(z: list[dict], toplam: float, bpm: float) -> np.ndarray:
    buf = np.zeros((int(math.ceil(toplam * SR)) + 1, 2))
    son = len(z) - 1
    for x in z:
        notalar, b = AKORLAR[0] if x["i"] == son and son > 0 else AKORLAR[x["i"] % len(AKORLAR)]
        t0, t1 = x["bas_sn"], x["bit_sn"]
        uz = (t1 - t0) + 0.5                      # sonrakiyle 0,5 sn üst üste: akor geçişi yumuşak
        ekle(buf, pad(notalar, uz, atak=0.6 if x["i"] == 0 else 0.4, tohum=x["i"]), t0, g=0.9)
        ekle(buf, bas(b, uz), t0, 0.5, 0.15)
        sekiz = 60 / bpm / 2
        arp = [notalar[0] + 12, notalar[1] + 12, notalar[2] + 12, notalar[1] + 12]
        k, t = 0, t0 + 0.05
        while t < t1 - 0.05:
            ekle(buf, pluk(arp[k % 4]), t, 0.3 + 0.4 * (k % 2), 0.10 if k % 4 == 0 else 0.065)
            k += 1
            t += sekiz
    n = len(buf)
    zarf = np.ones(n)
    a = int(0.3 * SR)
    zarf[:a] = np.linspace(0, 1, a)
    c = int(1.0 * SR)
    bit = int(toplam * SR)
    zarf[max(0, bit - c):bit] = np.linspace(1, 0, min(c, bit))
    zarf[bit:] = 0
    return buf * zarf[:, None]


def efektler(z: list[dict], toplam: float) -> tuple[np.ndarray, int, int]:
    buf = np.zeros((int(math.ceil(toplam * SR)) + 1, 2))
    kesim = 0
    for x in z[1:]:
        sure = 0.6
        w = whoosh(sure, tohum=11 + x["i"])
        ekle(buf, w, x["bas_sn"] - 0.45 * sure, g=1.0)
        kesim += 1
    harf = 0
    rng = np.random.default_rng(23)
    for x in z:
        s = x["sahne"]
        if s["tur"] != "yazi":
            continue
        metin = list(s["metin"])
        for ch, t in zip(metin, O.yazma_zamanlari(s["metin"], float(s["sure"]))):
            ekle(buf, tus(rng, ch == " "), x["bas_sn"] + t, 0.45 + 0.1 * rng.random(), 1.3)
            harf += 1
    return buf, kesim, harf


# ------------------------------------------------------------------ seviye + çıktı
def _wav(x, yol):
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def ebur128(yol) -> dict:
    """ffmpeg ebur128: entegre ses yüksekliği (LUFS), LRA ve gerçek tepe (dBTP)."""
    r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(yol), "-vn", "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True)
    ozet = r.stderr[r.stderr.rfind("Summary:"):]

    def bul(desen):
        m = re.search(desen, ozet)
        return float(m.group(1)) if m else float("nan")

    return {"I": bul(r"I:\s+(-?[\d.]+) LUFS"), "LRA": bul(r"LRA:\s+(-?[\d.]+) LU"),
            "TP": bul(r"Peak:\s+(-?[\d.]+) dBFS")}


def uret(js: dict, fps: int, wav_yol, lufs=-26.0, bpm=92.0, muzik=True, sure=None) -> dict:
    z = O.zamanla(js["sahneler"], fps)
    toplam = sure if sure else O.toplam_sn(js["sahneler"], fps)
    ef, kesim, harf = efektler(z, toplam)
    # Denge ölçülerek kuruldu: whoosh kesim penceresinde yatağın ~8 dB, tuşlar ~4 dB üstünde.
    mix = ef * 2.2
    if muzik:
        mix += yatak(z, toplam, bpm) * 0.45
    n = int(round(toplam * SR))
    mix = mix[:n]
    if len(mix) < n:
        mix = np.vstack([mix, np.zeros((n - len(mix), 2))])
    mix = mix / max(np.abs(mix).max(), 1e-9) * 0.5
    with tempfile.TemporaryDirectory() as td:
        ham = pathlib.Path(td) / "ham.wav"
        _wav(mix, ham)
        olcum = ebur128(ham)
    kazanc = lufs - olcum["I"]
    mix = mix * 10 ** (kazanc / 20)
    tepe = np.abs(mix).max()
    if tepe > 0.89:                                      # ~ -1 dBFS üstü: yumuşak sınırla
        mix = np.tanh(mix / 0.89) * 0.89
    _wav(mix, wav_yol)
    son = ebur128(wav_yol)
    return {"sure": n / SR, "kesim": kesim, "harf": harf, **son}


def mux(video, wav, cikti):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(cikti)],
                   check=True)


def main():
    ap = argparse.ArgumentParser(description="x-animasyon sesi: whoosh + klavye + müzik yatağı")
    ap.add_argument("json")
    ap.add_argument("--video", help="Remotion'dan çıkan sessiz mp4 (fps ve süre buradan okunur)")
    ap.add_argument("--cikti", help="sesli mp4 yolu (--video ile)")
    ap.add_argument("--wav", help="wav'ı buraya da yaz")
    ap.add_argument("--oran", choices=list(O.ORANLAR), help="--video yoksa fps için")
    ap.add_argument("--lufs", type=float, default=-26.0, help="entegre seviye (varsayılan -26: konuşmanın altında)")
    ap.add_argument("--bpm", type=float, default=92.0)
    ap.add_argument("--muziksiz", action="store_true", help="yalnız whoosh + klavye")
    a = ap.parse_args()
    js = O.oku(a.json)
    if a.video:
        vb = O.video_bilgi(a.video)
        fps = int(round(vb["fps"]))
        beklenen = O.toplam_sn(js["sahneler"], fps)
        if abs(vb["v_sure"] - beklenen) > 1.5 / fps:
            print(f"UYARI: video {vb['v_sure']:.3f} sn, JSON {beklenen:.3f} sn — JSON render'dan sonra değişmiş olabilir")
        sure = vb["v_sure"] or beklenen
    elif a.oran:
        fps, sure = O.ORANLAR[a.oran][1], None
    else:
        ap.error("--video ya da --oran gerekli")
    wav = pathlib.Path(a.wav) if a.wav else pathlib.Path(tempfile.mkdtemp()) / "ses.wav"
    r = uret(js, fps, wav, a.lufs, a.bpm, not a.muziksiz, sure)
    print(f"ses: {r['sure']:.2f} sn · {r['kesim']} whoosh · {r['harf']} tuş · "
          f"{r['I']:.1f} LUFS · tepe {r['TP']:.1f} dBTP · LRA {r['LRA']:.1f}")
    if a.video and a.cikti:
        mux(a.video, wav, a.cikti)
        print("yazıldı:", a.cikti)


if __name__ == "__main__":
    main()
