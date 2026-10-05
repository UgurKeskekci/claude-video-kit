"""Reels sesi: kesik konuşma (yatay-kurgu ile aynı örnek ızgarası) + efekt izi, ölçerek dengelenir.

- Konuşma: plan parçaları ÖRNEK ÖRNEK birleştirilir (kare x 1600 örnek, uçlarda 10 ms yumuşatma),
  80 Hz altı kesilir, hafif kompresör, sonra ölçülüp HEDEF_LUFS'a (-14) getirilir.
- Efektler: kart değişiminde yumuşak whoosh (tepesi kesim anında), terminal/sohbet yazılırken
  insan ritminde klavye, madde girerken kısa yumuşak "pop". Whoosh ve klavye x-animasyon skill'inin
  sentezinden gelir (numpy, dış örnek yok). Efekt izi ölçülür ve konuşmanın EFEKT_FARK dB altına konur.
- Son: yumuşak sınırlayıcı (tepe ~ -1 dBFS), stereo 48 kHz wav.
"""
from __future__ import annotations

import importlib.util
import math
import pathlib
import subprocess
import sys
import wave

import numpy as np

import kartlar
from cizim import KOK

SR = 48000
HEDEF_LUFS = -14.0
EFEKT_FARK = 15.0          # efekt izi (yalnız sesli anları, kapılı) konuşmanın en az bu kadar altında

_XS = None


def xs():
    """x-animasyon/araclar/ses.py'yi dosya yolundan yükler (whoosh, tus, ekle, ebur128).
    sys.path'e eklediği klasörü geri alır: oradaki olc.py/ortak.py adları bizimkilerle karışmasın."""
    global _XS
    if _XS is None:
        yol = KOK / ".claude" / "skills" / "x-animasyon" / "araclar" / "ses.py"
        if not yol.exists():
            raise SystemExit(f"{yol} yok: reels efekt sesleri için x-animasyon skill'inin sentezini kullanır.")
        eski = list(sys.path)
        sp = importlib.util.spec_from_file_location("xanim_ses", yol)
        m = importlib.util.module_from_spec(sp)
        try:
            sp.loader.exec_module(m)
        finally:
            sys.path[:] = eski
        _XS = m
    return _XS


def wav_oku(yol) -> np.ndarray:
    with wave.open(str(yol)) as w:
        n, ch, sr = w.getnframes(), w.getnchannels(), w.getframerate()
        x = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32768
    if sr != SR:
        raise SystemExit(f"{yol}: {sr} Hz, {SR} bekleniyordu")
    return x.reshape(-1, ch).mean(axis=1) if ch > 1 else x


def wav_yaz(yol, x: np.ndarray) -> None:
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


# ------------------------------------------------------------------ konuşma
def kesik_konusma(P) -> np.ndarray:
    kaynak = P.d / "ses48.wav"
    if not kaynak.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(P.video), "-map", "0:a:0", "-ac", "1", "-ar", str(SR),
                        "-c:a", "pcm_s16le", str(kaynak)], check=True)
    x = wav_oku(kaynak)
    f = int(SR * 0.01)
    rampa = np.linspace(0, 1, f, dtype=np.float32)
    out = []
    for k, p in enumerate(P.pp):
        bas, say = round(p["_ia"] * SR), P.parca_kare[k] * (SR // P.fps)
        y = x[bas:bas + say].copy()
        if len(y) < say:
            y = np.concatenate([y, np.zeros(say - len(y), np.float32)])
        if say > 2 * f:
            y[:f] *= rampa
            y[-f:] *= rampa[::-1]
        out.append(y)
    out.append(np.zeros(P.kuyruk_kare * (SR // P.fps), np.float32))
    return np.concatenate(out)


def konusma_isle(ham: pathlib.Path, cikti: pathlib.Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ham), "-af",
                    "highpass=f=80,acompressor=threshold=-24dB:ratio=2.5:attack=8:release=160:makeup=2",
                    "-ar", str(SR), "-c:a", "pcm_s16le", str(cikti)], check=True)


# ------------------------------------------------------------------ efektler
def pop(sure=0.09, tohum=0) -> np.ndarray:
    """Kısa yumuşak 'pop': 1,1 kHz'den 650 Hz'e kayan sinüs + çok kısa gürültü, üstel sönüm."""
    n = int(sure * SR)
    t = np.arange(n) / SR
    f = 650 + 450 * np.exp(-t / 0.018)
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.028) * np.minimum(1, t / 0.002)
    rng = np.random.default_rng(tohum)
    k = int(0.004 * SR)
    v[:k] += rng.standard_normal(k) * np.exp(-np.arange(k) / SR / 0.001) * 0.15
    return v * 0.45


def cizik(sure=0.28, tohum=3) -> np.ndarray:
    """Kalemle üstünü çizme: bant sınırlı gürültü, kısa çan zarfı."""
    rng = np.random.default_rng(tohum)
    n = int(sure * SR)
    t = np.arange(n) / n
    v = xs().fft_filtre(rng.standard_normal(n), alt=900, ust=4500) * np.sin(np.pi * t) ** 1.5
    return v / max(np.abs(v).max(), 1e-9) * 0.3


def olay_listesi(P) -> list[tuple[float, str]]:
    ev = []
    for n, v in enumerate(P.V):
        if n and v["_t"] > 0.05:
            ev.append((v["_t"], "whoosh"))
        k = v.get("kart")
        if k:
            for t, tur in kartlar.olaylar(k):
                if v["_t"] - 0.01 <= t < v["_bit"]:
                    ev.append((t, tur))
    return sorted(ev)


def efekt_izi(P, n: int) -> tuple[np.ndarray, dict]:
    X = xs()
    buf = np.zeros((n, 2))
    rng = np.random.default_rng(17)
    say = {"whoosh": 0, "tus": 0, "pop": 0, "cizik": 0}
    wh = {}
    for t, tur in olay_listesi(P):
        if tur == "whoosh":
            sure = 0.5
            w = wh.setdefault(say["whoosh"] % 4, X.whoosh(sure, alt=420, ust=1700, tohum=11 + say["whoosh"] % 4))
            X.ekle(buf, w, t - 0.45 * sure, g=1.0)
        elif tur == "tus":
            X.ekle(buf, X.tus(rng, rng.random() < 0.15), t, 0.45 + 0.1 * rng.random(), 0.9)
        elif tur == "pop":
            X.ekle(buf, pop(tohum=say["pop"]), t, 0.5, 0.8)
        elif tur == "cizik":
            X.ekle(buf, cizik(), t, 0.55, 0.8)
        say[tur] = say.get(tur, 0) + 1
    return buf, say


# ------------------------------------------------------------------ karışım
def karistir(P, kontrol: pathlib.Path, efekt_fark: float = EFEKT_FARK) -> dict:
    """kontrol/konusma.wav, kontrol/efekt.wav, kontrol/ses.wav yazar; ölçümleri döndürür."""
    X = xs()
    kontrol.mkdir(parents=True, exist_ok=True)
    n = P.toplam_kare * (SR // P.fps)
    ham = kesik_konusma(P)[:n]
    if len(ham) < n:
        ham = np.concatenate([ham, np.zeros(n - len(ham), np.float32)])
    wav_yaz(kontrol / "konusma-ham.wav", ham)
    konusma_isle(kontrol / "konusma-ham.wav", kontrol / "konusma-islenmis.wav")
    k = wav_oku(kontrol / "konusma-islenmis.wav")[:n]
    olc_k = X.ebur128(kontrol / "konusma-islenmis.wav")
    gk = 10 ** ((HEDEF_LUFS - olc_k["I"]) / 20)
    k = k * gk
    wav_yaz(kontrol / "konusma.wav", k)
    fx, say = efekt_izi(P, n)
    sonuc = {"konusma_ham_I": olc_k["I"], "efekt_sayisi": say}
    if np.abs(fx).max() > 1e-6:
        fx = fx / np.abs(fx).max() * 0.5
        wav_yaz(kontrol / "efekt-ham.wav", fx)
        olc_f = X.ebur128(kontrol / "efekt-ham.wav")
        gf = 10 ** ((HEDEF_LUFS - efekt_fark - olc_f["I"]) / 20)
        fx = fx * gf
        wav_yaz(kontrol / "efekt.wav", fx)
    mix = np.stack([k, k], 1) + fx
    # yumuşak sınırlayıcı: 0,76'nın üstü 0,85'e (≈ -1,4 dBFS) yumuşakça bükülür; AAC kodlaması
    # tepeyi ~0,5 dB yükseltiyor (ölçüldü: 0,89 tavanla son dosya -0,9 dBTP)
    a = np.abs(mix)
    ust = a > 0.76
    mix[ust] = np.sign(mix[ust]) * (0.76 + 0.09 * np.tanh((a[ust] - 0.76) / 0.09))
    wav_yaz(kontrol / "ses.wav", mix)
    sonuc["sinirlanan_ornek"] = int(ust.sum())
    return sonuc


def lufs(yol) -> dict:
    return xs().ebur128(yol)


def _db(x):
    return 20 * math.log10(max(x, 1e-9))
