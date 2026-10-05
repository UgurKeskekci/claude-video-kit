"""yatay-kurgu skill'inin kesim kurallarını kilitleyen testler.

Bağımlılık yok (numpy, ffmpeg, Whisper istemez):  python3 tests/test_kesim.py
Bunlar derleme hatası vermeyen hatalar: bozulduklarında video yine çıkar ama yanlış kesilir.
"""
from __future__ import annotations

import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / ".claude" / "skills" / "yatay-kurgu" / "araclar"))

import kesim  # noqa: E402
from kesim import Enerji  # noqa: E402


def kelimeler(metin: str, bas: float = 0.0, uzun: float = 0.3, ara: float = 0.05) -> list[dict]:
    out, t = [], bas
    for w in metin.split():
        out.append({"start": round(t, 3), "end": round(t + uzun, 3), "word": " " + w})
        t += uzun + ara
    return out


def zarf(sure: float, sesli: list[tuple[float, float]], seviye: float = -20.0, sessiz: float = -80.0) -> Enerji:
    """sure saniyelik yapay zarf: verilen aralıklar `seviye` dB, gerisi `sessiz`."""
    db = [sessiz] * int(round(sure * 100))
    for a, b, *s in [(*x,) for x in sesli]:
        for i in range(int(round(a * 100)), min(len(db), int(round(b * 100)))):
            db[i] = s[0] if s else seviye
    return Enerji(db)


class TestNorm(unittest.TestCase):
    def test_noktalama_ve_harf(self):
        self.assertEqual(kesim.norm(" Bu,"), "bu")
        self.assertEqual(kesim.norm("İşte"), "işte")
        self.assertEqual(kesim.norm("IŞIK"), "ışık")
        self.assertEqual(kesim.norm("Claude'un"), "claude")

    def test_sayi_karsilastirilmaz(self):
        # harfiyen döküm "5.5"i "5" + ".5" yazıyor; tekrar sanılıp "5" atılıyordu
        self.assertEqual(kesim.norm("5"), "")
        self.assertEqual(kesim.norm(".5"), "")
        self.assertEqual(kesim.norm("%10"), "")


class TestTekrar(unittest.TestCase):
    def test_ilk_kopya_atilir(self):
        at, _ = kesim.tekrar_bul(kelimeler("bu işi bu işi beş"))
        self.assertEqual(at, {0, 1})

    def test_uc_kelime(self):
        at, _ = kesim.tekrar_bul(kelimeler("şimdi size göstereyim şimdi size göstereyim tamam"))
        self.assertEqual(at, {0, 1, 2})

    def test_serbest_kelime_atilmaz(self):
        at, _ = kesim.tekrar_bul(kelimeler("çok çok güzel"))
        self.assertEqual(at, set())

    def test_uzak_kopya_tekrar_degil(self):
        ws = kelimeler("bunu") + kelimeler("bunu yaptık", bas=2.5)
        at, _ = kesim.tekrar_bul(ws)
        self.assertEqual(at, set())

    def test_sayi_tekrar_sayilmaz(self):
        at, _ = kesim.tekrar_bul(kelimeler("5 .5 5 .5 geldi"))
        self.assertEqual(at, set())

    def test_aday(self):
        _, aday = kesim.tekrar_bul(kelimeler("videoda gene daha önceki videoda anlattım"))
        self.assertEqual(len(aday), 1)
        self.assertTrue(aday[0].startswith("0.00: videoda gene"))

    def test_otomatik_aralik_ikinci_kopyanin_basina_kadar(self):
        ws = kelimeler("bu işi bu işi beş")
        idx, aralik, _ = kesim.otomatik_tekrar(ws)
        self.assertEqual(idx, [0, 1])
        self.assertEqual(aralik, [(ws[0]["start"], ws[2]["start"])])

    def test_cumle_sonu_ve_korunacak(self):
        idx, _, _ = kesim.otomatik_tekrar(kelimeler("yaptık. yaptık ki"))
        self.assertEqual(idx, [])
        ws = kelimeler("bilgi bilgi bilgi")
        self.assertTrue(kesim.otomatik_tekrar(ws)[0])
        self.assertEqual(kesim.otomatik_tekrar(ws, korunacak=[(0.0, 5.0, "vurgu")])[0], [])


class TestEnerji(unittest.TestCase):
    def test_yuzdelik_numpy_ile_ayni(self):
        self.assertAlmostEqual(kesim.yuzdelik([1, 2, 3, 4], 50), 2.5)
        self.assertAlmostEqual(kesim.yuzdelik([1, 2, 3, 4], 10), 1.3)

    def test_esik_gurultu_kapili(self):
        en = Enerji([-80.0] * 50 + [-20.0] * 50)
        self.assertAlmostEqual(en.esik, -50.0)      # konuşma - 30 dB

    def test_esik_gurultulu_oda(self):
        en = Enerji([-40.0] * 50 + [-20.0] * 50)
        self.assertAlmostEqual(en.esik, -32.0)      # taban + 8 dB

    def test_kosular_ve_konusma(self):
        en = Enerji([-80.0] * 50 + [-20.0] * 50)
        self.assertEqual(en.kosular(0, 1, 0.3), [(0.0, 0.5)])
        self.assertEqual(en.konusma(0, 1, 0.3), [(0.5, 1.0)])
        self.assertEqual(en.kosular(0, 1, 0.6), [])

    def test_sessiz_kare(self):
        db = [-30.0] * 100
        db[57] = -70.0
        en = Enerji(db, esik=-50)
        self.assertEqual(en.sessiz_kare(0.5), 0.57)
        self.assertEqual(en.sessiz_kare(0.5, pay=0.05), 0.45)   # dip pencere dışında: ilk en kısık


class TestParcalar(unittest.TestCase):
    def setUp(self):
        self.en = zarf(5, [(1.0, 1.8), (2.5, 3.2)])
        self.ws = [{"start": 1.0, "end": 1.8, "word": " merhaba"}, {"start": 2.5, "end": 3.2, "word": " dünya."}]

    def test_bas_ve_son_payi(self):
        pp = kesim.parcalar(self.ws, self.en, 0, 5, [])
        # baş -0,06; cümle içi +0,12; cümle sonu +0,28
        self.assertEqual(pp, [[0.94, 1.92], [2.44, 3.48]])

    def test_atilan_kelimenin_bolgesi_gider(self):
        pp = kesim.parcalar(self.ws, self.en, 0, 5, [(2.4, 3.3)])
        self.assertEqual(pp, [[0.94, 1.92]])

    def test_erken_damgali_kelime_atilmaz(self):
        # aralık sesin başladığı yerde bitiyor, kelimenin damgası aralığa taşıyor: ortası dışarıda -> kalır
        self.assertEqual(kesim.parcalar(self.ws, self.en, 0, 5, [(0.0, 1.1)]), [[0.94, 1.92], [2.44, 3.48]])
        self.assertTrue(kesim.atilmis({"start": 1.0, "end": 1.4}, [(0.0, 1.25)]))
        self.assertFalse(kesim.atilmis({"start": 1.0, "end": 1.6}, [(0.0, 1.25)]))

    def test_aralik_icindeki_bolge_komsu_damgaya_ragmen_gider(self):
        # "Pardon." aralığın içinde; sonraki tutulan kelime erken damgalı ve ±0,3 payla ona değiyor
        en = zarf(6, [(1.0, 2.0), (2.3, 2.7), (2.95, 3.8)])
        ws = [{"start": 1.0, "end": 2.0, "word": " yanlış"}, {"start": 2.3, "end": 2.6, "word": " pardon."},
              {"start": 2.75, "end": 3.8, "word": " doğrusu"}]
        pp = kesim.parcalar(ws, en, 0, 6, [(0.9, 2.85)])
        self.assertEqual(len(pp), 1)
        self.assertGreaterEqual(pp[0][0], 2.7)

    def test_kisa_bosluk_bolmez(self):
        en = zarf(5, [(1.0, 1.8), (1.9, 2.6)])
        ws = [{"start": 1.0, "end": 1.8, "word": " bir"}, {"start": 1.9, "end": 2.6, "word": " iki"}]
        self.assertEqual(len(kesim.parcalar(ws, en, 0, 5, [])), 1)

    def test_kisa_ada_atilir(self):
        en = zarf(5, [(1.0, 1.8), (3.0, 3.04)])
        ws = [{"start": 1.0, "end": 1.8, "word": " bir"}]
        self.assertEqual(kesim.parcalar(ws, en, 0, 5, []), [[0.94, 1.92]])

    def test_yazilmamis_soz_komsulari_tutuluyorsa_kalir(self):
        ws = [{"start": 1.0, "end": 1.5, "word": " bir"}, {"start": 2.4, "end": 2.9, "word": " üç"}]
        guclu = zarf(5, [(1.0, 1.5), (1.8, 2.1), (2.4, 2.9)])
        pp = kesim.parcalar(ws, guclu, 0, 5, [])
        self.assertEqual(len(pp), 3)
        self.assertTrue(pp[1][0] <= 1.8 and pp[1][1] >= 2.1)
        zayif = zarf(5, [(1.0, 1.5), (1.8, 2.1, -45.0), (2.4, 2.9)])
        self.assertEqual(len(kesim.parcalar(ws, zayif, 0, 5, [])), 2)

    def test_pay_komsuya_tasmaz(self):
        en = zarf(5, [(1.0, 1.5), (1.7, 2.2)])
        ws = [{"start": 1.0, "end": 1.5, "word": " bir."}, {"start": 1.7, "end": 2.2, "word": " iki"}]
        pp = kesim.parcalar(ws, en, 0, 5, [(1.6, 2.3)])
        self.assertEqual(len(pp), 1)
        self.assertLess(pp[0][1], 1.7)      # +0,28 cümle sonu payı ikinci kelimenin sesine girmez

    def test_bas_sabitle_ve_uzat(self):
        self.assertEqual(kesim.bas_sabitle(self.en, 1.0), 0.75)
        self.assertEqual(kesim.bas_sabitle(self.en, 0.0), 0.0)
        self.assertAlmostEqual(kesim.uzat(self.en, 3.0), 3.55)     # sesin bitişi 3,2 + 0,35
        self.assertAlmostEqual(kesim.uzat(self.en, 4.9), 5.0)      # kayıt sonunu aşmaz


class TestHizlandir(unittest.TestCase):
    def test_uzun_sessizlik_4x_kisa_2x(self):
        en = zarf(30, [(0, 5), (15, 20), (23, 30)])
        pp = kesim.hizlandir(en, [], [[0, 30]])
        self.assertEqual(pp, [[0, 5.35, 1], [5.35, 14.65, 4], [14.65, 20.35, 1], [20.35, 22.65, 2], [22.65, 30, 1]])

    def test_kelimenin_ustu_hizlanmaz(self):
        # sessiz koşunun içine damgalanmış kelime koşuyu böler; kelime normal hızda kalır
        en = zarf(30, [(0, 5), (15, 30)])
        ws = [{"start": 9.0, "end": 9.4, "word": " fısıltı"}]
        pp = kesim.hizlandir(en, ws, [[0, 30]])
        self.assertEqual(pp, [[0, 5.35, 1], [5.35, 8.55, 2], [8.55, 9.85, 1], [9.85, 14.65, 2], [14.65, 30, 1]])
        en2 = zarf(30, [(0, 5), (8, 12)])      # 3 sn'lik sessizliği kelime ikiye böler: ikisi de kısa
        self.assertEqual(kesim.hizlandir(en2, [{"start": 6.5, "end": 6.9, "word": " a"}], [[0, 12]]), [[0, 12, 1]])


class TestKareIzgarasi(unittest.TestCase):
    def test_kareye(self):
        i, n = kesim.kareye(1.234, 2.0, 1, 30)
        self.assertAlmostEqual(i, 37 / 30)
        self.assertEqual(n, 23)
        self.assertEqual(kesim.kareye(10, 14, 2, 30)[1], 60)      # 2x: 4 sn kaynak -> 2 sn

    def test_ses_ve_goruntu_kaymaz(self):
        rnd = random.Random(7)
        pp, t = [], 0.0
        for _ in range(250):
            t += rnd.uniform(0.05, 2.0)
            d = rnd.uniform(0.15, 6.0)
            pp.append({"in": round(t, 3), "out": round(t + d, 3), "hiz": rnd.choice([1, 1, 1, 2, 4])})
            t += d
        kare = sum(kesim.kareye(p["in"], p["out"], p["hiz"], 30)[1] for p in pp)
        ornek = sum(kesim.ses_araligi(p, 30)[1] for p in pp)
        self.assertEqual(ornek, kare * 1600)
        cz = kesim.zaman_cizelgesi(pp, 30)
        self.assertAlmostEqual(cz[-1] + kesim.sure(pp[-1], 30), kare / 30)

    def test_gecersiz_fps(self):
        with self.assertRaises(ValueError):
            kesim.ses_araligi({"in": 0, "out": 1}, 29)

    def test_cikti_ve_kaynak_zamani(self):
        pp = [{"in": 10.0, "out": 12.0}, {"in": 20.0, "out": 21.0}]
        self.assertAlmostEqual(kesim.cikti_zamani(11.0, pp), 1.0)
        self.assertAlmostEqual(kesim.cikti_zamani(15.0, pp), 2.0)    # atılan yer -> sonraki parçanın başı
        self.assertAlmostEqual(kesim.kaynak_zamani(2.5, pp), 20.5)


class TestGirdiler(unittest.TestCase):
    def test_gerekce_zorunlu(self):
        with self.assertRaises(ValueError):
            kesim.aralik_listesi([{"bas": 1, "son": 2}])
        with self.assertRaises(ValueError):
            kesim.aralik_listesi([{"bas": 3, "son": 2, "gerekce": "x"}])
        r = kesim.aralik_listesi([{"bas": 5, "son": 6, "gerekce": "b"}, {"bas": 1, "son": 2, "gerekce": "a"}])
        self.assertEqual(r, [(1.0, 2.0, "a"), (5.0, 6.0, "b")])

    def test_bloklar(self):
        self.assertEqual(kesim.blok_listesi(None, 60)[0]["goruntu"], "kamera")
        with self.assertRaises(ValueError):
            kesim.blok_listesi([{"bas": 0, "son": 5, "goruntu": "dikey"}], 60)

    def test_sozluk(self):
        ws = kelimeler("Cloud Code, ile kodekse kodeksler")
        out = kesim.duzelt_kelimeler(ws, [["Cloud Code", "Claude Code"], ["kodekse", "Codex'e"], ["kodeks", "Codex"]])
        self.assertEqual([w["word"] for w in out], [" Claude Code,", " ile", " Codex'e", " kodeksler"])
        self.assertEqual(out[0]["end"], ws[1]["end"])


class TestDokumParcalari(unittest.TestCase):
    def test_on_saniye_ve_sessizlikten(self):
        sesli, t = [], 0.0
        while t < 40:
            sesli.append((t, t + 3.0))
            t += 3.5
        en = zarf(40, sesli)
        pp = kesim.dokum_parcalari(en)
        self.assertTrue(all(b - a <= 10.0 + 1e-6 for a, b in pp))
        for a, _ in pp[1:]:
            self.assertLess(en.db[kesim.kare(a)], en.esik)      # sınır sessizlikte

    def test_kesintisiz_konusma_da_on_saniyeyi_gecmez(self):
        en = zarf(70, [(0, 70)], seviye=-20)
        en.esik = -50
        pp = kesim.dokum_parcalari(en)
        self.assertTrue(all(b - a <= 10.0 + 1e-6 for a, b in pp))
        self.assertAlmostEqual(pp[-1][1], 70.0)

    def test_kisa_sessizlik_yedek_sinir(self):
        # 0,3 sn'lik sessizlik yok, yalnız 0,15 sn'likler: sınır onlara oturur
        sesli, t = [], 0.0
        while t < 30:
            sesli.append((t, t + 2.85))
            t += 3.0
        en = zarf(30, sesli)
        pp = kesim.dokum_parcalari(en)
        self.assertTrue(all(b - a <= 10.0 + 1e-6 for a, b in pp))
        for a, _ in pp[1:]:
            self.assertLess(en.db[kesim.kare(a)], en.esik)

    def test_sessiz_parca_atlanir(self):
        en = zarf(40, [(0, 5)])
        pp = kesim.dokum_parcalari(en)
        self.assertTrue(all(a < 5 for a, _ in pp))


class TestPlan(unittest.TestCase):
    def setUp(self):
        sesli, ws, t = [], [], 0.5
        for n in range(12):
            sesli.append((t, t + 1.2))
            ws.append({"start": t, "end": t + 1.2, "word": f" kelime{n}."})
            t += 2.0
        self.en = zarf(26, sesli)
        self.ws = ws

    def test_bitisik_bloklar_ust_uste_binmez(self):
        bl = kesim.blok_listesi([{"bas": 0, "son": 12.1, "goruntu": "kamera"},
                                 {"bas": 12.1, "son": 26, "goruntu": "ekran"}], self.en.sure)
        pp, satir, say = kesim.plan_kur(self.ws, self.en, bl, [(4.4, 5.9, "deneme: yarım cümle")])
        for p, q in zip(pp, pp[1:]):
            self.assertLessEqual(p["out"], q["in"])
        self.assertEqual(say["elle_atma"], 1)
        self.assertEqual(say["parca"], 11)
        self.assertTrue(any("ATILDI 4.40–5.90: deneme: yarım cümle" in s for s in satir))
        self.assertAlmostEqual(say["cikti_sn"], sum(kesim.sure(p) for p in pp), places=3)
        self.assertEqual({p["gorsel"] for p in pp}, {"kamera", "ekran"})

    def test_zoom_atlamada_degisir(self):
        bl = kesim.blok_listesi(None, self.en.sure)
        pp, _, _ = kesim.plan_kur(self.ws, self.en, bl, [(4.4, 9.9, "uzun atma")])
        z = [p["zoom"] for p in pp]
        self.assertEqual(z[0], 1.06)
        i = next(k for k, p in enumerate(pp) if p["in"] > 9.9)
        self.assertNotEqual(z[i - 1], z[i])          # 5 sn atlandı -> yakınlaşma değişti


class TestDenetim(unittest.TestCase):
    def setUp(self):
        self.ws = kelimeler("bugün size yeni bir şey göstereceğim arkadaşlar", uzun=0.4, ara=0.1)
        # parça 1: bugün size yeni · parça 2: göstereceğim arkadaşlar ("bir şey" atıldı)
        self.pp = [{"in": 0.0, "out": 1.45, "etiket": "a"}, {"in": 2.5, "out": 3.5, "etiket": "a"}]

    def yeniden(self, metin):
        return kelimeler(metin, uzun=0.4, ara=0.1)

    def test_temiz(self):
        rapor, ozet = kesim.birlesim_denetle(self.pp, self.ws, self.yeniden("bugün size yeni göstereceğim arkadaşlar"))
        self.assertEqual(rapor, [])
        self.assertEqual(ozet["birlesim"], 1)

    def test_eksik(self):
        rapor, _ = kesim.birlesim_denetle(self.pp, self.ws, self.yeniden("bugün size arkadaşlar"))
        self.assertEqual(rapor[0]["eksik"], ["yeni", "göstereceğim"])

    def test_sizan(self):
        rapor, _ = kesim.birlesim_denetle(self.pp, self.ws, self.yeniden("bugün size yeni şey göstereceğim arkadaşlar"))
        self.assertEqual(rapor[0]["sizan"], ["şey"])


class TestSenkron(unittest.TestCase):
    def test_dogru_aykiri_noktaya_ragmen(self):
        nok = [(t, 3.87 + 0.00001 * t, 0.7) for t in range(15, 1500, 120)]
        nok.append((700, 4.6, 0.5))            # yanlış eşleşen pencere
        nok.append((800, 1.0, 0.1))            # güvenilmez (r düşük)
        a, b, kul = kesim.dogru_uydur(nok)
        self.assertAlmostEqual(a, 3.87, places=4)
        self.assertAlmostEqual(b, 0.00001, places=7)
        self.assertEqual(len(kul), len(nok) - 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
