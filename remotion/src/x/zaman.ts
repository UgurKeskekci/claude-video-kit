import type { Sahne } from "./sema";

/**
 * Zaman çizelgesi — TEK kaynak. Ses aracı (`.claude/skills/x-animasyon/araclar/ortak.py`)
 * aynı hesabı Python'da yapar; buradaki bir formül değişirse orası da değişmeli,
 * yoksa whoosh kesimden, klavye sesi harften kayar.
 */

/** Saniye -> kare. Math.round; Python tarafı floor(x + 0.5) kullanır (round() bankacı yuvarlaması yapar). */
export const kare = (sn: number, fps: number) => Math.round(sn * fps);

export type Zamanli = {
  sahne: Sahne;
  i: number;
  bas: number; // kare
  uz: number; // kare
  bolumNo: number;
  bolumAd: string;
};

export type Bolum = { no: number; ad: string; bas: number; bit: number };

export const zamanla = (sahneler: Sahne[], fps: number): Zamanli[] => {
  let bas = 0;
  let no = 0;
  let ad = "";
  return sahneler.map((sahne, i) => {
    if (sahne.bolum) {
      no += 1;
      ad = sahne.bolum;
    } else if (no === 0) {
      no = 1;
    }
    const uz = Math.max(1, kare(sahne.sure, fps));
    const z = { sahne, i, bas, uz, bolumNo: no, bolumAd: ad };
    bas += uz;
    return z;
  });
};

export const toplamKare = (sahneler: Sahne[], fps: number) =>
  zamanla(sahneler, fps).reduce((t, z) => t + z.uz, 0);

export const bolumler = (z: Zamanli[]): Bolum[] => {
  const out: Bolum[] = [];
  for (const s of z) {
    const son = out[out.length - 1];
    if (son && son.no === s.bolumNo) son.bit = s.bas + s.uz;
    else out.push({ no: s.bolumNo, ad: s.bolumAd, bas: s.bas, bit: s.bas + s.uz });
  }
  return out;
};

// ---- yazma ritmi (klavye sesi bununla senkron) ----
export const YAZ_BASLA = 0.55; // sn, sahnenin içinde ilk harf
const ozet = (i: number) => (((i + 1) * 2654435761) % 4294967296) / 4294967296;

/** Her harfin sahne içindeki zamanı (sn). İnsan ritmi: 55-115 ms, ara sıra kısa duraksama.
 *  Sahneye sığmazsa aralıklar orantılı kısalır (son harften sonra en az 0,9 sn kalır). */
export const yazmaZamanlari = (metin: string, sure: number): number[] => {
  const n = Array.from(metin).length;
  const ara: number[] = [];
  for (let i = 0; i < n; i++) {
    let a = 0.055 + 0.06 * ozet(i);
    if (ozet(i + 1000) < 0.07) a += 0.14;
    ara.push(a);
  }
  let toplam = 0;
  for (let i = 1; i < n; i++) toplam += ara[i];
  const pay = Math.max(0.3, sure - YAZ_BASLA - 0.9);
  const olcek = toplam > pay ? pay / toplam : 1;
  const z: number[] = [];
  let t = YAZ_BASLA;
  for (let i = 0; i < n; i++) {
    if (i > 0) t += ara[i] * olcek;
    z.push(t);
  }
  return z;
};
