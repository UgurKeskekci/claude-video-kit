"""Bitmiş Reels'i ölçer: süre/kare, temas sayfası, güvenli alan (piksel kutularından), ses seviyesi.

İzleyemediğin videoyu ölçerek kontrol et:
  - süre: görüntü ve ses aynı uzunlukta mı, beklenen kare sayısı tutuyor mu;
  - temas sayfası (`kontrol/temas.jpg`): her vuruştan bir kare, platform arayüzü kırmızı taralı — AÇ ve BAK;
  - güvenli alan: render her 5 karede altyazının/kartın/yüzün PİKSEL kutusunu ölçtü (olcum.json);
    altyazı ve kart üst banda (y<220), alt %20'ye (y>1536), sağ sütuna (x>940, y 1000-1536) girmemeli;
  - ses: son dosyanın entegre LUFS'u ve gerçek tepesi; efekt izinin konuşmadan kaç dB aşağıda olduğu.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import numpy as np
from PIL import Image

import cizim as C
import karisim
from proje import json_oku, mmss
from render import temas_sayfasi, varsayilan_kareler


def _ffprobe(yol) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-show_entries",
                        "stream=codec_type,width,height,r_frame_rate,duration,nb_read_packets", "-of", "json", str(yol)],
                       capture_output=True, text=True, check=True)
    out = {}
    for s in json.loads(r.stdout)["streams"]:
        out[s["codec_type"]] = s
    return out


def _kare_al(video, t) -> Image.Image:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return Image.frombuffer("RGB", (C.W, C.H), r.stdout[:C.W * C.H * 3], "raw", "RGB", 0, 1)


def ihlaller(b) -> list[str]:
    if not b:
        return []
    x0, y0, x1, y1 = b
    out = []
    if y0 < C.UST_BANT:
        out.append(f"üst bant (y {y0} < {C.UST_BANT})")
    if y1 > C.ALT_BANT:
        out.append(f"alt %20 (y {y1} > {C.ALT_BANT})")
    if x1 > C.SAG_SUTUN_X and y1 > C.SAG_SUTUN_Y[0] and y0 < C.SAG_SUTUN_Y[1]:
        out.append(f"sağ sütun (x {x1} > {C.SAG_SUTUN_X})")
    if x0 < C.KENAR or x1 > C.W - C.KENAR:
        out.append(f"kenar ({x0}..{x1})")
    return out


def guvenli_alan(olcumler: list[dict]) -> tuple[list[str], int]:
    satirlar, toplam = [], 0
    for ad in ("altyazi", "kart"):
        kutular = [(o["t"], o[ad]) for o in olcumler if o.get(ad)]
        if not kutular:
            satirlar.append(f"- {ad}: ölçülen kare yok")
            continue
        bir = [min(b[0] for _, b in kutular), min(b[1] for _, b in kutular),
               max(b[2] for _, b in kutular), max(b[3] for _, b in kutular)]
        kotu = [(t, ihlaller(b)) for t, b in kutular if ihlaller(b)]
        toplam += len(kotu)
        durum = "GÜVENLİ" if not kotu else f"{len(kotu)} karede İHLAL"
        satirlar.append(f"- {ad}: {len(kutular)} kare ölçüldü, kapladığı alan x {bir[0]}–{bir[2]}, y {bir[1]}–{bir[3]} -> {durum}")
        for t, ih in kotu[:6]:
            satirlar.append(f"    {mmss(t)}: {', '.join(ih)}")
    yuzler = [(o["t"], o["duzen"], o["yuz"]) for o in olcumler if o.get("yuz")]
    for duzen in ("bol", "yuz"):
        ys = [(t, b) for t, d, b in yuzler if d == duzen]
        if not ys:
            continue
        ust = min(b[1] for _, b in ys)
        alt = max(b[3] for _, b in ys)
        sorun = []
        if alt > C.ALT_BANT:
            sorun.append(f"yüzün altı arayüzün altında kalıyor (y {alt} > {C.ALT_BANT})")
        if duzen == "bol" and ust < C.YUZ_KARTI_UST:
            sorun.append(f"yüz kartın üst kenarından taşıyor/kesiliyor (y {ust} < {C.YUZ_KARTI_UST})")
        toplam += len(sorun)
        satirlar.append(f"- yüz ({duzen}): y {ust}–{alt} -> " + ("; ".join(sorun) if sorun else "GÜVENLİ"))
    return satirlar, toplam


def whoosh_kesimde(P, efekt_wav: pathlib.Path) -> str:
    """Her kart değişiminde efekt izinin tepesi kesime oturuyor mu (20 ms RMS, kesimin -0,15/+0,10 sn'si)."""
    if not efekt_wav.exists():
        return "efekt izi yok"
    x = karisim.wav_oku(efekt_wav)
    pen = int(karisim.SR * 0.02)
    n = len(x) // pen
    rms = np.sqrt((x[:n * pen].reshape(n, pen) ** 2).mean(axis=1) + 1e-12)
    kaymalar = []
    for v in P.V[1:]:
        tc = v["_t"]
        a, b = int((tc - 0.15) / 0.02), int((tc + 0.10) / 0.02)
        if a < 0 or b >= n:
            continue
        i = a + int(np.argmax(rms[a:b]))
        kaymalar.append((i + 0.5) * 0.02 - tc)
    if not kaymalar:
        return "kesim yok"
    k = np.array(kaymalar) * 1000
    return (f"{len(k)} kesimde whoosh tepesi kesimden ortalama {k.mean():+.0f} ms, en uzak {np.abs(k).max():.0f} ms "
            + ("-> TAMAM" if np.abs(k).max() <= 60 else "-> BAK (tepe kesimden kaymış)"))


def olc(P, video: pathlib.Path | None = None) -> dict:
    kon = P.d / "kontrol"
    video = pathlib.Path(video) if video else P.d / "cikti" / f"{P.ad}.mp4"
    if not video.exists():
        raise SystemExit(f"{video} yok; önce render")
    oj = json_oku(kon / "olcum.json", {}) or {}
    rapor = [f"# Ölçüm — {video.name}", ""]
    # --- süre
    pr = _ffprobe(video)
    v, a = pr.get("video", {}), pr.get("audio", {})
    vs, as_ = float(v.get("duration", 0)), float(a.get("duration", 0))
    kare = int(v.get("nb_read_packets", 0))
    sure_ok = abs(vs - P.sure) < 1.5 / C.FPS and kare == P.toplam_kare and abs(as_ - vs) < 0.05
    rapor += ["## Süre",
              f"- görüntü {vs:.3f} sn ({kare} kare, beklenen {P.toplam_kare}), ses {as_:.3f} sn, "
              f"{v.get('width')}x{v.get('height')} {v.get('r_frame_rate')} -> " + ("TAMAM" if sure_ok else "UYUMSUZ"),
              f"- konuşma {P.konusma_kare / P.fps:.2f} sn + kuyruk {P.kuyruk_kare / P.fps:.2f} sn, {len(P.pp)} parça, "
              f"{len(P.V)} vuruş, {sum(1 for x in P.V if x.get('kart'))} kart", ""]
    # --- güvenli alan
    satir, ihlal = guvenli_alan(oj.get("olcumler", []))
    rapor += ["## Güvenli alan (piksel ölçümü)"] + satir + [""]
    # --- ses
    son = karisim.lufs(video)
    kon_i = karisim.lufs(kon / "konusma.wav")["I"] if (kon / "konusma.wav").exists() else float("nan")
    ef_i = karisim.lufs(kon / "efekt.wav")["I"] if (kon / "efekt.wav").exists() else float("nan")
    ses = oj.get("ses", {})
    rapor += ["## Ses",
              f"- son dosya: {son['I']:.1f} LUFS, gerçek tepe {son['TP']:.1f} dBTP, LRA {son['LRA']:.1f} LU "
              f"(hedef -14 LUFS, tepe <= -1 dBTP) -> " + ("TAMAM" if abs(son['I'] + 14) <= 1.0 and son['TP'] <= -0.5 else "BAK"),
              f"- konuşma izi {kon_i:.1f} LUFS, efekt izi {ef_i:.1f} LUFS -> efektler konuşmanın {kon_i - ef_i:.1f} dB altında",
              f"- whoosh: {whoosh_kesimde(P, kon / 'efekt.wav')}",
              f"- efektler: {ses.get('efekt_sayisi', {})}, sınırlayıcıya giren örnek {ses.get('sinirlanan_ornek', '?')}", ""]
    # --- temas sayfası
    zamanlar = varsayilan_kareler(P)
    if P.kuyruk_kare:
        zamanlar.append(round(P.sure - 0.2, 2))
    resimler = [(t, P.vurus(t), _kare_al(video, t)) for t in zamanlar]
    temas = kon / "temas.jpg"
    temas_sayfasi(resimler, temas, P)
    rapor += ["## Temas sayfası", f"- {temas} ({len(resimler)} kare; kırmızı taralı = platform arayüzü). AÇ VE BAK.", ""]
    if oj.get("render_sn"):
        rapor += [f"Render: {oj['render_sn']} sn (ses {oj.get('ses_sn')} sn, görüntü {oj.get('goruntu_sn')} sn)."]
    metin = "\n".join(rapor)
    (kon / "olcum.md").write_text(metin, "utf-8")
    print(metin)
    return {"sure_ok": sure_ok, "ihlal": ihlal, "lufs": son, "konusma_I": kon_i, "efekt_I": ef_i, "temas": str(temas)}
