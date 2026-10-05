"""plan.json -> mp4. Parça parça üretir (önbellekli), uç uca ekler, sesi en sonda örnek örnek kurar.

Görüntü türleri (bloklar.json'daki `goruntu`):
- kamera:      ana kayıt tam kare. Atlanan kesimde 1,00 / 1,06 yakınlaşma sırayla (jump cut göze batmasın).
- ekran:       ekran kaydı tam kare + köşede yuvarlak küçük kamera (ana kayıttan).
- ekran-hizli: ekran gibi; konuşmasız aralıklar 2x / 4x hızlanır, sol üstte "2x" rozeti.

Ses her zaman ana kayıttan: parça = kare sayısı x (48000/fps) örnek, uçlarında 10 ms yumuşatma,
sonra alçak kesen + hafif gürültü azaltma + kompresör + loudnorm −14 LUFS.
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import pathlib
import re
import subprocess
import time

import kesim
import medya

SURUM = 3
KOK = pathlib.Path(__file__).resolve().parents[4]
FONT = KOK / "fontlar" / "IBMPlexMono-SemiBold.ttf"
ZEMIN = "0x111111"


def boyut_coz(s: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)[xX:](\d+)", s.strip())
    if not m:
        raise SystemExit(f"--boyut '{s}' anlaşılmadı (ör. 1920x1080)")
    w, h = int(m.group(1)), int(m.group(2))
    return w - w % 2, h - h % 2


# --- görseller (Pillow: maske, çerçeve, rozet) -----------------------------------------

def gorseller(dizin: pathlib.Path, D: int, kal: int, sekil: str, H: int, hizlar: set[int]) -> dict:
    from PIL import Image, ImageDraw, ImageFont
    dizin.mkdir(parents=True, exist_ok=True)
    out = {}
    r_oran = 0.5 if sekil == "daire" else 0.18

    def sekil_ciz(boy: int, renk, mod: str):
        S = 4
        im = Image.new(mod, (boy * S, boy * S), 0 if mod == "L" else (0, 0, 0, 0))
        ImageDraw.Draw(im).rounded_rectangle((0, 0, boy * S - 1, boy * S - 1), radius=int(boy * S * r_oran), fill=renk)
        return im.resize((boy, boy), Image.LANCZOS)

    m = dizin / f"maske-{sekil}-{D}.png"
    if not m.exists():
        sekil_ciz(D, 255, "L").save(m)
    c = dizin / f"cerceve-{sekil}-{D + 2 * kal}.png"
    if not c.exists():
        sekil_ciz(D + 2 * kal, (250, 248, 242, 255), "RGBA").save(c)
    out["maske"], out["cerceve"] = m, c
    for h in hizlar:
        r = dizin / f"rozet-{h}x-{H}.png"
        if not r.exists():
            boy = max(18, round(H * 0.036))
            try:
                font = ImageFont.truetype(str(FONT), boy)
            except OSError:
                font = ImageFont.load_default(size=boy)
            metin = f"{h}x"
            x0, y0, x1, y1 = font.getbbox(metin)
            px, py = round(boy * 0.6), round(boy * 0.35)
            w, hh = x1 - x0 + 2 * px, y1 - y0 + 2 * py
            S = 3
            im = Image.new("RGBA", (w * S, hh * S), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle((0, 0, w * S - 1, hh * S - 1), radius=hh * S // 2, fill=(16, 16, 16, 205))
            im = im.resize((w, hh), Image.LANCZOS)
            ImageDraw.Draw(im).text((px - x0, py - y0), metin, font=font, fill=(255, 255, 255, 255))
            im.save(r)
        out[f"rozet{h}"] = r
    return out


# --- tek parça ------------------------------------------------------------------------

def _ss(t: float) -> list[str]:
    return ["-ss", f"{max(0.0, t):.4f}"]


def parca_komutu(p: dict, ay: dict) -> tuple[list[str], list[str]]:
    """(girdi argümanları, filtre zinciri). Görüntü türüne göre."""
    W, H, fps = ay["W"], ay["H"], ay["fps"]
    i, n = kesim.kareye(p["in"], p["out"], p.get("hiz", 1), fps)
    hiz = p.get("hiz", 1)
    d = n / fps
    kaynak_sure = d * hiz + 0.3
    pts = f"setpts=(PTS-STARTPTS)/{hiz}" if hiz != 1 else "setpts=PTS-STARTPTS"
    uzat = f"tpad=stop_mode=clone:stop_duration={d + 0.5:.3f}"
    coz = ay["coz"]
    gir, fz = [], []
    gor = p["gorsel"]
    if gor == "kamera" or not ay.get("ekran"):
        z = p.get("zoom", 1.0) or 1.0
        gir += [*coz, *_ss(i), "-t", f"{kaynak_sure:.4f}", "-i", ay["video"]]
        kirp = "" if z == 1.0 else f"crop=iw/{z}:ih/{z}:(iw-iw/{z})*0.5:(ih-ih/{z})*0.4,"
        fz.append(f"[0:v]{pts},fps={fps},{uzat},{kirp}scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                  f"crop={W}:{H},setsar=1,format=yuv420p[v0]")
        son = "v0"
    else:
        et = i + ay["ofset"] + ay["kayma"] * i
        bosluk = max(0.0, -et) / hiz
        gir += [*coz, *_ss(et), "-t", f"{kaynak_sure:.4f}", "-i", ay["ekran"]]
        on = f"tpad=start_duration={bosluk:.3f}:color=black," if bosluk > 0 else ""
        ekk = f"crop={ay['ekran_kirp']}," if ay.get("ekran_kirp") else ""
        fz.append(f"[0:v]{pts},fps={fps},{on}{uzat},{ekk}scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                  f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={ZEMIN},setsar=1,format=yuv420p[b0]")
        son, k = "b0", 1
        if ay["kose"] != "yok" and p.get("kose", True):
            D, kal, (x, y), (cw, ch, cx, cy) = ay["D"], ay["kal"], ay["kose_xy"], ay["kirp"]
            gir += [*coz, *_ss(i), "-t", f"{kaynak_sure:.4f}", "-i", ay["video"],
                    "-i", str(ay["gorsel"]["maske"]), "-i", str(ay["gorsel"]["cerceve"])]
            fz.append(f"[{k}:v]{pts},fps={fps},{uzat},crop={cw}:{ch}:{cx}:{cy},scale={D}:{D}:flags=lanczos,"
                      f"format=yuva420p[c0];[{k + 1}:v]format=gray[m];[c0][m]alphamerge[c]")
            fz.append(f"[{son}][{k + 2}:v]overlay={x - kal}:{y - kal}[b1];[b1][c]overlay={x}:{y}[b2]")
            son, k = "b2", k + 3
        if hiz > 1:
            m = round(H * 0.04)
            rx = m if ay["kose"] != "sol-ust" else f"W-w-{m}"
            gir += ["-i", str(ay["gorsel"][f"rozet{hiz}"])]
            fz.append(f"[{son}][{k}:v]overlay={rx}:{m}[r0]")
            son = "r0"
    fz.append(f"[{son}]trim=end_frame={n},setpts=PTS-STARTPTS[vo]")
    return gir, fz


def parca_uret(no: int, p: dict, ay: dict) -> pathlib.Path:
    i, n = kesim.kareye(p["in"], p["out"], p.get("hiz", 1), ay["fps"])
    anahtar = json.dumps([SURUM, p["in"], p["out"], p["gorsel"], p.get("hiz", 1), p.get("zoom", 1.0), p.get("kose", True),
                          ay["imza"]], default=str)
    out = ay["dizin"] / f"{no:04d}-{hashlib.sha1(anahtar.encode()).hexdigest()[:10]}.mp4"
    if out.exists():
        return out
    gir, fz = parca_komutu(p, ay)
    tmp = out.with_name(out.stem + ".tmp.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y", *gir, "-filter_complex", ";".join(fz), "-map", "[vo]", "-an",
           "-frames:v", str(n), "-r", str(ay["fps"]), *ay["venc"], str(tmp)]
    try:
        medya.calistir(cmd, zaman_asimi=1200)
    except (RuntimeError, subprocess.TimeoutExpired):
        if not ay["coz"]:
            raise
        medya.calistir([c for c in cmd if c not in ay["coz"]], zaman_asimi=2400)   # donanım çözücüsüz yeniden
    tmp.rename(out)
    return out


# --- ses ------------------------------------------------------------------------------

SES_TEMIZ = "highpass=f=80,afftdn=nr=8:nf=-50,acompressor=threshold=-24dB:ratio=3:attack=6:release=150:makeup=4"
HEDEF = "I=-14:TP=-1.5:LRA=11"


def _olc(ses: pathlib.Path, zincir: str) -> dict | None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ses), "-af",
                        f"{zincir}loudnorm={HEDEF}:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    return json.loads(m.group(0)) if m else None


def ses_zinciri(ses: pathlib.Path, temiz: bool) -> str:
    """Hedef −14 LUFS, tepe −1,5 dBTP. Tek geçişli loudnorm konuşmada hedefin ~1 dB altında
    kalıyordu (ölçüldü: −15,0; tepe/ses oranı yüksek, doğrusal kazanç tepeyi aşıyor). Önce ölç,
    eksik kazancı ver, tepeleri sınırlayıcıyla −2 dBFS'te tut, sonra ölçülmüş değerlerle loudnorm."""
    on = SES_TEMIZ + "," if temiz else ""
    o = _olc(ses, on)
    if not o:
        return f"{on}loudnorm={HEDEF}"
    kazanc = max(0.0, -14.0 - float(o["input_i"]) + 0.3)
    on += f"volume={kazanc:.2f}dB,alimiter=limit=0.79:attack=5:release=60:level=false,"
    o = _olc(ses, on)
    if not o:
        return f"{on}loudnorm={HEDEF}"
    return (f"{on}loudnorm={HEDEF}:measured_I={o['input_i']}:measured_TP={o['input_tp']}:measured_LRA={o['input_lra']}:"
            f"measured_thresh={o['input_thresh']}:offset={o['target_offset']}:linear=true")


def lufs(yol: pathlib.Path) -> float | None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(yol), "-map", "0:a:0", "-af",
                        "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


# --- ana ------------------------------------------------------------------------------

def calistir(proje: pathlib.Path, a) -> int:
    medya.ffmpeg_kontrol()
    plan_yol = proje / "plan.json"
    if not plan_yol.exists():
        raise SystemExit(f"{plan_yol} yok. Önce: kurgu.py kurgu {proje}")
    plan = json.loads(plan_yol.read_text("utf-8"))
    kaynak = json.loads((proje / "kaynak.json").read_text("utf-8"))
    pp, fps = plan["parcalar"], plan["fps"]
    if not pp:
        raise SystemExit("planda parça yok")
    bas = a.bas or 0
    bit = len(pp) - 1 if a.bit is None else min(a.bit, len(pp) - 1)
    W, H = boyut_coz(a.boyut)
    enc, venc, coz = medya.kodlayici(a.kodlayici, W, H)
    ekranli = any(p["gorsel"] != "kamera" for p in pp[bas:bit + 1])
    ay = {"W": W, "H": H, "fps": fps, "venc": venc, "coz": coz, "video": kaynak["video"], "ekran": None,
          "ofset": 0.0, "kayma": 0.0, "kose": a.kose, "dizin": proje / "parca", "ekran_kirp": None}
    if a.ekran_kirp:
        if not re.fullmatch(r"\d+:\d+:\d+:\d+", a.ekran_kirp.strip()):
            raise SystemExit(f"--ekran-kirp '{a.ekran_kirp}' anlaşılmadı (genişlik:yükseklik:x:y, ör. 2468:1388:46:47)")
        ay["ekran_kirp"] = a.ekran_kirp.strip()
    if ekranli:
        sj = proje / "senkron.json"
        if not kaynak.get("ekran"):
            raise SystemExit("planda ekran bloğu var ama ekran kaydı yok: kurgu.py senkron <proje> --ekran <dosya>")
        if not sj.exists():
            raise SystemExit(f"{sj} yok. Önce: kurgu.py senkron {proje}")
        s = json.loads(sj.read_text("utf-8"))
        ay.update(ekran=kaynak["ekran"], ofset=s["ofset"], kayma=s.get("kayma", 0.0))
        vb = kaynak.get("video_bilgi") or medya.bilgi(kaynak["video"])
        D = round(H * a.kose_boyut) // 2 * 2
        kal = max(2, round(D * 0.022))
        cx_, cy_, boy = (float(v) for v in a.kose_kirp.split(","))
        kenar = min(vb["w"], vb["h"], round(vb["h"] * boy)) // 2 * 2
        kx = min(max(0, round(vb["w"] * cx_ - kenar / 2)), vb["w"] - kenar)
        ky = min(max(0, round(vb["h"] * cy_ - kenar / 2)), vb["h"] - kenar)
        m = round(H * 0.04)
        x = m + kal if "sol" in a.kose else W - D - m - kal
        y = m + kal if "ust" in a.kose else H - D - m - kal
        hizlar = {p["hiz"] for p in pp if p.get("hiz", 1) > 1}
        ay.update(D=D, kal=kal, kose_xy=(x, y), kirp=(kenar, kenar, kx, ky),
                  gorsel=gorseller(proje / "kontrol" / "gorsel", D, kal, a.kose_sekil, H, hizlar))
    kaynak_imza = [(f, pathlib.Path(f).stat().st_size) for f in (kaynak["video"], ay["ekran"]) if f]
    ay["imza"] = [W, H, fps, enc, venc, ay["ekran_kirp"], a.kose, a.kose_boyut, a.kose_kirp, a.kose_sekil, ay["ofset"], ay["kayma"],
                  kaynak_imza]
    ay["dizin"].mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    secili = list(range(bas, bit + 1))
    dosyalar: dict[int, pathlib.Path] = {}
    print(f"{len(secili)} parça, {W}x{H} {fps} fps, kodlayıcı {enc}, {a.paralel} paralel", flush=True)
    with cf.ThreadPoolExecutor(max_workers=max(1, a.paralel)) as ex:
        isler = {ex.submit(parca_uret, no, pp[no], ay): no for no in secili}
        for n, f in enumerate(cf.as_completed(isler), 1):
            dosyalar[isler[f]] = f.result()
            if n % 10 == 0 or n == len(secili):
                g = time.time() - t0
                print(f"  {n}/{len(secili)} parça · {g:.0f} sn · kalan ~{g / n * (len(secili) - n):.0f} sn", flush=True)
    t_goruntu = time.time() - t0

    kontrol = proje / "kontrol"
    kontrol.mkdir(exist_ok=True)
    tam = bas == 0 and bit == len(pp) - 1
    ek = "" if tam else f"-{bas}-{bit}"
    liste = kontrol / f"liste{ek}.txt"
    liste.write_text("".join(f"file '{dosyalar[no].as_posix()}'\n" for no in secili), "utf-8")
    ham = kontrol / f"goruntu{ek}.mp4"
    medya.calistir(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(liste), "-c", "copy", str(ham)])

    _, s48 = medya.ses_hazirla(proje, kaynak)
    x, _ = medya.wav_oku(s48)
    ses = kontrol / f"ses{ek}.wav"
    medya.wav_yaz(ses, medya.kesik_ses(x, pp[bas:bit + 1], fps), kesim.SR)
    cikti = pathlib.Path(a.cikti).resolve() if a.cikti else proje / "cikti" / f"kurgu{ek}.mp4"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    zincir = ses_zinciri(ses, a.ses == "temiz")
    medya.calistir(["ffmpeg", "-v", "error", "-y", "-i", str(ham), "-i", str(ses), "-filter_complex", f"[1:a]{zincir}[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart", str(cikti)])
    if tam:   # artık planda olmayan eski parçalar
        kullanilan = set(dosyalar.values())
        for f in ay["dizin"].glob("*.mp4"):
            if f not in kullanilan:
                f.unlink()
    beklenen = sum(kesim.kareye(p["in"], p["out"], p.get("hiz", 1), fps)[1] for p in pp[bas:bit + 1]) / fps
    olculen = medya.bilgi(cikti)["sure"]
    seviye = lufs(cikti)
    turler = {}
    for p in pp[bas:bit + 1]:
        turler[p["gorsel"]] = turler.get(p["gorsel"], 0) + 1
    print(f"{cikti}\n  süre {olculen:.2f} sn (plan {beklenen:.2f}) · ses "
          f"{'?' if seviye is None else f'{seviye:.1f}'} LUFS · parçalar {turler} · "
          f"görüntü {t_goruntu:.0f} sn, toplam {time.time() - t0:.0f} sn", flush=True)
    return 0


def temas(proje: pathlib.Path, video: str | None) -> int:
    """Her bloğun ilk parçasından (ve ilk hızlı parçadan) bir kare: göz kontrolü için temas sayfası."""
    plan = json.loads((proje / "plan.json").read_text("utf-8"))
    pp, fps = plan["parcalar"], plan["fps"]
    v = pathlib.Path(video).resolve() if video else proje / "cikti" / "kurgu.mp4"
    if not v.exists():
        raise SystemExit(f"{v} yok. Önce: kurgu.py cek {proje}")
    t0 = kesim.zaman_cizelgesi(pp, fps)
    secim, gorulen, hizli = [], set(), False
    for k, p in enumerate(pp):
        if p["blok"] not in gorulen or (p.get("hiz", 1) > 1 and not hizli):
            gorulen.add(p["blok"])
            hizli = hizli or p.get("hiz", 1) > 1
            secim.append((t0[k] + kesim.sure(p, fps) / 2, p))
    secim = secim[:16]
    d = proje / "kontrol" / "temas"
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.jpg"):
        f.unlink()
    for n, (t, _) in enumerate(secim):
        medya.calistir(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(v), "-frames:v", "1",
                        "-vf", "scale=640:-2", "-q:v", "3", str(d / f"{n:02d}.jpg")])
    sut = min(4, len(secim))
    sat = (len(secim) + sut - 1) // sut
    out = proje / "kontrol" / "temas.jpg"
    medya.calistir(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(d / "%02d.jpg"),
                    "-vf", f"tile={sut}x{sat}:padding=8:margin=8:color=white", "-frames:v", "1", "-q:v", "3", str(out)])
    for n, (t, p) in enumerate(secim):
        print(f"  {n + 1:2d}. {kesim._mmss(t)} {p['etiket']} ({p['gorsel']}{', ' + str(p['hiz']) + 'x' if p.get('hiz', 1) > 1 else ''})")
    print(out)
    return 0
