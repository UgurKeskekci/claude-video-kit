"""Yatay konuşma videosu için kaba kurgu — tek giriş noktası.

    python kurgu.py dokum   <proje> --video kamera.mp4 [--ekran ekran.mp4] [--model large-v3] [--dil tr]
    python kurgu.py kurgu   <proje>                      # atilacak.json / bloklar.json -> plan.json + dokum.md
    python kurgu.py senkron <proje> [--ekran ekran.mp4]  # iki kaydı sesten eşle -> senkron.json
    python kurgu.py cek     <proje> [--boyut 1920x1080]  # plan.json -> cikti/kurgu.mp4
    python kurgu.py dogrula <proje>                      # kesik sesi yeniden çöz -> dogrula.md
    python kurgu.py pencere <proje> 104.1 212.7 …        # birleşimin ±3 sn'sini yeniden çöz
    python kurgu.py zarf    <proje> 80 95                # aralığın ses zarfı + kelimeleri
    python kurgu.py temas   <proje>                      # çıktıdan blok başına bir kare -> kontrol/temas.jpg

<proje> bir klasördür (öneri: calisma/<ad>). Ham videolara yalnızca okunur, hiçbir şey yazılmaz.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import kesim  # noqa: E402


def json_oku(yol: pathlib.Path, varsayilan=None):
    if not yol.exists():
        return varsayilan
    with open(yol, encoding="utf-8-sig") as f:
        return json.load(f)


def json_yaz(yol: pathlib.Path, veri) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1), "utf-8")


def gerekli(yol: pathlib.Path, ipucu: str):
    if not yol.exists():
        raise SystemExit(f"{yol} yok. Önce: {ipucu}")
    return yol


def sn(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def kaynak_oku(proje: pathlib.Path) -> dict:
    return json_oku(gerekli(proje / "kaynak.json", f"kurgu.py dokum {proje} --video <dosya>"))


def transkript_oku(proje: pathlib.Path) -> dict:
    return json_oku(gerekli(proje / "transkript.json", f"kurgu.py dokum {proje} --video <dosya>"))


def istem_kur(sozluk: dict, terimler: str | None) -> str:
    istem = sozluk.get("istem", "")
    if terimler:
        istem = f"{istem} {terimler.strip()}".strip()
    return istem


# --- dokum ----------------------------------------------------------------------------

def k_dokum(a) -> int:
    import medya
    medya.ffmpeg_kontrol()
    proje = pathlib.Path(a.proje).resolve()
    proje.mkdir(parents=True, exist_ok=True)
    video = pathlib.Path(a.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"video yok: {video}")
    eski = json_oku(proje / "kaynak.json", {}) or {}
    vb = medya.bilgi(video)
    if not vb["ses"]:
        raise SystemExit(f"{video.name} içinde ses yok. Sesi taşıyan kaydı --video ile ver.")
    kaynak = {"video": str(video), "video_bilgi": vb}
    ekran = a.ekran or (eski.get("ekran") if eski.get("video") == str(video) else None)
    if ekran:
        ekran = pathlib.Path(ekran).expanduser().resolve()
        if not ekran.exists():
            raise SystemExit(f"ekran kaydı yok: {ekran}")
        kaynak["ekran"] = str(ekran)
        kaynak["ekran_bilgi"] = medya.bilgi(ekran)
    yeni_video = eski.get("video") != str(video)
    if yeni_video:
        for ad in ("ses16k.wav", "ses48.wav"):
            (proje / ad).unlink(missing_ok=True)
    json_yaz(proje / "kaynak.json", kaynak)
    print(f"{video.name}: {sn(vb['sure'])}, {vb['w']}x{vb['h']} {vb['fps']:.2f} fps", flush=True)

    t0 = time.time()
    s16, _ = medya.ses_hazirla(proje, kaynak)
    en = medya.zarf(s16)
    t_ses = time.time() - t0
    sozluk = medya.sozluk_oku(a.sozluk)
    istem = istem_kur(sozluk, a.terimler)
    tr = proje / "transkript.json"
    eski_tr = json_oku(tr)
    ayni = (eski_tr and not yeni_video and eski_tr.get("model") == a.model and eski_tr.get("dil") == a.dil
            and eski_tr.get("istem") == istem)
    t1 = time.time()
    if ayni and not a.yeniden:
        print(f"  transkript.json zaten var ({a.model}); yeniden çözmek için --yeniden", flush=True)
    else:
        print(f"  harfiyen döküm: {a.model}, dil {a.dil}, eşik {en.esik:.1f} dB", flush=True)
        model = medya.model_yukle(a.model, a.cihaz)
        ws = medya.harfiyen_coz(model, s16, a.dil, istem, sozluk.get("duzeltmeler", []), en)
        json_yaz(tr, {"model": a.model, "dil": a.dil, "istem": istem, "kaynak_sn": round(en.sure, 3),
                      "cozum_sn": round(time.time() - t1, 1), "words": ws})
        print(f"  {len(ws)} kelime, {time.time() - t1:.0f} sn ({en.sure / max(1e-6, time.time() - t1):.2f}x gerçek zaman)",
              flush=True)
    print(f"  süreler: ses {t_ses:.0f} sn, döküm {time.time() - t1:.0f} sn", flush=True)
    return plan_yap(proje, a.fps, a.zoom, a.serbest)


# --- kurgu ----------------------------------------------------------------------------

def plan_yap(proje: pathlib.Path, fps: int, zoom: float, serbest: str | None) -> int:
    import medya
    kaynak = kaynak_oku(proje)
    tr = transkript_oku(proje)
    s16, _ = medya.ses_hazirla(proje, kaynak)
    en = medya.zarf(s16)
    bloklar = kesim.blok_listesi(json_oku(proje / "bloklar.json"), en.sure)
    atilacak = kesim.aralik_listesi(json_oku(proje / "atilacak.json", []), "atilacak.json")
    korunacak = kesim.aralik_listesi(json_oku(proje / "korunacak.json", []), "korunacak.json")
    ek = {kesim.norm(x) for x in (serbest or "").split(",") if x.strip()}
    for x, y, g in atilacak:
        if not any(x < b["son"] and y > b["bas"] for b in bloklar):
            print(f"  UYARI: atilacak {x:.2f}–{y:.2f} hiçbir blokla kesişmiyor ({g})")
    if any(b["goruntu"] != "kamera" for b in bloklar) and not kaynak.get("ekran"):
        print("  UYARI: bloklarda ekran var ama kaynak.json'da ekran kaydı yok (dokum --ekran ya da senkron --ekran)")
    pp, satir, say = kesim.plan_kur(tr["words"], en, bloklar, atilacak, korunacak,
                                    kesim.TEKRAR_SERBEST | ek, fps, zoom)
    json_yaz(proje / "plan.json", {"fps": fps, "zoom": zoom, "sayilar": say, "parcalar": pp})
    baslik = f"Kurgu dökümü — {pathlib.Path(kaynak['video']).name}"
    (proje / "dokum.md").write_text(kesim.dokum_metni(satir, say, baslik), "utf-8")
    print(f"{say['parca']} parça, {say['blok']} blok: {sn(say['kaynak_sn'])} → {sn(say['cikti_sn'])} · "
          f"elle {say['elle_atma']} · tekrar {say['oto_tekrar_kelime']} kelime · aday {say['aday']} · "
          f"düşen {say['dustu_kelime']} kelime -> {proje / 'dokum.md'}")
    return 0


def k_kurgu(a) -> int:
    return plan_yap(pathlib.Path(a.proje).resolve(), a.fps, a.zoom, a.serbest)


# --- senkron / cek / temas ------------------------------------------------------------

def k_senkron(a) -> int:
    import senkron
    return senkron.calistir(pathlib.Path(a.proje).resolve(), a.ekran, a.ofset)


def k_cek(a) -> int:
    import cek
    return cek.calistir(pathlib.Path(a.proje).resolve(), a)


def k_temas(a) -> int:
    import cek
    return cek.temas(pathlib.Path(a.proje).resolve(), a.cikti)


# --- dogrula / pencere / zarf -----------------------------------------------------------

def kesik_hazirla(proje: pathlib.Path) -> tuple[dict, pathlib.Path, pathlib.Path]:
    """plan.json -> kontrol/kesik48.wav + kesik16k.wav (cek ile aynı örnek ızgarası)."""
    import medya
    plan = json_oku(gerekli(proje / "plan.json", f"kurgu.py kurgu {proje}"))
    kaynak = kaynak_oku(proje)
    _, s48 = medya.ses_hazirla(proje, kaynak)
    k48, k16 = proje / "kontrol" / "kesik48.wav", proje / "kontrol" / "kesik16k.wav"
    anahtar = hashlib.sha1(json.dumps([[p["in"], p["out"], p.get("hiz", 1)] for p in plan["parcalar"]]
                                      + [plan["fps"]]).encode()).hexdigest()[:12]
    isaret = proje / "kontrol" / "kesik.anahtar"
    if not (k48.exists() and k16.exists() and isaret.exists() and isaret.read_text() == anahtar):
        x, _ = medya.wav_oku(s48)
        medya.wav_yaz(k48, medya.kesik_ses(x, plan["parcalar"], plan["fps"]), kesim.SR)
        medya.calistir(["ffmpeg", "-v", "error", "-y", "-i", str(k48), "-ar", "16000", str(k16)])
        isaret.write_text(anahtar)
    plan["_anahtar"] = anahtar
    return plan, k48, k16


def k_dogrula(a) -> int:
    import medya
    proje = pathlib.Path(a.proje).resolve()
    tr = transkript_oku(proje)
    plan, _, k16 = kesik_hazirla(proje)
    model_ad = a.model or tr.get("model", "large-v3")
    kt = proje / "kontrol" / "kesik-transkript.json"
    onceki = json_oku(kt)
    t0 = time.time()
    if onceki and onceki.get("anahtar") == plan["_anahtar"] and onceki.get("model") == model_ad:
        yeni = onceki["words"]
        print("  kesik ses değişmemiş, önceki yeniden çözüm kullanılıyor", flush=True)
    else:
        sozluk = medya.sozluk_oku(a.sozluk)
        model = medya.model_yukle(model_ad, a.cihaz)
        yeni = medya.harfiyen_coz(model, k16, tr.get("dil", "tr"), tr.get("istem", ""),
                                  sozluk.get("duzeltmeler", []), etiket="denetim ")
        json_yaz(kt, {"anahtar": plan["_anahtar"], "model": model_ad, "words": yeni})
    rapor, ozet = kesim.birlesim_denetle(plan["parcalar"], tr["words"], yeni, plan["fps"])
    (proje / "dogrula.md").write_text(kesim.dogrula_metni(rapor, ozet), "utf-8")
    print(f"{ozet['birlesim']} birleşim, {ozet['supheli']} şüpheli (EKSİK {ozet['eksik']}, SIZAN {ozet['sizan']}) · "
          f"beklenen {ozet['beklenen_kelime']} / duyulan {ozet['duyulan_kelime']} kelime · {time.time() - t0:.0f} sn "
          f"-> {proje / 'dogrula.md'}")
    return 0


def k_pencere(a) -> int:
    import medya
    proje = pathlib.Path(a.proje).resolve()
    tr = transkript_oku(proje)
    plan, _, k16 = kesik_hazirla(proje)
    pp, fps = plan["parcalar"], plan["fps"]
    x, sr = medya.wav_oku(k16)
    model = medya.model_yukle(a.model or tr.get("model", "large-v3"), a.cihaz)
    ws = tr["words"]
    t0 = kesim.zaman_cizelgesi(pp, fps)
    cikti_t = {}
    for k, p in enumerate(pp):
        for i in p.get("kelimeler", []):
            cikti_t[i] = t0[k] + max(0.0, ws[i]["start"] - p["in"]) / p.get("hiz", 1)
    for deger in a.zamanlar:
        T = deger if a.cikti else kesim.cikti_zamani(deger, pp, fps)
        bas, son = max(0.0, T - a.pay), T + a.pay
        segs, _ = model.transcribe(x[int(bas * sr): int(son * sr)], language=tr.get("dil", "tr"), beam_size=5,
                                   condition_on_previous_text=False, vad_filter=False,
                                   initial_prompt=tr.get("istem") or None)
        duyulan = " ".join(s.text.strip() for s in segs)
        beklenen = " ".join(ws[i]["word"].strip() for i in sorted(cikti_t) if bas <= cikti_t[i] < son)
        etiket = f"çıktı {kesim._mmss(T)}" + ("" if a.cikti else f" (kaynak {deger:.2f})")
        print(f"{etiket}\n  beklenen: {beklenen}\n  duyulan:  {duyulan}", flush=True)
    return 0


def k_zarf(a) -> int:
    import medya
    proje = pathlib.Path(a.proje).resolve()
    kaynak = kaynak_oku(proje)
    s16, _ = medya.ses_hazirla(proje, kaynak)
    en = medya.zarf(s16)
    tr = json_oku(proje / "transkript.json", {"words": []})
    plan = json_oku(proje / "plan.json")
    bas, son = a.bas, a.son
    print(f"eşik {en.esik:.1f} dB   '#' eşik+10 üstü  '+' eşik üstü  '.' sessiz   (her işaret 20 ms, satır 1 sn)")
    if plan:
        print("ikinci satır: '=' çıktıda kalan, ' ' atılan")
    print("kelimeler: " + "  ".join(f"{w['start']:.2f}:{w['word'].strip()}" for w in tr["words"]
                                     if bas <= w["start"] < son))
    pp = plan["parcalar"] if plan else []
    i = kesim.kare(bas)
    while i < kesim.kare(son):
        s, k = "", ""
        for j in range(i, min(i + 100, kesim.kare(son)), 2):
            v = max(en.db[j:j + 2]) if j < len(en.db) else -120
            s += "#" if v >= en.esik + 10 else ("+" if v >= en.esik else ".")
            t = j / 100
            k += "=" if any(p["in"] <= t < p["out"] for p in pp) else " "
        print(f"{i / 100:8.2f} {s}")
        if plan:
            print(f"{'':8} {k}")
        i += 100
    return 0


# --- CLI ------------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kurgu.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    alt = ap.add_subparsers(dest="komut", required=True)

    def plan_arglari(p):
        p.add_argument("--fps", type=int, default=30, choices=kesim.FPS_GECERLI, help="çıktı kare hızı (varsayılan 30)")
        p.add_argument("--zoom", type=float, default=1.06,
                       help="kamera bloğunda atlanan kesimde yakınlaşma (1 = kapalı, varsayılan 1.06)")
        p.add_argument("--serbest", help="otomatik atılmayacak tekrar kelimeleri, virgülle (ör. 'adım,bilgi')")

    def model_arglari(p, varsayilan=None):
        p.add_argument("--model", default=varsayilan, help="Whisper modeli: large-v3 | medium | small | …")
        p.add_argument("--cihaz", default="auto", choices=("auto", "cpu", "cuda"))
        p.add_argument("--sozluk", help="kendi sozluk.json'ın (varsayılan: araclar/sozluk.json)")

    p = alt.add_parser("dokum", help="ses çıkar + harfiyen döküm + ilk plan")
    p.add_argument("proje")
    p.add_argument("--video", required=True, help="sesi taşıyan ana kayıt (genelde kamera)")
    p.add_argument("--ekran", help="ayrı ekran kaydı (isteğe bağlı)")
    p.add_argument("--dil", default="tr")
    p.add_argument("--terimler", help="bu videoya özel terimler, Whisper istemine eklenir (ör. 'React Native, TypeScript, Vite')")
    p.add_argument("--yeniden", action="store_true", help="transkript varsa da yeniden çöz")
    model_arglari(p, "large-v3")
    plan_arglari(p)
    p.set_defaults(f=k_dokum)

    p = alt.add_parser("kurgu", help="plan.json + dokum.md (atilacak.json, bloklar.json, korunacak.json okunur)")
    p.add_argument("proje")
    plan_arglari(p)
    p.set_defaults(f=k_kurgu)

    p = alt.add_parser("senkron", help="ana kayıt ile ekran kaydını sesten eşle -> senkron.json")
    p.add_argument("proje")
    p.add_argument("--ekran", help="ekran kaydı (dokum'da verilmediyse)")
    p.add_argument("--ofset", type=float, help="ölçmeden elle ver: ekran_t = ana_t + ofset")
    p.set_defaults(f=k_senkron)

    p = alt.add_parser("cek", help="plan.json -> mp4")
    p.add_argument("proje")
    p.add_argument("--boyut", default="1920x1080", help="çıktı boyutu (varsayılan 1920x1080; 2560x1440 da olur)")
    p.add_argument("--kodlayici", default="auto", choices=("auto", "videotoolbox", "nvenc", "x264"))
    p.add_argument("--ekran-kirp", help="ekran kaydından kırpılacak alan, ffmpeg biçimi genişlik:yükseklik:x:y (ör. 2468:1388:46:47); "
                   "kenarda siyah şerit ya da tarayıcı çubuğu varsa")
    p.add_argument("--kose", default="sag-alt", choices=("sag-alt", "sol-alt", "sag-ust", "sol-ust", "yok"),
                   help="ekran bloklarında küçük kameranın köşesi")
    p.add_argument("--kose-boyut", type=float, default=0.26, help="küçük kamera çapı / çıktı yüksekliği")
    p.add_argument("--kose-kirp", default="0.5,0.42,0.75",
                   help="kameradan alınacak kare: merkez x, merkez y (0-1), kenar / yükseklik")
    p.add_argument("--kose-sekil", default="daire", choices=("daire", "yuvarlak"))
    p.add_argument("--ses", default="temiz", choices=("temiz", "ham"),
                   help="temiz: alçak kesen + gürültü azaltma + kompresör + −14 LUFS · ham: yalnız −14 LUFS")
    p.add_argument("--paralel", type=int, default=2, help="aynı anda kaç parça üretilsin (varsayılan 2)")
    p.add_argument("--bas", type=int, help="yalnız bu parça numarasından (deneme)")
    p.add_argument("--bit", type=int, help="bu parça numarasına kadar (dahil)")
    p.add_argument("--cikti", help="çıktı dosyası (varsayılan <proje>/cikti/kurgu.mp4)")
    p.set_defaults(f=k_cek)

    p = alt.add_parser("dogrula", help="kesik sesi yeniden çöz, her birleşimi denetle -> dogrula.md")
    p.add_argument("proje")
    model_arglari(p)
    p.set_defaults(f=k_dogrula)

    p = alt.add_parser("pencere", help="verilen anların ±pay sn'sini kesik seste yeniden çöz")
    p.add_argument("proje")
    p.add_argument("zamanlar", type=float, nargs="+", help="kaynak saniyesi (--cikti ile çıktı saniyesi)")
    p.add_argument("--cikti", action="store_true", help="zamanlar çıktı saniyesi")
    p.add_argument("--pay", type=float, default=3.0)
    model_arglari(p)
    p.set_defaults(f=k_pencere)

    p = alt.add_parser("zarf", help="kaynakta bir aralığın ASCII ses zarfı ve kelimeleri")
    p.add_argument("proje")
    p.add_argument("bas", type=float)
    p.add_argument("son", type=float)
    p.set_defaults(f=k_zarf)

    p = alt.add_parser("temas", help="çıktıdan blok başına bir kare -> kontrol/temas.jpg")
    p.add_argument("proje")
    p.add_argument("--cikti", help="denetlenecek video (varsayılan cikti/kurgu.mp4)")
    p.set_defaults(f=k_temas)

    a = ap.parse_args(argv)
    try:
        return a.f(a)
    except (ValueError, RuntimeError) as e:
        print(f"HATA: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
