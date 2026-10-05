"""x-animasyon araçlarının ortak parçası: sahne JSON'u, zaman çizelgesi, ffprobe.

Zaman hesabı `remotion/src/x/zaman.ts` ile BİREBİR aynı olmalı. Orada bir formül değişirse
burada da değişir; yoksa whoosh kesimden, klavye sesi harften kayar. `olc.py` bu eşleşmeyi
ölçer (kesim anında ses tepesi var mı).
"""
from __future__ import annotations

import json
import math
import pathlib
import subprocess

KOK = pathlib.Path(__file__).resolve().parents[4]          # repo kökü
REMOTION = KOK / "remotion"

# oran -> (kompozisyon kimliği, fps, genişlik, yükseklik)
ORANLAR = {
    "16x9": ("XAnimasyon16x9", 60, 1920, 1080),
    "9x16": ("XAnimasyon9x16", 30, 1080, 1920),
}

YAZ_BASLA = 0.55


def oku(yol) -> dict:
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def kare(sn: float, fps: int) -> int:
    """JS Math.round ile aynı (pozitif sayı). Python round() bankacı yuvarlaması yapar, kullanılmaz."""
    return int(math.floor(sn * fps + 0.5))


def zamanla(sahneler: list[dict], fps: int) -> list[dict]:
    """Her sahne: bas/uz (kare), bas_sn/bit_sn (saniye)."""
    out, bas = [], 0
    for i, s in enumerate(sahneler):
        uz = max(1, kare(float(s["sure"]), fps))
        out.append({"i": i, "sahne": s, "tur": s["tur"], "bas": bas, "uz": uz,
                    "bas_sn": bas / fps, "bit_sn": (bas + uz) / fps})
        bas += uz
    return out


def toplam_sn(sahneler: list[dict], fps: int) -> float:
    z = zamanla(sahneler, fps)
    return (z[-1]["bas"] + z[-1]["uz"]) / fps


def _ozet(i: int) -> float:
    return ((i + 1) * 2654435761) % 4294967296 / 4294967296


def yazma_zamanlari(metin: str, sure: float) -> list[float]:
    """zaman.ts::yazmaZamanlari ile aynı: her harfin sahne içi zamanı (sn)."""
    n = len(list(metin))
    ara = []
    for i in range(n):
        a = 0.055 + 0.06 * _ozet(i)
        if _ozet(i + 1000) < 0.07:
            a += 0.14
        ara.append(a)
    toplam = 0.0
    for i in range(1, n):
        toplam += ara[i]
    pay = max(0.3, sure - YAZ_BASLA - 0.9)
    olcek = pay / toplam if toplam > pay else 1.0
    z, t = [], YAZ_BASLA
    for i in range(n):
        if i > 0:
            t += ara[i] * olcek
        z.append(t)
    return z


def ffprobe(yol) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate,nb_frames,duration:format=duration",
                        "-of", "json", str(yol)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def video_bilgi(yol) -> dict:
    j = ffprobe(yol)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    pay, payda = (v.get("r_frame_rate") or "0/1").split("/")
    return {
        "sure": float(j["format"].get("duration", 0)),
        "fps": float(pay) / float(payda or 1),
        "w": v.get("width"), "h": v.get("height"),
        "kare": int(v["nb_frames"]) if v.get("nb_frames", "N/A") != "N/A" else None,
        "v_sure": float(v.get("duration", 0) or 0),
        "a_sure": float(a.get("duration", 0) or 0) if a else None,
    }
