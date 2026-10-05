"""Konuşan kafa kaydından dikey Reels/Shorts (1080x1920, 30 fps), "kart" formatında.

    python reels.py dokum     <proje> --video kayit.mp4 [--bas 56 --sure 42] [--terimler "..."]
    python reels.py kurgu     <proje>                 # atilacak.json'dan sonra planı yeniden kur
    python reels.py kelimeler <proje>                 # kurguda kalan kelimeler, çıktı saniyesiyle
    python reels.py yuz       <proje>                 # yüz kutusu tahmini -> kadraj.json + kontrol/kadraj.jpg
    python reels.py vuruslar  <proje>                 # senaryodaki kartların çözülmüş zamanları
    python reels.py kare      <proje> 1.5,8,20        # önizleme kareleri -> kontrol/kareler.jpg
    python reels.py render    <proje>                 # -> cikti/<ad>.mp4 (+ otomatik ölçüm)
    python reels.py olc       <proje>                 # temas sayfası + güvenli alan + ses seviyesi

<proje> bir klasör (öneri: calisma/reels/<ad>). Döküm ve kesim `yatay-kurgu` skill'inin araçlarıyla
yapılır (aynı repo); bu araç onların yazdığı kaynak.json / transkript.json / plan.json dosyalarını okur.
Ham kayıt yalnızca okunur.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import time

BURASI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BURASI))

import cizim as C  # noqa: E402
from proje import Proje, json_oku, json_yaz, mmss  # noqa: E402

KURGU = C.KOK / ".claude" / "skills" / "yatay-kurgu" / "araclar" / "kurgu.py"


def ffmpeg_var() -> None:
    for p in ("ffmpeg", "ffprobe"):
        if not shutil.which(p):
            raise SystemExit(f"{p} bulunamadı. macOS: brew install ffmpeg · Windows: winget install ffmpeg")


def yatay_kurgu(*argv: str) -> None:
    if not KURGU.exists():
        raise SystemExit(f"{KURGU} yok: reels, döküm ve kesim için aynı repodaki yatay-kurgu skill'ini kullanır.")
    r = subprocess.run([sys.executable, str(KURGU), *argv])
    if r.returncode:
        raise SystemExit(r.returncode)


def h264_kodlayici() -> list[str]:
    """Pencere kesiti için kodlayıcı: macOS'ta VideoToolbox (hızlı), yoksa libx264."""
    if sys.platform == "darwin":
        dene = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=320x240:d=0.1",
                               "-c:v", "h264_videotoolbox", "-f", "null", "-"], capture_output=True)
        if dene.returncode == 0:
            return ["-c:v", "h264_videotoolbox", "-b:v", "60M", "-allow_sw", "1"]
    return ["-c:v", "libx264", "-crf", "14", "-preset", "fast"]


# ------------------------------------------------------------------ dokum / kurgu
def k_dokum(a) -> None:
    ffmpeg_var()
    P = pathlib.Path(a.proje).resolve()
    P.mkdir(parents=True, exist_ok=True)
    video = pathlib.Path(a.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"video yok: {video}")
    kaynak = video
    if a.bas is not None or a.sure is not None:
        bas, sure = a.bas or 0.0, a.sure
        pencere = {"video": str(video), "bas": bas, "sure": sure}
        kaynak = P / "kaynak.mov"
        if json_oku(P / "pencere.json") != pencere or not kaynak.exists():
            print(f"pencere kesiliyor: {video.name} {bas:.2f} sn'den {sure if sure else 'sona'} sn", flush=True)
            t0 = time.time()
            cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{bas:.3f}", "-i", str(video)]
            if sure:
                cmd += ["-t", f"{sure:.3f}"]
            cmd += ["-map", "0:v:0", "-map", "0:a:0", *h264_kodlayici(), "-pix_fmt", "yuv420p",
                    "-c:a", "pcm_s16le", "-ar", "48000", str(kaynak)]
            subprocess.run(cmd, check=True)
            json_yaz(P / "pencere.json", pencere)
            print(f"  {kaynak.name} ({time.time() - t0:.0f} sn)", flush=True)
    ek = []
    if a.terimler:
        ek += ["--terimler", a.terimler]
    if a.model:
        ek += ["--model", a.model]
    if a.yeniden:
        ek.append("--yeniden")
    yatay_kurgu("dokum", str(P), "--video", str(kaynak), "--fps", str(C.FPS), *ek)
    print(f"\nSıradaki: {P / 'dokum.md'} dosyasını oku; atılacakları atilacak.json'a yaz, sonra `reels.py kurgu {P}`.")


def k_kurgu(a) -> None:
    yatay_kurgu("kurgu", str(pathlib.Path(a.proje).resolve()), "--fps", str(C.FPS))


def k_kelimeler(a) -> None:
    P = Proje(a.proje, senaryo=False)
    print(f"# {P.ad}: {len(P.kelimeler)} kelime, konuşma {P.konusma_kare / P.fps:.2f} sn ({len(P.pp)} parça)")
    print("# satır = cümle; [saniye] kelime. Çıpa için kelimenin BAŞINI yaz (ör. 'effort' -> effort'u da tutar)\n")
    satir, bas = [], None
    for w in P.kelimeler:
        if bas is None:
            bas = w["start"]
        satir.append(f"[{w['start']:.2f}] {w['word']}")
        if w["word"][-1:] in ".?!…":
            print(f"{mmss(bas)}  " + " ".join(satir))
            satir, bas = [], None
    if satir:
        print(f"{mmss(bas)}  " + " ".join(satir))


def k_vuruslar(a) -> None:
    P = Proje(a.proje)
    for n, v in enumerate(P.V):
        k = v.get("kart") or {}
        alt = [f"{o.get('yazi', o.get('kim', ''))[:22]}@{o['_t']:.2f}" for o in Proje._ogeler(k)]
        print(f"{n + 1:2d}  {mmss(v['_t'])} - {mmss(v['_bit'])}  {v['_duzen']:6s} {k.get('tur', '-'):9s} "
              f"'{v.get('kelime', '')}'  " + "  ".join(alt))
    print(f"toplam {P.sure:.2f} sn (konuşma {P.konusma_kare / P.fps:.2f} + kuyruk {P.kuyruk_kare / P.fps:.2f})")


# ------------------------------------------------------------------ yüz / kare / render / olc
def k_yuz(a) -> None:
    import kadraj
    kadraj.tahmin_et(pathlib.Path(a.proje).resolve(), a.ornek, a.zorla)


def k_kare(a) -> None:
    import render
    P = Proje(a.proje)
    zamanlar = [float(x) for x in a.zamanlar.split(",")] if a.zamanlar else render.varsayilan_kareler(P)
    render.kareler(P, zamanlar)


def k_render(a) -> None:
    import render
    import denetim
    P = Proje(a.proje)
    son = render.render(P, a.kodlayici, a.cikti)
    if not a.olcme:
        denetim.olc(P, son)


def k_olc(a) -> None:
    import denetim
    P = Proje(a.proje)
    denetim.olc(P, pathlib.Path(a.video) if a.video else None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Konuşan kafa kaydından kart formatında dikey Reels")
    alt = ap.add_subparsers(dest="komut", required=True)

    p = alt.add_parser("dokum", help="(isteğe bağlı pencere kesiti) + harfiyen döküm + ilk plan")
    p.add_argument("proje")
    p.add_argument("--video", required=True, help="kamera kaydı (ses içinde)")
    p.add_argument("--bas", type=float, help="kayıttan yalnız bu saniyeden başlayan pencereyi kullan")
    p.add_argument("--sure", type=float, help="pencerenin uzunluğu (sn)")
    p.add_argument("--terimler", help="videoya özel terimler (Whisper istemine eklenir)")
    p.add_argument("--model", help="Whisper modeli (varsayılan yatay-kurgu'nunki: large-v3)")
    p.add_argument("--yeniden", action="store_true", help="transkript varsa da yeniden çöz")
    p.set_defaults(fn=k_dokum)

    for ad, fn, yardim in (("kurgu", k_kurgu, "atilacak.json'la planı yeniden kur"),
                           ("kelimeler", k_kelimeler, "kurguda kalan kelimeler, çıktı saniyesiyle"),
                           ("vuruslar", k_vuruslar, "senaryo kartlarının çözülmüş zamanları")):
        p = alt.add_parser(ad, help=yardim)
        p.add_argument("proje")
        p.set_defaults(fn=fn)

    p = alt.add_parser("yuz", help="yüz kutusu tahmini -> kadraj.json + kontrol/kadraj.jpg")
    p.add_argument("proje")
    p.add_argument("--ornek", type=int, default=8, help="kaç kareye bakılsın (varsayılan 8)")
    p.add_argument("--zorla", action="store_true", help="kadraj.json varsa da üzerine yaz")
    p.set_defaults(fn=k_yuz)

    p = alt.add_parser("kare", help="önizleme kareleri -> kontrol/kareler.jpg")
    p.add_argument("proje")
    p.add_argument("zamanlar", nargs="?", help="virgülle çıktı saniyeleri (boşsa her vuruştan bir kare)")
    p.set_defaults(fn=k_kare)

    p = alt.add_parser("render", help="-> cikti/<ad>.mp4, sonra ölçüm")
    p.add_argument("proje")
    p.add_argument("--kodlayici", default="x264", choices=("x264", "videotoolbox"))
    p.add_argument("--cikti", help="çıktı dosyası (varsayılan <proje>/cikti/<ad>.mp4)")
    p.add_argument("--olcme", action="store_true", help="sondaki ölçümü atla")
    p.set_defaults(fn=k_render)

    p = alt.add_parser("olc", help="temas sayfası + güvenli alan + ses seviyesi")
    p.add_argument("proje")
    p.add_argument("--video", help="ölçülecek mp4 (varsayılan cikti/<ad>.mp4)")
    p.set_defaults(fn=k_olc)

    a = ap.parse_args(argv)
    a.fn(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
