"""Tek komut: sahne JSON'u -> Remotion render -> ses -> ölçüm.

    python3 .claude/skills/x-animasyon/araclar/uret.py ornekler/x-animasyon/ornek.json
    python3 .claude/skills/x-animasyon/araclar/uret.py hikaye.json --oran 9x16 --ad reels
    python3 .claude/skills/x-animasyon/araclar/uret.py hikaye.json --taslak     # yarım boy, sessiz, hızlı bakış

Çıktılar (varsayılan calisma/x-animasyon/):
  <ad>-<oran>-sessiz.mp4   Remotion'dan çıkan görüntü
  <ad>-<oran>.mp4          sesli son hâl (teslim edilen)
  <ad>-<oran>-sayfa.jpg    temas sayfası (her sahneden iki kare)
  <ad>-<oran>-olcum.txt    süre, ses seviyesi, whoosh kontrolü
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ortak as O  # noqa: E402

TURLER = {"baslik", "yazi", "sayac", "olcer", "sutunlar", "karsilastirma", "liste", "soru"}


def kontrol(js: dict):
    hatalar = []
    if not js.get("marka"):
        hatalar.append("'marka' yok")
    for i, s in enumerate(js.get("sahneler", [])):
        if s.get("tur") not in TURLER:
            hatalar.append(f"sahne {i + 1}: bilinmeyen tur {s.get('tur')!r} (olabilir: {', '.join(sorted(TURLER))})")
        if not isinstance(s.get("sure"), (int, float)) or s["sure"] < 0.5:
            hatalar.append(f"sahne {i + 1}: 'sure' en az 0,5 sn olmalı")
    if not js.get("sahneler"):
        hatalar.append("'sahneler' boş")
    if hatalar:
        sys.exit("JSON hatalı:\n  " + "\n  ".join(hatalar))


def hazirlik() -> str:
    """npx'in tam yolunu döndürür (Windows'ta npx.cmd; listeyle çağrılınca tam yol gerekiyor)."""
    npx, node = shutil.which("npx"), shutil.which("node")
    if not npx or not node:
        sys.exit("Node.js yok: https://nodejs.org (18 ya da üstü)")
    if not (O.REMOTION / "node_modules" / "remotion").exists():
        sys.exit("Önce kur:  cd remotion && npm install")
    if not (O.REMOTION / "public" / "fonts" / "Newsreader.ttf").exists():
        subprocess.run([node, "scripts/fontlari-kopyala.mjs"], cwd=O.REMOTION, check=True)
    return npx


def render(npx: str, kimlik: str, json_yol: pathlib.Path, cikti: pathlib.Path, taslak: bool, es: int | None) -> float:
    komut = [npx, "remotion", "render", kimlik, str(cikti), f"--props={json_yol}", "--log=warn", "--muted"]
    if taslak:
        komut.append("--scale=0.5")
    if es:
        komut.append(f"--concurrency={es}")
    t = time.time()
    subprocess.run(komut, cwd=O.REMOTION, check=True)
    return time.time() - t


def main():
    ap = argparse.ArgumentParser(description="x-animasyon: JSON -> video + ses + ölçüm")
    ap.add_argument("json")
    ap.add_argument("--oran", choices=["16x9", "9x16", "ikisi"], default="16x9")
    ap.add_argument("--ad", help="çıktı adı (varsayılan: JSON dosyasının adı)")
    ap.add_argument("--cikti", default=str(O.KOK / "calisma" / "x-animasyon"))
    ap.add_argument("--lufs", type=float, default=-26.0, help="-26 konuşmanın altında; tek başına video için -18")
    ap.add_argument("--muziksiz", action="store_true")
    ap.add_argument("--taslak", action="store_true", help="yarım boy, sessiz; yalnız temas sayfası")
    ap.add_argument("--es", type=int, help="Remotion eşzamanlılığı (varsayılan: çekirdeklerin yarısı)")
    a = ap.parse_args()

    json_yol = pathlib.Path(a.json).resolve()
    js = O.oku(json_yol)
    kontrol(js)
    npx = hazirlik()
    cikti = pathlib.Path(a.cikti).resolve()
    cikti.mkdir(parents=True, exist_ok=True)
    ad = a.ad or json_yol.stem
    oranlar = ["16x9", "9x16"] if a.oran == "ikisi" else [a.oran]

    import ses as SES  # numpy burada gerekli

    ozet = []
    for oran in oranlar:
        kimlik, fps, _, _ = O.ORANLAR[oran]
        on = f"{ad}-{oran}" + ("-taslak" if a.taslak else "")
        sessiz = cikti / f"{on}-sessiz.mp4"
        print(f"\n== {kimlik}: render ({O.toplam_sn(js['sahneler'], fps):.2f} sn, {fps} fps)")
        sn = render(npx, kimlik, json_yol, sessiz, a.taslak, a.es)
        print(f"   render {sn:.1f} sn")
        son = sessiz
        if not a.taslak:
            son = cikti / f"{on}.mp4"
            vb = O.video_bilgi(sessiz)
            r = SES.uret(js, fps, cikti / f"{on}.wav", a.lufs, muzik=not a.muziksiz, sure=vb["v_sure"])
            SES.mux(sessiz, cikti / f"{on}.wav", son)
            (cikti / f"{on}.wav").unlink()
            print(f"   ses {r['I']:.1f} LUFS · {r['kesim']} whoosh · {r['harf']} tuş")
        subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("olc.py")), str(son), "--json", str(json_yol)],
                       check=True)
        ozet.append(f"{oran}: {son}  (render {sn:.1f} sn)")
    print("\n" + "\n".join(ozet))


if __name__ == "__main__":
    main()
