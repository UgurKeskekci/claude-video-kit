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
  klavye  dizüstü (MacBook tipi) tuş: tık + plastik gövde + yumuşak dip + sessiz bırakma tıkı,
          yalnız gürültüden (saf ton yok); tuştan tuşa ±%15-18 renk, ±3 dB (tohumlu, deterministik).
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
# Dizüstü (MacBook tipi makas) klavye, yakın ama sert olmayan kayıt gibi. SAF TON YOK: eski tuşun
# 170-560 Hz sönümlü sinüsü enerjinin ~%75'ini tek 1/6 oktavda topluyordu ("bip", yapay). Şimdi
# her parça zarflanmış gürültü + geniş spektral şekil:
#   tık      ~1-3 ms, 1,5 kHz üstü geniş bant (tuşa ilk temas)
#   gövde    400-2500 Hz bant gürültü, tuştan tuşa kayan geniş tepe, ~15-25 ms'de söner (plastik)
#   dip      300 Hz altı yumuşak vuruş, ~25-35 ms (tuş dibe oturur)
#   bırakma  50-110 ms sonra 10-14 dB daha sessiz tık + kısa gövde (tuş geri kalkar)
#   oda      2,5 ms sonra başlayan çok kısa dağınık yansıma, -18 dB (tuşa göre değişir: sabit renk yok)
# Tuştan tuşa perde/EQ ±%15-18, seviye ±3 dB. Boşluk/Enter daha tok, ~2 dB yüksek, sabitleyici
# teli yüzünden küçük ikinci vuruşu var.
_TUS_ON = int(0.004 * SR)      # sıfır fazlı süzgecin ön çınlaması bu boşluğa düşer, sonra atılır


def _hp(f, fc, k=2):
    return 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * k))


def _lp(f, fc, k=2):
    return 1 / np.sqrt(1 + (f / fc) ** (2 * k))


def _tepe(f, fc, db, oktav):
    """Log-frekansta çan biçimli GENİŞ tepe: tek frekansa kilitlenmez, ton üretmez."""
    return 10 ** (db / 20 * np.exp(-0.5 * (np.log2(np.maximum(f, 1.0) / fc) / oktav) ** 2))


def _renk(x, kazanc):
    """Sıfır fazlı FFT süzgeci; kazanc(f) genlik eğrisi."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(np.fft.rfft(x) * kazanc(f), len(x))


def _zarf(n, bas, atak, sonum, son=None):
    """bas'tan başlar: yükseltilmiş kosinüs atak + üstel sönüm (son verilirse ondan sonra sıfır)."""
    t = np.arange(n) / SR - bas
    a = np.clip(t / atak, 0, 1)
    z = np.where(t < 0, 0.0, (0.5 - 0.5 * np.cos(np.pi * a)) * np.exp(-np.maximum(t - atak, 0) / sonum))
    if son is not None:
        z[t > son] = 0
    return z


def _birim(x):
    return x / max(float(np.sqrt((x ** 2).sum())), 1e-12)


def _vurus(rng, n, bas, s, fc, fc2, sonum, tik_db):
    """Tık + plastik gövde; parçalar enerjiye göre dengelenir."""
    tik = rng.standard_normal(n) * _zarf(n, bas, 0.00025, 0.0009, son=0.003)
    tik = _renk(tik, lambda f: _hp(f, 1500 * s) * _lp(f, 7000) * _tepe(f, 3500 * s, 2, 0.5))
    gov = rng.standard_normal(n) * _zarf(n, bas + 0.0003, 0.0006, sonum)
    gov = _renk(gov, lambda f: _hp(f, 400 * s) * _lp(f, 2500 * s) * _tepe(f, fc, 7, 0.35) * _tepe(f, fc2, 4, 0.3))
    return _birim(gov) + _birim(tik) * 10 ** (tik_db / 20)


def tus(rng, bosluk=False):
    """Tek dizüstü klavye tuşu (MacBook tipi). Boşluk/Enter (bosluk=True) daha tok, biraz yüksek.
    Yalnız gürültü temelli; aynı rng durumu -> aynı ses (render deterministik)."""
    s0 = rng.uniform(0.84, 1.18)                   # perde/EQ ölçeği, tuştan tuşa
    seviye = 10 ** (rng.uniform(-3, 3) / 20)
    fc = rng.uniform(1000, 1700) * s0              # gövdenin geniş tepesi
    fc2 = fc * rng.uniform(1.9, 2.5)
    sonum = rng.uniform(0.004, 0.007)
    dip_gec = rng.uniform(0.0015, 0.004)
    dip_sonum = rng.uniform(0.007, 0.011)
    birak = rng.uniform(0.05, 0.11)
    birak_db = rng.uniform(-14, -10)
    s = s0
    if bosluk:
        s, fc, fc2 = s0 * 0.62, fc * 0.6, fc2 * 0.6
        sonum *= 1.7
        dip_sonum *= 1.35
        birak += 0.02
        seviye *= 10 ** (2 / 20)
    n = _TUS_ON + int(0.16 * SR)
    b = _TUS_ON / SR
    v = _vurus(rng, n, b, s, fc, fc2, sonum, -6)
    dip = rng.standard_normal(n) * _zarf(n, b + dip_gec, 0.002, dip_sonum)
    dip = _renk(dip, lambda f: _lp(f, (180 if bosluk else 230) * s0) * _hp(f, 90))
    v += _birim(dip) * 10 ** ((-2 if bosluk else -5) / 20)
    if bosluk:                                     # sabitleyici tel: küçük ikinci vuruş
        v += _vurus(rng, n, b + rng.uniform(0.007, 0.013), s * 1.1, fc * 1.15, fc2 * 1.1, sonum * 0.7, -8) \
            * 10 ** (-9 / 20)
    v += _vurus(rng, n, b + birak, s * 1.1, fc * 1.12, fc2 * 1.05, 0.0025, -3) * 10 ** (birak_db / 20)
    k = int(0.035 * SR)                            # oda: kısa dağınık yansıma
    t = np.arange(k) / SR
    ir = _birim(_renk(rng.standard_normal(k) * np.exp(-t / 0.007) * (t > 0.0025),
                      lambda f: _lp(f, 4500) * _hp(f, 250)))
    m = n + k - 1
    v = v + np.fft.irfft(np.fft.rfft(v, m) * np.fft.rfft(ir, m), m)[:n] * 10 ** (-18 / 20)
    v = _renk(v, lambda f: _lp(f, 8500, 1))[_TUS_ON:]
    v[-240:] *= np.linspace(1, 0, 240)
    return v * seviye * 1.5          # 1,5: 5 sn yazma dizisi eski tuştan 2 LU sessiz (ölçüldü)


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
    # Denge ölçülerek kuruldu: whoosh kesim penceresinde yatağın ~8 dB, tuşlar ~3 dB üstünde (2026-10-05).
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
