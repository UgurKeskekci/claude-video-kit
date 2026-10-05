"""İki kaydı (sesi iyi olan ana kayıt ↔ ekran kaydının kendi mikrofonu) sesten eşler.

Yöntem: 200 Hz'lik log ses zarfı, 1 sn'lik hareketli ortalaması çıkarılmış (yalnız konuşmanın
inip çıkışı kalır, mikrofon farkı silinir). Önce tüm kayıt FFT çapraz ilişkisiyle kaba ofset,
sonra pencere pencere ±1 sn içinde ince ofset; pencerelerden doğru uydurulur (saat sürüklenmesi):

    ekran_t = ana_t + ofset + kayma * ana_t

Ölçüm (25 dakikalık kamera + ekran kaydı): sürüklenme 25 dakikada 15 ms, r ≈ 0,7.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np

import kesim
import medya

HZ = 200


def zarf(x: np.ndarray, sr: int = 16000, hz: int = HZ) -> np.ndarray:
    n = sr // hz
    x = x[: len(x) // n * n].reshape(-1, n).astype(np.float64)
    e = np.log1p(np.sqrt((x ** 2).mean(1)) * 32768)
    return e - np.convolve(e, np.ones(hz) / hz, "same")


def kaba_ofset(A: np.ndarray, E: np.ndarray, hz: int = HZ) -> float:
    """c[L] = Σ E[n+L]·A[n] en büyük olduğu L: ekran_t = ana_t + L/hz."""
    n = 1 << int(np.ceil(np.log2(len(A) + len(E))))
    c = np.fft.irfft(np.fft.rfft(E, n) * np.conj(np.fft.rfft(A, n)), n)
    lag = int(np.argmax(c))
    return (lag if lag < n // 2 else lag - n) / hz


def ince(A: np.ndarray, E: np.ndarray, t: float, uzun: float, merkez: float, ara: float = 1.0,
         hz: int = HZ) -> tuple[float, float]:
    """A'nın [t, t+uzun] penceresi için merkez ± ara içindeki en iyi ofset (parabolik ara değerle)."""
    a = A[int(t * hz): int((t + uzun) * hz)]
    if len(a) < hz * 3 or a.std() < 1e-6:
        return merkez, 0.0
    L0, L1 = int((merkez - ara) * hz), int((merkez + ara) * hz)
    rr = []
    for L in range(L0, L1 + 1):
        s = int(t * hz) + L
        if s < 0 or s + len(a) > len(E):
            rr.append(-1.0)
            continue
        b = E[s: s + len(a)]
        rr.append(float(np.corrcoef(a, b)[0, 1]) if b.std() > 1e-6 else -1.0)
    rr = np.array(rr)
    k = int(np.argmax(rr))
    d = 0.0
    if 0 < k < len(rr) - 1:
        y0, y1, y2 = rr[k - 1], rr[k], rr[k + 1]
        payda = y0 - 2 * y1 + y2
        if abs(payda) > 1e-12:
            d = 0.5 * (y0 - y2) / payda
    return (L0 + k + d) / hz, float(rr[k])


def calistir(proje: pathlib.Path, ekran: str | None, elle: float | None) -> int:
    k = proje / "kaynak.json"
    if not k.exists():
        raise SystemExit(f"{k} yok. Önce: kurgu.py dokum {proje} --video <dosya>")
    kaynak = json.loads(k.read_text("utf-8"))
    if ekran:
        e = pathlib.Path(ekran).expanduser().resolve()
        if not e.exists():
            raise SystemExit(f"ekran kaydı yok: {e}")
        kaynak["ekran"], kaynak["ekran_bilgi"] = str(e), medya.bilgi(e)
        k.write_text(json.dumps(kaynak, ensure_ascii=False, indent=1), "utf-8")
    if not kaynak.get("ekran"):
        raise SystemExit("ekran kaydı verilmemiş: kurgu.py senkron <proje> --ekran <dosya>")
    if elle is not None:
        sonuc = {"ekran": kaynak["ekran"], "ofset": elle, "kayma": 0.0, "yontem": "elle", "pencereler": []}
        (proje / "senkron.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), "utf-8")
        print(f"ekran_t = ana_t + {elle:.3f} (elle) -> {proje / 'senkron.json'}")
        return 0
    if not kaynak.get("ekran_bilgi", {}).get("ses"):
        raise SystemExit("Ekran kaydında ses yok; sesten eşlenemez. Ofseti biliyorsan: senkron --ofset <sn>")
    s16, _ = medya.ses_hazirla(proje, kaynak)
    e16 = proje / "ekran16k.wav"
    if not e16.exists() or e16.stat().st_mtime < pathlib.Path(kaynak["ekran"]).stat().st_mtime:
        medya.wav_cikar(kaynak["ekran"], [(e16, 16000)])
    xa, _ = medya.wav_oku(s16)
    xe, _ = medya.wav_oku(e16)
    A, E = zarf(xa), zarf(xe)
    kaba = kaba_ofset(A, E)
    sure = len(A) / HZ
    uzun = 30.0 if sure >= 120 else max(5.0, sure / 3)
    adim = max(uzun, sure / 12)
    pencere = []
    t = 0.0
    while t + uzun <= sure:
        o, r = ince(A, E, t, uzun, kaba)
        pencere.append((round(t + uzun / 2, 2), round(o, 4), round(r, 3)))
        t += adim
    a, b, kullanilan = kesim.dogru_uydur(pencere)
    if not kullanilan:
        a, b = kaba, 0.0
        print("UYARI: hiçbir pencerede güvenilir eşleşme yok (r < 0,3); kaba ofset kullanıldı. "
              "Kayıtlar aynı anı mı içeriyor? Ekran kaydında mikrofon açık mıydı?")
    rler = sorted(r for _, _, r in pencere)
    r_med = rler[len(rler) // 2] if rler else 0.0
    sonuc = {"ekran": kaynak["ekran"], "ofset": round(a, 4), "kayma": round(b, 9), "kaba_ofset": round(kaba, 3),
             "r_medyan": round(r_med, 3), "yontem": "ses zarfı çapraz ilişki",
             "pencereler": [{"t": t_, "ofset": o, "r": r} for t_, o, r in pencere],
             "kullanilan": len(kullanilan)}
    (proje / "senkron.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), "utf-8")
    for t_, o, r in pencere:
        print(f"  ana {t_:7.1f} sn  ofset {o:+.3f}  r={r:.2f}")
    print(f"ekran_t = ana_t + {a:.3f} + {b:.7f}·ana_t   (kaba {kaba:.3f}, r medyan {r_med:.2f}, "
          f"{len(kullanilan)}/{len(pencere)} pencere; {sure / 60:.0f} dakikada {abs(b) * sure * 1000:.0f} ms kayma)"
          f" -> {proje / 'senkron.json'}")
    return 0
