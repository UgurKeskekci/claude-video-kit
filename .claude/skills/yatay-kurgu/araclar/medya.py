"""ffmpeg, wav ve Whisper yardımcıları (numpy + faster-whisper burada, kesim.py saf kalsın)."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import wave

import numpy as np

from kesim import SR, Enerji, dokum_parcalari, duzelt_kelimeler, kareye, ses_araligi

BURASI = pathlib.Path(__file__).resolve().parent
SOZLUK = BURASI / "sozluk.json"


# --- ffmpeg ---------------------------------------------------------------------------

def ffmpeg_kontrol() -> None:
    for p in ("ffmpeg", "ffprobe"):
        if not shutil.which(p):
            raise SystemExit(f"{p} bulunamadı. macOS: brew install ffmpeg · Windows: winget install ffmpeg")


def calistir(cmd: list[str], zaman_asimi: float | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=zaman_asimi)
    if r.returncode:
        raise RuntimeError(f"komut başarısız ({r.returncode}): {' '.join(cmd[:6])} …\n{r.stderr[-1500:]}")
    return r


def bilgi(yol: str | pathlib.Path) -> dict:
    """Süre, görüntü boyutu, fps, ses var mı."""
    r = calistir(["ffprobe", "-v", "error", "-show_entries",
                  "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", str(yol)])
    j = json.loads(r.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = any(s.get("codec_type") == "audio" for s in j.get("streams", []))
    fps = 0.0
    if v.get("r_frame_rate", "0/0") != "0/0":
        n, d = v["r_frame_rate"].split("/")
        fps = float(n) / float(d)
    return {"sure": float(j["format"]["duration"]), "w": v.get("width", 0), "h": v.get("height", 0),
            "fps": fps, "ses": a}


def wav_cikar(video: str | pathlib.Path, hedefler: list[tuple[pathlib.Path, int]]) -> None:
    """Videonun ilk ses izinden mono wav'lar (16 kHz döküm için, 48 kHz çıktı için) tek geçişte."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video)]
    for yol, sr in hedefler:
        yol.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(yol)]
    calistir(cmd)


def wav_oku(yol: str | pathlib.Path) -> tuple[np.ndarray, int]:
    with wave.open(str(yol)) as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{yol}: 16 bit PCM bekleniyordu")
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            x = x.reshape(-1, w.getnchannels()).mean(1)
        return x, w.getframerate()


def wav_yaz(yol: str | pathlib.Path, x: np.ndarray, sr: int) -> None:
    pathlib.Path(yol).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(yol), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.clip(x * 32768, -32768, 32767).astype(np.int16).tobytes())


def zarf(wav: str | pathlib.Path) -> Enerji:
    """wav -> 10 ms'lik dB zarfı (Enerji). Eşik numpy ile hesaplanır, formül kesim.Enerji ile aynı."""
    x, sr = wav_oku(wav)
    n = sr // 100
    x = x[: len(x) // n * n].reshape(-1, n)
    db = 20 * np.log10(np.sqrt((x.astype(np.float64) ** 2).mean(axis=1)) + 1e-6)
    p10, p90 = np.percentile(db, 10), np.percentile(db, 90)
    from kesim import ESIK_KONUSMA, ESIK_TABAN
    return Enerji(db.tolist(), esik=float(max(p10 + ESIK_TABAN, p90 - ESIK_KONUSMA)))


def kesik_ses(x48: np.ndarray, pp: list[dict], fps: int, fade: float = 0.01) -> np.ndarray:
    """Plan -> kesik ses, ÖRNEK ÖRNEK: her parça kare sayısı x (48000/fps) örnek, uçlarında 10 ms
    yumuşatma. Görüntüyle aynı ızgara, 200+ parçada bile kayma birikmez."""
    f = int(SR * fade)
    rampa = np.linspace(0, 1, f, dtype=np.float32)
    out = []
    for p in pp:
        bas, say = ses_araligi(p, fps)
        y = x48[bas: bas + say].copy()
        if len(y) < say:
            y = np.concatenate([y, np.zeros(say - len(y), np.float32)])
        if say > 2 * f:
            y[:f] *= rampa
            y[-f:] *= rampa[::-1]
        out.append(y)
    return np.concatenate(out) if out else np.zeros(0, np.float32)


# --- Whisper --------------------------------------------------------------------------

def sozluk_oku(yol: str | pathlib.Path | None = None) -> dict:
    p = pathlib.Path(yol) if yol else SOZLUK
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def _cuda_dll() -> None:
    """Windows: pip ile gelen nvidia cuBLAS/cuDNN DLL klasörlerini yükleme yoluna ekler."""
    if sys.platform != "win32":
        return
    eklenen = []
    for kok in (pathlib.Path(p) / "nvidia" for p in sys.path if p):
        if kok.is_dir():
            for alt in sorted(kok.iterdir()):
                b = alt / "bin"
                if b.is_dir():
                    eklenen.append(str(b))
                    try:
                        os.add_dll_directory(str(b))
                    except (OSError, AttributeError):
                        pass
    if eklenen:
        os.environ["PATH"] = os.pathsep.join(eklenen) + os.pathsep + os.environ.get("PATH", "")


def cihaz_sec(cihaz: str = "auto") -> tuple[str, str]:
    if cihaz == "cuda":
        return "cuda", "float16"
    if cihaz == "cpu":
        return "cpu", "int8"
    _cuda_dll()
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def model_yukle(model: str = "large-v3", cihaz: str = "auto"):
    d, ct = cihaz_sec(cihaz)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("faster-whisper kurulu değil: pip install -r requirements.txt")
    t0 = time.time()
    m = WhisperModel(model, device=d, compute_type=ct, cpu_threads=os.cpu_count() or 4)
    print(f"  model {model} ({d}/{ct}) {time.time() - t0:.0f} sn'de yüklendi", flush=True)
    return m


UYDURMA = ("Altyazı M.K", "Altyazı M. K", "M.K.", "Alt yazı M.K")


def harfiyen_coz(model, wav: str | pathlib.Path, dil: str = "tr", istem: str = "", duzeltmeler=(),
                 en: Enerji | None = None, etiket: str = "") -> list[dict]:
    """Takılmaları da yazan kelime dökümü: sessizliklerden <= 10 sn'lik parçalar, her biri
    BAĞIMSIZ (condition_on_previous_text=False), istemde takılma örnekleri. Sessizlikte
    uydurulan satır (sesli oranı < %15) atılır. Sözlük düzeltmeleri en sonda."""
    en = en or zarf(wav)
    x, sr = wav_oku(wav)
    if sr != 16000:
        raise ValueError(f"{wav}: 16 kHz bekleniyordu")
    parca = dokum_parcalari(en)
    toplam = sum(b - a for a, b in parca)
    out, t0, biten = [], time.time(), 0.0
    for n, (a, b) in enumerate(parca):
        segs, _ = model.transcribe(x[int(a * sr): int(b * sr)], language=dil, word_timestamps=True,
                                   condition_on_previous_text=False, beam_size=5, initial_prompt=istem or None,
                                   vad_filter=False)
        for s in segs:
            if any(u in s.text for u in UYDURMA):
                continue
            if en.sesli_oran(a + s.start, a + s.end) < 0.15:
                continue
            for w in s.words or []:
                out.append({"start": round(a + w.start, 3), "end": round(a + w.end, 3), "word": w.word,
                            "prob": round(w.probability, 3)})
        biten += b - a
        if n % 15 == 0 or n == len(parca) - 1:
            gecen = time.time() - t0
            print(f"  {etiket}{n + 1}/{len(parca)} parça · {biten:.0f}/{toplam:.0f} sn ses · {gecen:.0f} sn"
                  + (f" · kalan ~{gecen / max(biten, 1e-6) * (toplam - biten):.0f} sn" if biten else ""), flush=True)
    return duzelt_kelimeler(out, list(duzeltmeler))


def kodlayici(tercih: str, w: int, h: int) -> tuple[str, list[str], list[str]]:
    """(ad, kodlama argümanları, çözme argümanları). Sırayla dener: macOS VideoToolbox,
    NVIDIA NVENC, libx264. Listede olmak yetmez, 0,1 sn'lik deneme kodlaması yapılır."""
    piksel = (w * h) / (1920 * 1080)
    mbit = max(8, round(14 * piksel))
    adaylar = {
        "videotoolbox": ("h264_videotoolbox", ["-c:v", "h264_videotoolbox", "-b:v", f"{mbit}M", "-maxrate", f"{round(mbit * 1.3)}M",
                                               "-bufsize", f"{mbit * 2}M", "-profile:v", "high", "-pix_fmt", "yuv420p"],
                         ["-hwaccel", "videotoolbox"]),
        "nvenc": ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0",
                                 "-profile:v", "high", "-pix_fmt", "yuv420p"], []),
        "x264": ("libx264", ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
                             "-pix_fmt", "yuv420p"], []),
    }
    sira = ([tercih] if tercih != "auto" else
            (["videotoolbox", "x264"] if sys.platform == "darwin" else ["nvenc", "x264"]))
    liste = calistir(["ffmpeg", "-hide_banner", "-encoders"]).stdout
    for ad in sira:
        if ad not in adaylar:
            raise SystemExit(f"bilinmeyen kodlayıcı: {ad} (auto | videotoolbox | nvenc | x264)")
        enc, args, coz = adaylar[ad]
        if enc not in liste:
            continue
        deneme = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x144:d=0.1",
                                 *args, "-f", "null", "-"], capture_output=True)
        if deneme.returncode == 0:
            return enc, args, coz
    raise SystemExit("Çalışan bir H.264 kodlayıcı bulunamadı (libx264'lü bir ffmpeg kur).")


def ses_hazirla(proje: pathlib.Path, kaynak: dict) -> tuple[pathlib.Path, pathlib.Path]:
    """Ana videodan ses16k.wav (döküm, zarf) ve ses48.wav (çıktı) — yoksa çıkarır."""
    s16, s48 = proje / "ses16k.wav", proje / "ses48.wav"
    if not (s16.exists() and s48.exists()):
        print("  ses çıkarılıyor…", flush=True)
        wav_cikar(kaynak["video"], [(s16, 16000), (s48, SR)])
    return s16, s48


def kare_bilgisi(p: dict, fps: int) -> tuple[float, int]:
    return kareye(p["in"], p["out"], p.get("hiz", 1), fps)
