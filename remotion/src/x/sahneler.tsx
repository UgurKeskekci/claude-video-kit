import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { MONO, SANS } from "./fontlar";
import {
  Baslik,
  Mono,
  ORAN,
  Sayi,
  SerifSatir,
  Vurgulu,
  sayiYaz,
  sigdir,
  uzunluk,
  useAc,
  useDuzen,
  useTema,
} from "./parcalar";
import type { Sahne } from "./sema";
import { yazmaZamanlari } from "./zaman";

type S<T extends Sahne["tur"]> = { s: Extract<Sahne, { tur: T }> };

/** İçerik alanında dikey ortalanmış sütun (başlık, sayaç, soru). */
const Orta: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const d = useDuzen();
  return (
    <div
      style={{
        position: "absolute",
        left: d.x0,
        width: d.x1 - d.x0,
        top: d.ust,
        height: d.alt - d.ust,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
      }}
    >
      {children}
    </div>
  );
};

const cik = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

// ---------------------------------------------------------------- baslik
export const BaslikSahne: React.FC<S<"baslik">> = ({ s }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const d = useDuzen();
  const g = d.x1 - d.x0;
  // dikeyde boy küçülmez, satır kırılır: telefonda okunurluk sığdırmaktan önemli
  const b1 = sigdir(d.dikey ? 150 : 180, [s.satirlar[0]], g, ORAN.serif, d.dikey ? 120 : 0);
  const b2 = sigdir(d.dikey ? 120 : 140, s.satirlar.slice(1).length ? s.satirlar.slice(1) : ["x"], g, ORAN.serif, d.dikey ? 100 : 0);
  return (
    <Orta>
      {s.ust ? (
        <div style={{ opacity: ac(f, 0.1), marginBottom: 28 }}>
          <Mono boy={d.dikey ? 21 : 19}>{s.ust}</Mono>
        </div>
      ) : null}
      {s.satirlar.map((x, i) => (
        <SerifSatir key={i} at={0.15 + 0.3 * i} boy={i === 0 ? b1 : b2} hiza="center">
          <Vurgulu metin={x} />
        </SerifSatir>
      ))}
    </Orta>
  );
};

// ---------------------------------------------------------------- yazi (klavyeyle yazılan istem)
export const YaziSahne: React.FC<S<"yazi">> = ({ s }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const harfler = Array.from(s.metin);
  const zaman = yazmaZamanlari(s.metin, s.sure);
  const sn = f / fps;
  const gorunen = zaman.filter((z) => z <= sn).length;
  const bitti = gorunen >= harfler.length;
  const imlec = !bitti || Math.floor((sn - zaman[zaman.length - 1]) / 0.5) % 2 === 0;
  const boy = d.dikey ? 48 : 56;
  const g = ac(f, 0.1, 0.5);
  const ustY = s.satirlar ? (d.dikey ? 560 : 390) : d.dikey ? 520 : 300;
  return (
    <>
      {s.satirlar ? <Baslik satirlar={s.satirlar} /> : null}
      <div
        style={{
          position: "absolute",
          left: d.x0,
          width: d.x1 - d.x0,
          top: ustY,
          opacity: g,
          transform: `translateY(${(1 - g) * 30}px)`,
          border: `1.5px solid ${t.kenar}`,
          borderRadius: 18,
          background: `${t.panel}e6`,
          padding: d.dikey ? "28px 34px 40px" : "30px 44px 44px",
          minHeight: d.dikey ? 520 : 420,
          boxSizing: "border-box",
        }}
      >
        <Mono boy={d.dikey ? 19 : 17}>{s.ust ?? "istem"}</Mono>
        <div style={{ height: 1, background: t.cizgi, margin: "20px 0 26px" }} />
        <div
          style={{
            fontFamily: MONO,
            fontWeight: 400,
            fontSize: boy,
            lineHeight: 1.35,
            color: t.yazi,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          <span style={{ color: t.vurgu }}>{"› "}</span>
          {harfler.slice(0, gorunen).join("")}
          <span
            style={{
              display: "inline-block",
              width: boy * 0.56,
              height: boy * 1.05,
              marginLeft: 2,
              verticalAlign: "text-bottom",
              background: t.vurgu,
              opacity: imlec ? 1 : 0,
            }}
          />
        </div>
      </div>
    </>
  );
};

// ---------------------------------------------------------------- sayac
export const SayacSahne: React.FC<S<"sayac">> = ({ s }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const od = s.ondalik ?? 0;
  const p = cik(f, 0.3 * fps, 1.9 * fps);
  const bas = s.baslangic ?? 0;
  const v = bas + (s.deger - bas) * p;
  const son = `${s.onek ?? ""}${sayiYaz(s.deger, od)}`;
  const g = d.x1 - d.x0;
  const boy = Math.min(d.dikey ? 280 : 300, Math.floor(g / ((uzunluk(son) + uzunluk(s.sonek ?? "") * 0.4) * ORAN.rakam)));
  const cizgi = ac(f, 1.9, 0.5);
  return (
    <Orta>
      {s.ust ? (
        <div style={{ opacity: ac(f, 0.1), marginBottom: 22 }}>
          <Mono boy={d.dikey ? 21 : 19}>{s.ust}</Mono>
        </div>
      ) : null}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "center", opacity: ac(f, 0.2, 0.3) }}>
        <Sayi boy={boy}>{`${s.onek ?? ""}${sayiYaz(v, od)}`}</Sayi>
        {s.sonek ? (
          <span style={{ fontFamily: SANS, fontWeight: 600, fontSize: boy * 0.36, color: t.soluk, marginLeft: boy * 0.05, letterSpacing: -boy * 0.01 }}>
            {s.sonek.trim()}
          </span>
        ) : null}
      </div>
      <div style={{ width: 120 * cizgi, height: 4, borderRadius: 2, background: t.vurgu, margin: `${boy * 0.12}px 0 ${boy * 0.1}px` }} />
      {s.alt ? (
        <SerifSatir at={1.3} boy={sigdir(d.dikey ? 72 : 72, [s.alt], g, ORAN.serif, d.dikey ? 56 : 0)} hiza="center">
          <Vurgulu metin={s.alt} />
        </SerifSatir>
      ) : null}
    </Orta>
  );
};

// ---------------------------------------------------------------- olcer
export const OlcerSahne: React.FC<S<"olcer">> = ({ s }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const n = s.seviyeler.length;
  const genis = d.x1 - d.x0;
  const ara = d.dikey ? 24 : n > 4 ? 60 : 82;
  // 16:9'da sütun en fazla 300 px, grup ortalanır (3 sütun tam genişlikte blok gibi duruyordu)
  const w = Math.min(d.dikey ? 9999 : 300, (genis - (n - 1) * ara) / n);
  const x0 = d.x0 + (genis - (n * w + (n - 1) * ara)) / 2;
  const taban = d.dikey ? 1180 : 860;
  const [hMin, hMax] = d.dikey ? [140, 540] : [120, 440];
  const adim = Math.min(0.34, Math.max(0.15, (s.sure - 1.8) / n));
  const adBoy = sigdir(d.dikey ? 42 : 44, s.seviyeler.map((x) => x.ad), w, ORAN.sans);
  return (
    <AbsoluteFill>
      <Baslik satirlar={s.satirlar} />
      {s.seviyeler.map((sv, i) => {
        const g = ac(f, 0.25 + 0.07 * i, 0.45);
        const dol = ac(f, 0.75 + adim * i, 0.45);
        const h = hMin + (hMax - hMin) * (n === 1 ? 1 : i / (n - 1));
        const renk = t.seri[i % t.seri.length];
        return (
          <div key={i} style={{ position: "absolute", left: x0 + i * (w + ara), top: taban - h, width: w, height: h, opacity: g }}>
            <div
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: 14,
                border: `1.5px solid ${dol > 0.02 ? renk : t.kenar}`,
                background: `${t.panel}b3`,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                  bottom: 0,
                  height: `${dol * 100}%`,
                  background: `repeating-linear-gradient(0deg, ${renk} 0 10px, transparent 10px 16px)`,
                  opacity: 0.9,
                }}
              />
            </div>
            <div style={{ position: "absolute", top: h + 14, left: 0, width: w }}>
              <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: adBoy, letterSpacing: -adBoy * 0.035, color: dol > 0.5 ? t.yazi : t.koyu, lineHeight: 1.1, whiteSpace: "nowrap" }}>
                {sv.ad}
              </div>
              <Mono boy={d.dikey ? 17 : 15} renk={dol > 0.5 ? renk : t.koyu}>
                {sv.etiket ?? `seviye ${String(i + 1).padStart(2, "0")}`}
              </Mono>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- sutunlar
const siralar = (v: number[]) => v.map((x) => 1 + v.filter((y) => y > x).length);

export const SutunlarSahne: React.FC<S<"sutunlar">> = ({ s }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const n = s.ogeler.length;
  const degerler = s.ogeler.map((o) => o.deger);
  const enBuyuk = Math.max(...degerler, 1e-9);
  const sira = siralar(degerler);
  const p = cik(f, 0.35 * fps, 1.75 * fps); // hepsi birlikte büyür: sıra her karede doğru kalır
  const od = s.ondalik ?? 0;
  const yaz = (x: number) => `${s.onek ?? ""}${sayiYaz(x, od)}${s.sonek ?? ""}`;
  const genis = d.x1 - d.x0;
  const not = s.not ? (
    <div style={{ position: "absolute", right: d.dikey ? undefined : d.W - d.x1, left: d.dikey ? d.x0 : undefined, top: d.dikey ? 520 : d.ust + 14, opacity: ac(f, 0.2) }}>
      <Mono>{s.not}</Mono>
    </div>
  ) : null;

  if (d.dikey) {
    // dikey: yatay çubuk satırları (dar tuvalde sütun okunmuyor)
    const y0 = 590;
    const satirH = Math.min(220, (1300 - y0) / n);
    const cubukW = genis - 230;
    const adBoy = sigdir(46, s.ogeler.map((o) => o.ad), genis - 260, ORAN.sans);
    return (
      <AbsoluteFill>
        <Baslik satirlar={s.satirlar} />
        {not}
        {s.ogeler.map((o, i) => {
          const renk = t.seri[i % t.seri.length];
          const w = Math.max(8, (o.deger / enBuyuk) * cubukW * p);
          return (
            <div key={i} style={{ position: "absolute", left: d.x0, top: y0 + i * satirH, width: genis, opacity: ac(f, 0.25 + i * 0.05, 0.3) }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
                <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: adBoy, letterSpacing: -adBoy * 0.035, color: t.yazi }}>{o.ad}</div>
                <Mono boy={17} renk={sira[i] === 1 ? t.vurgu : t.soluk}>
                  {o.etiket ?? `${sira[i]}. sıra`}
                </Mono>
              </div>
              <div style={{ display: "flex", alignItems: "center", marginTop: 16 }}>
                <div style={{ width: w, height: 40, borderRadius: 10, background: renk, opacity: sira[i] === 1 ? 1 : 0.78 }} />
                <Sayi boy={56} style={{ marginLeft: 22 }}>
                  {yaz(o.deger * p)}
                </Sayi>
              </div>
            </div>
          );
        })}
      </AbsoluteFill>
    );
  }

  const ara = n > 4 ? 60 : 82;
  const w = Math.min(300, (genis - (n - 1) * ara) / n);
  const x0 = d.x0 + (genis - (n * w + (n - 1) * ara)) / 2;
  const taban = 860;
  const degerBoy = sigdir(64, s.ogeler.map((o) => yaz(o.deger)), w, ORAN.rakam);
  const adBoy = sigdir(44, s.ogeler.map((o) => o.ad), w, ORAN.sans);
  return (
    <AbsoluteFill>
      <Baslik satirlar={s.satirlar} />
      {not}
      {s.ogeler.map((o, i) => {
        const h = 40 + (o.deger / enBuyuk) * 400;
        const renk = t.seri[i % t.seri.length];
        return (
          <div key={i} style={{ position: "absolute", left: x0 + i * (w + ara), top: taban - h * p, width: w, height: h * p, opacity: ac(f, 0.25 + i * 0.05, 0.3) }}>
            <div style={{ position: "absolute", inset: 0, borderRadius: 14, background: renk, opacity: sira[i] === 1 ? 1 : 0.78 }} />
            <div style={{ position: "absolute", top: -degerBoy - 18, left: 0, width: w, display: "flex", justifyContent: "center" }}>
              <Sayi boy={degerBoy}>{yaz(o.deger * p)}</Sayi>
            </div>
            <div style={{ position: "absolute", top: h * p + 14, left: 0, width: w }}>
              <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: adBoy, letterSpacing: -adBoy * 0.035, color: t.yazi, lineHeight: 1.1, whiteSpace: "nowrap" }}>{o.ad}</div>
              <Mono boy={15} renk={sira[i] === 1 ? t.vurgu : t.soluk}>
                {o.etiket ?? `${sira[i]}. sıra`}
              </Mono>
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- karsilastirma
const Kart: React.FC<{
  k: S<"karsilastirma">["s"]["a"];
  renk: string;
  at: number;
  x: number;
  y: number;
  w: number;
  h: number;
}> = ({ k, renk, at, x, y, w, h }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const g = ac(f, at, 0.55);
  const pad = d.dikey ? 32 : 38;
  const degerBoy = sigdir(d.dikey ? 100 : 112, [k.deger], w - 2 * pad, ORAN.rakam);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: h,
        borderRadius: 18,
        border: `1.5px solid ${t.kenar}`,
        background: `${t.panel}e6`,
        padding: d.dikey ? "28px 32px" : "34px 38px",
        opacity: g,
        transform: `translateY(${(1 - g) * 40}px)`,
        boxSizing: "border-box",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ width: 12, height: 12, borderRadius: 9, background: renk }} />
        <Mono renk={t.yazi} boy={22}>
          {k.ad}
        </Mono>
        {d.dikey && k.ust ? (
          <>
            <div style={{ flex: 1 }} />
            <Mono boy={16}>{k.ust}</Mono>
          </>
        ) : null}
      </div>
      {!d.dikey && k.ust ? (
        <div style={{ marginTop: 40 }}>
          <Mono boy={17}>{k.ust}</Mono>
        </div>
      ) : null}
      <Sayi boy={degerBoy} style={{ marginTop: d.dikey ? 22 : k.ust ? 8 : 48 }}>
        {k.deger}
      </Sayi>
      {d.dikey ? (
        k.alt || k.altEtiket ? (
          <div style={{ marginTop: 18, display: "flex", gap: 14, alignItems: "baseline" }}>
            {k.altEtiket ? <Mono boy={16}>{k.altEtiket}</Mono> : null}
            {k.alt ? <span style={{ fontFamily: MONO, fontSize: 30, color: t.soluk }}>{k.alt}</span> : null}
          </div>
        ) : null
      ) : (
        <>
          {k.altEtiket ? (
            <div style={{ marginTop: 22 }}>
              <Mono boy={17}>{k.altEtiket}</Mono>
            </div>
          ) : null}
          {k.alt ? <div style={{ fontFamily: MONO, fontSize: 38, color: t.soluk, marginTop: 6 }}>{k.alt}</div> : null}
        </>
      )}
    </div>
  );
};

export const KarsilastirmaSahne: React.FC<S<"karsilastirma">> = ({ s }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const renkA = t.seri[0];
  const renkB = t.seri[Math.min(4, t.seri.length - 1)];
  const genis = d.x1 - d.x0;
  const fark = s.fark;
  if (d.dikey) {
    const kh = 290;
    return (
      <AbsoluteFill>
        <Baslik satirlar={s.satirlar} />
        <Kart k={s.a} renk={renkA} at={0.5} x={d.x0} y={480} w={genis} h={kh} />
        <Kart k={s.b} renk={renkB} at={0.75} x={d.x0} y={480 + kh + 28} w={genis} h={kh} />
        {fark ? (
          <div style={{ position: "absolute", left: d.x0, top: 480 + 2 * kh + 70, width: genis, display: "flex", alignItems: "center", gap: 28 }}>
            <div style={{ opacity: ac(f, 1.5) }}>
              <Mono>{fark.etiket ?? "fark"}</Mono>
            </div>
            <div style={{ flex: 1 }}>
              <SerifSatir at={1.6} boy={sigdir(160, [fark.deger], genis - 200, ORAN.serif)}>
                <span style={{ fontStyle: "italic", color: t.vurgu }}>{fark.deger}</span>
              </SerifSatir>
            </div>
          </div>
        ) : null}
      </AbsoluteFill>
    );
  }
  const kw = fark ? 560 : (genis - 40) / 2;
  const fx = d.x0 + 2 * kw + 2 * 40 + 20;
  const fw = d.x1 - fx;
  return (
    <AbsoluteFill>
      <Baslik satirlar={s.satirlar} boy={92} />
      <Kart k={s.a} renk={renkA} at={0.5} x={d.x0} y={330} w={kw} h={400} />
      <Kart k={s.b} renk={renkB} at={0.75} x={d.x0 + kw + 40} y={330} w={kw} h={400} />
      {fark ? (
        <div style={{ position: "absolute", left: fx, top: 330, width: fw }}>
          <div style={{ opacity: ac(f, 1.5) }}>
            <Mono>{fark.etiket ?? "fark"}</Mono>
          </div>
          <SerifSatir at={1.6} boy={sigdir(210, [fark.deger], fw, ORAN.serif)}>
            <span style={{ fontStyle: "italic", color: t.vurgu }}>{fark.deger}</span>
          </SerifSatir>
          {fark.alt ? (
            <div style={{ marginTop: 10, opacity: ac(f, 2.0) }}>
              <Mono renk={t.yazi} boy={20} style={{ whiteSpace: "normal", lineHeight: 1.5 }}>
                {fark.alt}
              </Mono>
            </div>
          ) : null}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- liste
export const ListeSahne: React.FC<S<"liste">> = ({ s }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const n = s.ogeler.length;
  const genis = d.x1 - d.x0;
  const y0 = d.dikey ? 540 : 340;
  const satirH = Math.min(d.dikey ? 170 : 130, ((d.dikey ? 1300 : 900) - y0) / n);
  const noW = d.dikey ? 76 : 96;
  const boy = sigdir(d.dikey ? 58 : 66, s.ogeler, genis - noW, ORAN.sans, d.dikey ? 46 : 0);
  const adim = Math.min(0.55, Math.max(0.25, (s.sure - 1.6) / n));
  return (
    <AbsoluteFill>
      <Baslik satirlar={s.satirlar} boy={d.dikey ? 86 : 88} />
      {s.ogeler.map((o, i) => {
        const g = ac(f, 0.5 + adim * i, 0.5);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: d.x0,
              top: y0 + i * satirH,
              width: genis,
              height: satirH,
              display: "flex",
              alignItems: "center",
              borderBottom: `1px solid ${t.cizgi}`,
              opacity: g,
              transform: `translateX(${(1 - g) * -30}px)`,
            }}
          >
            <div style={{ width: noW }}>
              <Mono renk={t.vurgu} boy={20}>
                {String(i + 1).padStart(2, "0")}
              </Mono>
            </div>
            <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: boy, lineHeight: 1.12, letterSpacing: -boy * 0.025, color: t.yazi, flex: 1 }}>
              <Vurgulu metin={o} serif={false} />
            </div>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- soru
export const SoruSahne: React.FC<S<"soru">> = ({ s }) => {
  const f = useCurrentFrame();
  const ac = useAc();
  const d = useDuzen();
  const t = useTema();
  const boy = sigdir(d.dikey ? 132 : 140, s.satirlar, d.x1 - d.x0, ORAN.serif, d.dikey ? 96 : 0);
  const g = ac(f, 0.4 + 0.2 * s.satirlar.length, 0.5);
  return (
    <Orta>
      {s.satirlar.map((x, i) => (
        <SerifSatir key={i} at={0.1 + 0.2 * i} boy={boy} hiza="center">
          <Vurgulu metin={x} />
        </SerifSatir>
      ))}
      {s.alt ? (
        <div style={{ marginTop: boy * 0.45, opacity: g, display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <div style={{ width: 56 * g, height: 4, borderRadius: 2, background: t.vurgu }} />
          <Mono renk={t.yazi} boy={d.dikey ? 22 : 21}>
            {s.alt}
          </Mono>
        </div>
      ) : null}
    </Orta>
  );
};

export const SahneCiz: React.FC<{ s: Sahne }> = ({ s }) => {
  switch (s.tur) {
    case "baslik":
      return <BaslikSahne s={s} />;
    case "yazi":
      return <YaziSahne s={s} />;
    case "sayac":
      return <SayacSahne s={s} />;
    case "olcer":
      return <OlcerSahne s={s} />;
    case "sutunlar":
      return <SutunlarSahne s={s} />;
    case "karsilastirma":
      return <KarsilastirmaSahne s={s} />;
    case "liste":
      return <ListeSahne s={s} />;
    case "soru":
      return <SoruSahne s={s} />;
  }
};
