"""Reels projesi: kurgu planı + döküm -> çıktı zaman ekseni, senaryodaki kelime çıpaları, altyazı grupları.

Girdiler (hepsi proje klasöründe, `calisma/reels/<ad>/`):
    kaynak.json      yatay-kurgu `dokum` yazar: {"video": ...}
    transkript.json  yatay-kurgu `dokum` yazar: {"words": [{"start", "end", "word"}]} (kaynak saniyesi)
    plan.json        yatay-kurgu `kurgu` yazar: {"fps", "parcalar": [{"in", "out", "hiz", "zoom", "kelimeler"}]}
    senaryo.json     Claude yazar: hangi kart hangi KELİMEDE girer (saniye değil)

Zaman ızgarası yatay-kurgu ile aynıdır: parçanın başı kareye yuvarlanır, süresi tam kare sayısıdır,
sesi kare x (48000/fps) örnektir. Böylece altyazı, kart ve ses aynı eksende kalır.
"""
from __future__ import annotations

import json
import pathlib
import re

SR = 48000


def json_oku(yol: pathlib.Path, varsayilan=None):
    if not yol.exists():
        return varsayilan
    with open(yol, encoding="utf-8-sig") as f:
        return json.load(f)


def json_yaz(yol: pathlib.Path, veri) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=1), "utf-8")


def norm(w: str) -> str:
    """Türkçe küçük harf, noktalama ve kesme işareti atılır: "Effort'u," -> "effortu"."""
    w = w.replace("İ", "i").replace("I", "ı").lower().replace("’", "'")
    return re.sub(r"[^\wçğıöşüâîû]", "", w)


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def kareye(i: float, o: float, hiz: float, fps: int) -> tuple[float, int]:
    """yatay-kurgu ile aynı: parçanın kareye yuvarlanmış başı ve çıktıdaki kare sayısı."""
    return round(i * fps) / fps, max(1, round((o - i) / hiz * fps))


class SenaryoHatasi(SystemExit):
    pass


class Proje:
    def __init__(self, dizin, senaryo: bool = True):
        self.d = pathlib.Path(dizin).resolve()
        self.ad = self.d.name
        kaynak = json_oku(self.d / "kaynak.json")
        plan = json_oku(self.d / "plan.json")
        tr = json_oku(self.d / "transkript.json")
        if not (kaynak and plan and tr):
            raise SystemExit(f"{self.d}: kaynak.json / plan.json / transkript.json eksik. Önce: reels.py dokum {self.d} --video <kayit>")
        self.video = kaynak["video"]
        self.fps = int(plan["fps"])
        self.pp = plan["parcalar"]
        self.ws = tr["words"]
        # --- zaman ekseni
        self.parca_bas, self.parca_kare, n = [], [], 0
        for p in self.pp:
            ia, k = kareye(p["in"], p["out"], p.get("hiz", 1), self.fps)
            p["_ia"] = ia
            self.parca_bas.append(n)
            self.parca_kare.append(k)
            n += k
        self.konusma_kare = n
        self.sen = json_oku(self.d / "senaryo.json") if senaryo else None
        kuyruk = float((self.sen or {}).get("kuyruk", 0.0))
        self.kuyruk_kare = int(round(kuyruk * self.fps))
        self.toplam_kare = n + self.kuyruk_kare
        self.sure = self.toplam_kare / self.fps
        self.kelimeler = self._kelimeler()
        self.V = []
        if self.sen:
            self._senaryo_coz()
            self.gruplar = self._altyazi_gruplari()

    # ------------------------------------------------------------------ eksen
    def kare_kaynagi(self, n: int) -> tuple[int, float, float]:
        """Çıktı karesi n -> (parça no, kaynak saniyesi, yakınlaşma). Kuyrukta son kare tekrarlanır."""
        if n >= self.konusma_kare:
            k = len(self.pp) - 1
            j = self.parca_kare[k] - 1
        else:
            k = max(i for i, b in enumerate(self.parca_bas) if b <= n)
            j = n - self.parca_bas[k]
        p = self.pp[k]
        return k, p["_ia"] + j * p.get("hiz", 1) / self.fps, float(p.get("zoom", 1.0))

    def cikti_zamani(self, x: float) -> float | None:
        for k, p in enumerate(self.pp):
            if p["in"] <= x < p["out"]:
                return self.parca_bas[k] / self.fps + max(0.0, (x - p["_ia"]) / p.get("hiz", 1))
        return None

    def _kelimeler(self) -> list[dict]:
        """Kurguda KALAN kelimeler, çıktı zamanıyla. Plan parçası kelime listesi taşıyorsa o kullanılır."""
        out = []
        for k, p in enumerate(self.pp):
            t0 = self.parca_bas[k] / self.fps
            son = t0 + self.parca_kare[k] / self.fps
            idx = p.get("kelimeler")
            if idx is None:
                idx = [i for i, w in enumerate(self.ws) if p["in"] <= w["start"] < p["out"]]
            for i in idx:
                w = self.ws[i]
                s = t0 + max(0.0, (w["start"] - p["_ia"]) / p.get("hiz", 1))
                e = t0 + max(0.0, (w["end"] - p["_ia"]) / p.get("hiz", 1))
                yazi = w["word"].strip()
                if not yazi:
                    continue
                ek = yazi[0] in "'’" or (yazi[0] == "." and yazi[1:2].isalnum())
                if ek and out and out[-1]["parca"] == k:
                    # Whisper eki ya da dosya uzantısını ayrı yazabiliyor ("effort 'unu", "CLAUDE .md"):
                    # önceki kelimeye yapıştır (yoksa altyazıda "CLAUDE .md" çıkıyor, vurgu da tutmuyordu)
                    o = out[-1]
                    o["word"] += ("'" if yazi[0] in "'’" else yazi[0]) + yazi[1:]
                    o["n"] = norm(o["word"])
                    o["end"] = round(min(max(e, o["start"] + 0.05), son), 3)
                    continue
                out.append({"i": i, "word": yazi, "n": norm(yazi), "start": round(min(s, son), 3),
                            "end": round(min(max(e, s + 0.05), son), 3), "parca": k})
        out.sort(key=lambda w: w["start"])
        return out

    # ------------------------------------------------------------------ çıpa
    def bul(self, ifade: str, bas: float, kac: int = 1, kim: str = "") -> float:
        """`ifade`yi (bir ya da birkaç kelime; her biri kelimenin BAŞI) `bas` saniyesinden sonra arar."""
        hedef = [norm(x) for x in ifade.split() if norm(x)]
        if not hedef:
            raise SenaryoHatasi(f"{kim}: boş çıpa '{ifade}'")
        ws = self.kelimeler
        bulunan = 0
        for a in range(len(ws)):
            if ws[a]["start"] < bas - 0.05:
                continue
            if all(a + j < len(ws) and ws[a + j]["n"].startswith(h) for j, h in enumerate(hedef)):
                bulunan += 1
                if bulunan == kac:
                    return ws[a]["start"]
        sonraki = " ".join(w["word"] for w in ws if w["start"] >= bas - 0.05)[:260]
        raise SenaryoHatasi(f"{kim}: '{ifade}' ({kac}. geçiş) {mmss(bas)} sonrasında bulunamadı.\n"
                            f"  O andan sonra söylenenler: {sonraki} …\n"
                            f"  Çıpa döküm kelimesinin BAŞI olmalı (reels.py kelimeler ile bak).")

    def _cipa(self, spec: dict, bas: float, kim: str) -> float:
        if spec.get("kelime"):
            return self.bul(spec["kelime"], bas, int(spec.get("kac", 1)), kim) + float(spec.get("ofs", 0.0))
        return bas + float(spec.get("ofs", 0.0))

    def _senaryo_coz(self) -> None:
        vs = self.sen.get("vuruslar") or []
        if not vs:
            raise SenaryoHatasi("senaryo.json: 'vuruslar' boş")
        imlec = 0.0
        for n, v in enumerate(vs):
            kim = f"vuruş {n + 1}"
            if n == 0 and not v.get("kelime"):
                t = 0.0
            else:
                t = self._cipa(v, imlec, kim)
            if n == 0:
                if t > 0.8:
                    print(f"  not: ilk vuruşun çıpası {t:.2f} sn'de; video yine de 0'da bu vuruşla açılır")
                t = 0.0
            if t < imlec - 1e-6:
                raise SenaryoHatasi(f"{kim}: zamanı ({t:.2f}) bir önceki vuruştan önce; sıra bozuk")
            v["_t"] = t
            imlec = t
            kart = v.get("kart")
            v["_duzen"] = v.get("duzen") or ("bol" if kart else "yuz")
            if v["_duzen"] not in ("bol", "yuz", "grafik"):
                raise SenaryoHatasi(f"{kim}: duzen '{v['_duzen']}' (bol | yuz | grafik)")
            if v["_duzen"] in ("bol", "grafik") and not kart:
                raise SenaryoHatasi(f"{kim}: '{v['_duzen']}' düzeni bir kart ister")
            if kart:
                kart["_t"] = t
                self._kart_coz(kart, t, kim)
        for n, v in enumerate(vs):
            v["_bit"] = vs[n + 1]["_t"] if n + 1 < len(vs) else self.sure
            kart = v.get("kart")
            if kart:
                for o in self._ogeler(kart):
                    if o.get("_t") is not None and o["_t"] >= v["_bit"]:
                        print(f"  UYARI: vuruş {n + 1} ({kart.get('tur')}): '{o.get('yazi', '')[:30]}' {o['_t']:.2f} sn'de, "
                              f"kart {v['_bit']:.2f}'de değişiyor -> görünmeyecek")
        self.V = vs

    @staticmethod
    def _ogeler(kart: dict) -> list[dict]:
        out = []
        for ad in ("satirlar", "maddeler", "mesajlar"):
            out += [o for o in kart.get(ad, []) if isinstance(o, dict)]
        return out

    def _kart_coz(self, kart: dict, t: float, kim: str) -> None:
        """Kart içindeki `*_kelime` -> `*_t`; satır/madde/mesaj `kelime` -> `_t` (sırayla, karttan sonra)."""
        imlec = t
        for k in list(kart):
            if k.endswith("_kelime") and kart[k]:
                kart[k[:-7] + "_t"] = self.bul(kart[k], t, 1, f"{kim} {k}")
        for ad in ("satirlar", "maddeler", "mesajlar"):
            liste = kart.get(ad)
            if not liste:
                continue
            for i, o in enumerate(liste):
                if isinstance(o, str):
                    o = liste[i] = {"yazi": o}
                if o.get("kelime"):
                    o["_t"] = self._cipa(o, imlec, f"{kim} {ad}[{i}]")
                    imlec = o["_t"]
                else:
                    o["_t"] = max(t + 0.25 + 0.12 * i, imlec + (0.12 if i else 0.0)) + float(o.get("ofs", 0.0))
                    imlec = o["_t"]
                for k in list(o):
                    if k.endswith("_kelime") and o[k]:
                        o[k[:-7] + "_t"] = self.bul(o[k], o["_t"], 1, f"{kim} {ad}[{i}] {k}")

    def vurus(self, t: float) -> dict:
        j = 0
        for n, v in enumerate(self.V):
            if v["_t"] <= t + 1e-9:
                j = n
        return self.V[j]

    # ------------------------------------------------------------------ altyazı
    def _altyazi_gruplari(self) -> list[dict]:
        """1-2 kelimelik gruplar: kısa kelime sonrakine eklenir, noktalama ve 0,35 sn'lik boşluk grubu böler.
        Kelimeler söylendikçe belirir; grup bir sonraki grup başlayana (en çok son kelime + 0,3 sn) kadar durur."""
        duzelt = {norm(k): v for k, v in (self.sen.get("altyazi_duzelt") or {}).items()}
        ws = []
        for w in self.kelimeler:
            yazi = duzelt.get(w["n"], w["word"])
            if not yazi:
                continue
            yazi = yazi.rstrip(".,;:…")
            if not yazi:
                continue
            ws.append({**w, "yazi": yazi, "n": norm(yazi), "son_nokta": w["word"].strip()[-1:] in ".?!…,;:"})
        gruplar, g = [], []
        for n, w in enumerate(ws):
            if g and (w["start"] - g[-1]["end"] > 0.35):
                gruplar.append(g)
                g = []
            g.append(w)
            metin = " ".join(x["yazi"] for x in g)
            if len(g) >= 2 or len(metin) >= 11 or w["son_nokta"]:
                gruplar.append(g)
                g = []
        if g:
            gruplar.append(g)
        out = []
        for n, gr in enumerate(gruplar):
            son = gr[-1]["end"] + 0.3
            if n + 1 < len(gruplar):
                son = min(son, gruplar[n + 1][0]["start"])
            son = max(son, gr[-1]["end"])
            out.append({"bas": gr[0]["start"], "son": min(son, self.konusma_kare / self.fps),
                        "kel": [(x["yazi"], x["start"], x["n"]) for x in gr]})
        return out

    def grup(self, t: float) -> dict | None:
        for g in self.gruplar:
            if g["bas"] <= t < g["son"]:
                return g
        return None
