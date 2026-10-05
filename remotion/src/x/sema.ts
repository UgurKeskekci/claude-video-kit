import { z } from "zod";
import { zColor } from "@remotion/zod-types";

/**
 * x-animasyon sahne dili. Hikâye JSON olarak yazılır, her sahne bir `tur` taşır.
 * Metinde `*kelime*` = vurgu (serifte italik + vurgu rengi, diğer yazılarda yalnız renk).
 * Süreler SANİYE; kare sayısı fps'ten hesaplanır (16:9 60 fps, 9:16 30 fps).
 */

const ortak = {
  sure: z.number().min(0.5).max(60).describe("Sahnenin süresi (sn)"),
  bolum: z.string().optional().describe("Sağ üstte '01 — BÖLÜM'. Verilmezse önceki bölüm sürer."),
};
const satirlar = z.array(z.string()).min(1).max(4).describe("Serif başlık satırları; *vurgu*");

export const baslikSema = z.object({
  tur: z.literal("baslik"),
  ...ortak,
  ust: z.string().optional().describe("Başlığın üstünde küçük mono etiket"),
  satirlar,
});

export const yaziSema = z.object({
  tur: z.literal("yazi"),
  ...ortak,
  satirlar: satirlar.optional(),
  ust: z.string().optional().describe("Panelin üst etiketi (varsayılan: istem)"),
  metin: z.string().min(1).max(160).describe("Harf harf yazılan metin (klavye sesi buna göre)"),
});

export const sayacSema = z.object({
  tur: z.literal("sayac"),
  ...ortak,
  ust: z.string().optional(),
  deger: z.number(),
  baslangic: z.number().optional().describe("Sayma buradan başlar (varsayılan 0)"),
  ondalik: z.number().int().min(0).max(3).optional(),
  onek: z.string().optional().describe("Türkçede yüzde önde: '%'"),
  sonek: z.string().optional().describe("Birim: ' sn', ' TL', '×'"),
  alt: z.string().optional().describe("Sayının altındaki serif cümle"),
});

export const olcerSema = z.object({
  tur: z.literal("olcer"),
  ...ortak,
  satirlar,
  seviyeler: z
    .array(z.object({ ad: z.string(), etiket: z.string().optional() }))
    .min(2)
    .max(6)
    .describe("Soldan sağa yükselen seviyeler; sırayla dolar"),
});

export const sutunlarSema = z.object({
  tur: z.literal("sutunlar"),
  ...ortak,
  satirlar,
  ogeler: z
    .array(z.object({ ad: z.string(), deger: z.number(), etiket: z.string().optional() }))
    .min(2)
    .max(6),
  ondalik: z.number().int().min(0).max(3).optional(),
  onek: z.string().optional(),
  sonek: z.string().optional(),
  not: z.string().optional().describe("Sağ üstte küçük mono not: ölçüt, kaynak"),
});

const kartSema = z.object({
  ad: z.string(),
  ust: z.string().optional().describe("Değerin üstündeki mono etiket"),
  deger: z.string().describe("Biçimlenmiş değer: '$0,50', '41 sn'"),
  altEtiket: z.string().optional(),
  alt: z.string().optional(),
});

export const karsilastirmaSema = z.object({
  tur: z.literal("karsilastirma"),
  ...ortak,
  satirlar,
  a: kartSema,
  b: kartSema,
  fark: z
    .object({ deger: z.string(), etiket: z.string().optional(), alt: z.string().optional() })
    .optional(),
});

export const listeSema = z.object({
  tur: z.literal("liste"),
  ...ortak,
  satirlar,
  ogeler: z.array(z.string()).min(2).max(5),
});

export const soruSema = z.object({
  tur: z.literal("soru"),
  ...ortak,
  satirlar,
  alt: z.string().optional().describe("Altta mono çağrı: 'yorumlara yaz'"),
});

export const sahneSema = z.discriminatedUnion("tur", [
  baslikSema,
  yaziSema,
  sayacSema,
  olcerSema,
  sutunlarSema,
  karsilastirmaSema,
  listeSema,
  soruSema,
]);

export const temaSema = z.object({
  zemin: zColor().optional(),
  yazi: zColor().optional(),
  soluk: zColor().optional(),
  vurgu: zColor().optional(),
  seri: z.array(z.string()).optional().describe("Ölçer ve sütun renkleri, sırayla"),
});

export const xSema = z.object({
  marka: z.string().describe("Sol üstteki marka adı"),
  etiket: z.string().optional().describe("Sağ altta küçük not, ör. 'örnek veri'"),
  tema: temaSema.optional(),
  sahneler: z.array(sahneSema).min(1),
});

export type Sahne = z.infer<typeof sahneSema>;
export type XProps = z.infer<typeof xSema>;
