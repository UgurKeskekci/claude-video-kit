"""Telifsiz ses sentezi — numpy, dış örnek yok. Animasyonla AYNI zaman programından beslenir.

Yayınlanmış işlerde kullanılan sentezin genelleştirilmiş hâli; örnek `ornekler/animasyon-bir-hafta/ses.py`.
Perde ve tını ölçülerek düzeltildi (bkz. references/tarifler.md "Ses"):
- Karplus-Strong teli ÜÇGEN çekilir (beyaz gürültüyle 2.-5. harmonik temelden güçlü çıkıyordu),
  başlangıç DC'si sıfırlanır, etkin gecikme N-0.5 örnek (yoksa tizde +32 cent).
- whoosh YUMUŞAK: frekansı süpürülen bant + çan zarfı. Eski geniş bant "pıssst" whoosh'u
  sert ve tıslı bulundu, kaldırıldı.
- Klavye: tek tek tuş sesi (tık + plastik gövde + dip + bırakma, SAF TON YOK), insan ritminde; eşit aralıklı
  "tırrrt" tik dizisi yazma sesi yerine kullanılmaz.

    import sys; sys.path.insert(0, ".claude/skills/animasyon/kit")
    import sentez as Z
    buf = Z.bos(sure)
    Z.ekle(buf, Z.harp(62), 1.25, pan=0.4)
    Z.yaz_wav(Z.yanki(buf), "ses.wav", lufs=-15)
"""
from __future__ import annotations

import math
import pathlib
import subprocess
import wave

import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def bos(sure):
    return np.zeros((int(sure * SR), 2))


def fft_filtre(x, alt=None, ust=None):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    if ust:
        X *= 1 / np.sqrt(1 + (f / ust) ** 4)
    if alt:
        X *= 1 / np.sqrt(1 + (alt / np.maximum(f, 1e-3)) ** 4)
    return np.fft.irfft(X, len(x))


def ekle(buf, x, t0, pan=0.5, g=1.0):
    i = int(t0 * SR)
    if i >= len(buf) or i < 0:
        return
    n = min(len(x), len(buf) - i)
    if x.ndim == 2:
        buf[i:i + n] += x[:n] * g
        return
    buf[i:i + n, 0] += x[:n] * np.sqrt(1 - pan) * g
    buf[i:i + n, 1] += x[:n] * np.sqrt(pan) * g


# ------------------------------------------------------------------ enstrümanlar
def harp(m, sure=2.4, parlak=0.5):
    """Telli (arp, pizzicato, marimba yerine de iş görür). Karplus-Strong."""
    f = hz(m)
    N = max(2, int(SR / f))
    n = int(sure * SR)
    x = np.arange(N) / N
    buf = np.where(x < 0.28, x / 0.28, (1 - x) / 0.72) + parlak * 0.25 * rng.uniform(-1, 1, N)
    buf -= buf.mean()
    out = np.zeros(n + N)
    kayip = np.exp(-(N / SR) / (1.4 * (220 / f) ** 0.35))
    i = 0
    while i < n:
        out[i:i + N] = buf
        buf = kayip * 0.5 * (buf + np.roll(buf, -1))
        i += N
    out = out[:n]
    oran = f / (SR / (N - 0.5))
    t = np.arange(int(n / oran) - 1) * oran
    out = np.interp(t, np.arange(n), out)
    out *= np.minimum(1, np.arange(len(out)) / (0.003 * SR))
    return fft_filtre(out, ust=4200) * 0.5


def yayli(notalar, sure, atak=0.8, birak=1.2, kesim=1700):
    """Yaylı/pad: 5 detune testere + vibrato, stereo yayılım. (n, 2) döner."""
    n = int(sure * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.0016 * np.sin(2 * np.pi * 5.3 * t + rng.random() * 6)
    out = np.zeros((n, 2))
    for m in notalar:
        for k, det in enumerate((-0.12, -0.05, 0.0, 0.06, 0.13)):
            faz = np.cumsum(hz(m) * 2 ** (det / 12) * vib) / SR + rng.random()
            v = 2 * (faz % 1) - 1
            p = (k + 0.5) / 5
            out[:, 0] += v * np.sqrt(1 - p)
            out[:, 1] += v * np.sqrt(p)
    for c in range(2):
        out[:, c] = fft_filtre(out[:, c], alt=90, ust=kesim)
    env = np.minimum(1, t / atak) * np.clip((sure - t) / birak, 0, 1)
    return out * env[:, None] / (len(notalar) * 5) * 1.6


def bas(m, sure):
    n = int(sure * SR)
    t = np.arange(n) / SR
    faz = np.cumsum(hz(m) * (1 + 0.002 * np.sin(2 * np.pi * 4.8 * t))) / SR
    v = 2 * (faz % 1) - 1 + 0.5 * (2 * ((faz * 0.5) % 1) - 1)
    return fft_filtre(v, alt=35, ust=520) * np.minimum(1, t / 0.35) * np.clip((sure - t) / 0.6, 0, 1) * 0.5


def flut(m, sure):
    n = int(sure * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * t) * np.clip((t - 0.35) / 0.4, 0, 1)
    faz = 2 * np.pi * np.cumsum(hz(m) * vib) / SR
    v = np.sin(faz) + 0.22 * np.sin(2 * faz) + 0.07 * np.sin(3 * faz)
    nefes = fft_filtre(rng.standard_normal(n), alt=hz(m) * 0.8, ust=hz(m) * 2.5) * 0.05
    return (v + nefes) * np.minimum(1, t / 0.12) * np.clip((sure - t) / 0.3, 0, 1) * 0.35


def taiko(guc=1.0, derin=1.0):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    f = 42 * derin + 45 * np.exp(-t / 0.06)
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.35 * derin))
    v += fft_filtre(rng.standard_normal(n), ust=260) * np.exp(-t / 0.05) * 0.6
    return np.tanh(v * 1.3) * guc * 0.9


# ------------------------------------------------------------------ efektler (UI / komedi)
def ding(g=1.0):
    """Bildirim sesi."""
    k = int(0.5 * SR); t = np.arange(k) / SR
    v = (np.sin(2 * np.pi * 1568 * t) * np.exp(-t / 0.16) + 0.6 * np.sin(2 * np.pi * 2349 * t) * np.exp(-t / 0.1)
         + 0.2 * np.sin(2 * np.pi * 3136 * t) * np.exp(-t / 0.05))
    return v * np.minimum(1, t / 0.002) * 0.3 * g


def tik():
    """Tahta tik: sahne/gün geçişi."""
    k = int(0.08 * SR); t = np.arange(k) / SR
    v = np.sin(2 * np.pi * 950 * t) * np.exp(-t / 0.012)
    v += fft_filtre(rng.standard_normal(k), alt=1500, ust=5000) * np.exp(-t / 0.006) * 0.4
    return v * 0.5


def hisirti():
    """Kâğıt: kart düşmesi, sayfa."""
    k = int(0.09 * SR); t = np.arange(k) / SR
    return fft_filtre(rng.standard_normal(k), alt=1200, ust=6500) * np.exp(-t / 0.025) * 0.12


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
    """Yumuşak hava geçişi: bant alt->ust->alt süpürülür, zarf çan eğrisi (tepe %45'te).
    Tepeyi kesime oturtmak için `ekle(buf, whoosh(s), kesim - 0.45 * s)`.
    İki kademe bant + 3,2 kHz üstü kesim: tek kademede tıslıyordu, hedef merkez ~1-1,5 kHz."""
    r = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.arange(n) / n
    tepe = 0.45
    zarf = np.where(t < tepe, np.sin(0.5 * np.pi * t / tepe) ** 2, np.cos(0.5 * np.pi * (t - tepe) / (1 - tepe)) ** 1.6)
    merkez = alt + (ust - alt) * np.sin(np.pi * np.clip(t / 0.9, 0, 1)) ** 1.5
    v = _bant(_bant(r.standard_normal(n), merkez, 1.1), merkez, 1.1) * 0.6 \
        + _bant(_bant(r.standard_normal(n), merkez * 0.5, 0.8), merkez * 0.5, 0.8) * 0.4
    v = fft_filtre(v, ust=3200) * zarf
    return v / max(np.abs(v).max(), 1e-9) * 0.5


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


def tus(r=None, bosluk=False):
    """Tek dizüstü klavye tuşu (MacBook tipi). Boşluk/Enter (bosluk=True) daha tok, biraz yüksek.
    Yalnız gürültü temelli; aynı rng durumu -> aynı ses (render deterministik). r yoksa modülün rng'si."""
    rng = r or globals()["rng"]
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


def yazma(t0, sure, tohum=1):
    """[t0, t0+sure] boyunca insan ritminde tuş zamanları: 70-140 ms, ara sıra kısa duraksama."""
    r = np.random.default_rng(tohum)
    zaman, t = [], t0
    while t < t0 + sure:
        zaman.append(t)
        t += r.uniform(0.07, 0.14) + (r.uniform(0.08, 0.2) if r.random() < 0.1 else 0)
    return zaman


def swell(sure, alt=3500):
    """Ters zil — büyük anın ÖNCESİ."""
    n = int(sure * SR); t = np.arange(n) / SR
    return fft_filtre(rng.standard_normal(n), alt=alt, ust=11000) * (t / sure) ** 2.5 * 0.12


# ------------------------------------------------------------------ miks + çıktı
def yanki(x, sure=3.4, oran=0.4):
    n = int(sure * SR)
    t = np.arange(n) / SR
    out = x.copy()
    for c in range(2):
        ir = fft_filtre(rng.standard_normal(n) * np.exp(-t / (sure / 6.5)), ust=5500)
        ir[: int(0.03 * SR)] *= np.linspace(0, 1, int(0.03 * SR))
        ir /= np.sqrt((ir ** 2).sum())
        N2 = 1 << (len(x) + n - 1).bit_length()
        out[:, c] = x[:, c] + oran * np.fft.irfft(np.fft.rfft(x[:, c], N2) * np.fft.rfft(ir, N2), N2)[: len(x)]
    return out


def kes(buf, t, sonum=0.015):
    """t'den sonra her şeyi sustur (komedi sessizliği için keskin kesim).
    Yankıyı ÖNCE uygula: kes() sonra yanki() kuyruğu sessizliğe taşır (bkz. tarifler.md "Ses")."""
    i, s = int(t * SR), int(sonum * SR)
    buf[i:i + s] *= np.linspace(1, 0, min(s, len(buf) - i))[:, None]
    buf[i + s:] = 0


def _wav16(x, yol):
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def lufs_olc(yol) -> float:
    """ffmpeg ebur128 ile entegre ses yüksekliği (LUFS)."""
    import re
    r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(yol), "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", r.stderr[r.stderr.rfind("Summary:"):])
    return float(m.group(1)) if m else float("nan")


def yaz_wav(buf, yol, lufs=-15.0):
    """Yumuşak doyum + DOĞRUSAL kazançla hedef LUFS. ffmpeg loudnorm'un tek geçişli (dinamik)
    kipi kısa kliplerde hedefi tutturmuyordu (ölçüldü: hedef -15, çıkan -13,8) ve sessizlik
    sonrası seviyeyi pompalayabiliyor; burada ölç -> tek kazanç -> gerekirse yumuşak sınır."""
    x = np.tanh(buf * 1.1) / 1.1
    x /= max(np.abs(x).max(), 1e-9) / 0.9
    ham = pathlib.Path(yol).with_suffix(".ham.wav")
    _wav16(x, ham)
    olcum = lufs_olc(ham)
    ham.unlink()
    if olcum == olcum:                      # NaN değilse
        x = x * 10 ** ((lufs - olcum) / 20)
    if np.abs(x).max() > 0.89:              # ~ -1 dBFS üstü: yumuşak sınırla
        x = np.tanh(x / 0.89) * 0.89
    _wav16(x, yol)
    return yol
