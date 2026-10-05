import React, { createContext, useContext } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { MONO, SANS, SERIF } from "./fontlar";

// ---------------------------------------------------------------- tema
export const VARSAYILAN_TEMA = {
  zemin: "#111113",
  panel: "#18191c",
  kenar: "#2a2b30",
  cizgi: "#2f3036",
  yazi: "#ece7df",
  soluk: "#8b8883",
  koyu: "#55534f",
  vurgu: "#38bdf8", // gök mavisi: tek vurgu rengi
  olumlu: "#6ee7a8",
  seri: ["#3fb4a2", "#4b84e0", "#9a6be0", "#e88a3a", "#e2506a", "#c9b458"],
};
export type Tema = typeof VARSAYILAN_TEMA;
export const TemaBag = createContext<Tema>(VARSAYILAN_TEMA);
export const useTema = () => useContext(TemaBag);

// ---------------------------------------------------------------- düzen (16:9 / 9:16)
/**
 * Yerleşim ölçüleri iki yön için ayrı. Dikeyde platform arayüzü (Reels/Shorts): üstte ~190 px,
 * altta ~520 px ve sağ alt köşe butonlar — içerik y 300..1320 arasında, x 72..1008.
 */
export const useDuzen = () => {
  const { width, height, fps } = useVideoConfig();
  const dikey = height > width;
  return dikey
    ? { dikey, W: width, H: height, fps, x0: 72, x1: width - 72, ust: 300, alt: 1320, cerceveUst: 190, cerceveAlt: 550 }
    : { dikey, W: width, H: height, fps, x0: 150, x1: width - 150, ust: 140, alt: 960, cerceveUst: 46, cerceveAlt: 46 };
};
export type Duzen = ReturnType<typeof useDuzen>;

// ---------------------------------------------------------------- zaman yardımcıları
export const kolay = Easing.bezier(0.16, 1, 0.3, 1);

/** f karesinde, `at` saniyesinde başlayıp `d` saniye süren 0->1 giriş. */
export const useAc = () => {
  const { fps } = useVideoConfig();
  return (f: number, at: number, d = 0.45) =>
    interpolate(f, [at * fps, (at + d) * fps], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: kolay,
    });
};

// ---------------------------------------------------------------- metin
/** `*kelime*` -> vurgu. serif=true: italik + vurgu rengi; değilse yalnız renk. */
export const Vurgulu: React.FC<{ metin: string; serif?: boolean }> = ({ metin, serif = true }) => {
  const t = useTema();
  const parca = metin.split("*");
  return (
    <>
      {parca.map((p, i) =>
        i % 2 === 1 ? (
          <span key={i} style={{ fontStyle: serif ? "italic" : "normal", color: t.vurgu }}>
            {p}
          </span>
        ) : (
          <React.Fragment key={i}>{p}</React.Fragment>
        )
      )}
    </>
  );
};

/** Vurgu işaretleri hariç karakter sayısı (boyut kestirimi için). */
export const uzunluk = (s: string) => Array.from(s.replace(/\*/g, "")).length;

/**
 * Satıra sığan yazı boyu. Ölçüm yerine ortalama harf genişliği kestirimi (deterministik,
 * font yüklenmeden önce de aynı sonucu verir). oran: harf genişliği / boy.
 * `enAz` verilirse boy onun altına inmez, satır kırılır (dikeyde okunurluk için).
 */
export const sigdir = (taban: number, metinler: string[], genislik: number, oran = 0.46, enAz = 0) => {
  const n = Math.max(1, ...metinler.map(uzunluk));
  return Math.max(enAz, Math.min(taban, Math.floor(genislik / (n * oran))));
};

/** Ölçüldü (1920 genişlikte): Newsreader 0.38-0.45 (harfe göre), Inter kalın ~0.58, Inter rakam ~0.62 em/harf. */
export const ORAN = { serif: 0.46, sans: 0.6, rakam: 0.62 };

export const Mono: React.FC<{
  children: React.ReactNode;
  renk?: string;
  boy?: number;
  style?: React.CSSProperties;
}> = ({ children, renk, boy = 19, style }) => {
  const t = useTema();
  return (
    <span
      style={{
        fontFamily: MONO,
        fontWeight: 500,
        fontSize: boy,
        letterSpacing: boy * 0.24,
        textTransform: "uppercase",
        color: renk ?? t.soluk,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </span>
  );
};

/** Serif başlık satırı: maskenin altından yükselir. `at` saniye (sahne içi). */
export const SerifSatir: React.FC<{
  at: number;
  boy: number;
  children: React.ReactNode;
  hiza?: "left" | "center";
}> = ({ at, boy, children, hiza = "left" }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const v = ac(f, at, 0.6);
  const t = useTema();
  return (
    <div style={{ overflow: "hidden", paddingBottom: boy * 0.16, marginBottom: -boy * 0.1 }}>
      <div
        style={{
          transform: `translateY(${(1 - v) * 110}%)`,
          fontFamily: SERIF,
          fontWeight: 400,
          fontSize: boy,
          lineHeight: 1.06,
          letterSpacing: -boy * 0.03,
          color: t.yazi,
          textAlign: hiza,
        }}
      >
        {children}
      </div>
    </div>
  );
};

/** Sol üstte başlık bloğu (satırlar sırayla yükselir). */
export const Baslik: React.FC<{ satirlar: string[]; boy?: number; at?: number }> = ({ satirlar, boy, at = 0.05 }) => {
  const d = useDuzen();
  const taban = boy ?? (d.dikey ? 86 : 80);
  const b = sigdir(taban, satirlar, d.x1 - d.x0, ORAN.serif, d.dikey ? 68 : 0);
  return (
    <div style={{ position: "absolute", left: d.x0, top: d.ust, width: d.x1 - d.x0 }}>
      {satirlar.map((s, i) => (
        <SerifSatir key={i} at={at + 0.13 * i} boy={b}>
          <Vurgulu metin={s} />
        </SerifSatir>
      ))}
    </div>
  );
};

export const Sayi: React.FC<{ children: React.ReactNode; boy: number; renk?: string; style?: React.CSSProperties }> = ({
  children,
  boy,
  renk,
  style,
}) => {
  const t = useTema();
  return (
    <div
      style={{
        fontFamily: SANS,
        fontWeight: 700,
        fontSize: boy,
        letterSpacing: -boy * 0.04,
        lineHeight: 1,
        color: renk ?? t.yazi,
        fontVariantNumeric: "tabular-nums",
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const sayiYaz = (x: number, ondalik = 0) =>
  x.toLocaleString("tr-TR", { minimumFractionDigits: ondalik, maximumFractionDigits: ondalik });
