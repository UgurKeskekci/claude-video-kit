import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { Mono, useDuzen, useTema } from "./parcalar";
import type { Bolum } from "./zaman";

/**
 * Sürekli arayüz çerçevesi + zemin: sol üst marka, sağ üst "01 — BÖLÜM", altta bölmeli
 * ilerleme + zaman. Zeminde hafif ızgara, kenar kararması, ince gren, çok hafif ışık.
 * Yazıda parlama/degrade YOK.
 */

// Gren: tohumlu gürültü karosu, bir kez üretilir, her karede kaydırılır.
// (SVG feTurbulence'ı her karede hesaplamak render'ı kilitliyordu.)
let grenUrl = "";
const gren = () => {
  if (grenUrl || typeof document === "undefined") return grenUrl;
  const n = 192;
  const c = document.createElement("canvas");
  c.width = n;
  c.height = n;
  const x = c.getContext("2d");
  if (!x) return "";
  const img = x.createImageData(n, n);
  let s = 0x2f6b1d3;
  const rnd = () => {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  for (let i = 0; i < n * n; i++) {
    const v = Math.floor(rnd() * 255);
    img.data[i * 4] = v;
    img.data[i * 4 + 1] = v;
    img.data[i * 4 + 2] = v;
    img.data[i * 4 + 3] = 255;
  }
  x.putImageData(img, 0, 0);
  grenUrl = c.toDataURL("image/png");
  return grenUrl;
};

const hexRgba = (hex: string, a: number) => {
  const h = hex.replace("#", "");
  const v = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6);
  const n = parseInt(v, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

export const Zemin: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTema();
  const d = useDuzen();
  const adim = Math.floor(f / Math.max(1, Math.round(fps / 30))); // gren 30 Hz'de kayar
  const izgara = d.dikey ? 90 : 96;
  return (
    <>
      <AbsoluteFill
        style={{
          background: `radial-gradient(${d.W * 0.6}px ${d.H * 0.7}px at 18% 28%, ${hexRgba(t.vurgu, 0.07)}, transparent 70%), ${t.zemin}`,
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.032) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.032) 1px, transparent 1px)",
          backgroundSize: `${izgara}px ${izgara}px`,
          backgroundPosition: `-1px ${izgara / 2 - 8}px`,
        }}
      />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)" }} />
      <AbsoluteFill
        style={{
          backgroundImage: `url(${gren()})`,
          backgroundRepeat: "repeat",
          backgroundPosition: `${-((adim * 37) % 192)}px ${-((adim * 53) % 192)}px`,
          opacity: 0.06,
          mixBlendMode: "overlay",
        }}
      />
    </>
  );
};

const Isaret: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTema();
  const yanan = Math.floor(f / (fps * 0.5)) % 5;
  return (
    <svg width="34" height="30" viewBox="0 0 34 30">
      {[0, 1, 2, 3, 4].map((i) => (
        <rect key={i} x={i * 7} y={30 - (8 + i * 5.5)} width="4.5" height={8 + i * 5.5} rx="1.5" fill={i === yanan ? t.vurgu : t.yazi} />
      ))}
    </svg>
  );
};

export const Cerceve: React.FC<{ marka: string; etiket?: string; bolumler: Bolum[]; toplam: number }> = ({
  marka,
  etiket,
  bolumler,
  toplam,
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useTema();
  const d = useDuzen();
  const bolum = [...bolumler].reverse().find((b) => f >= b.bas) ?? bolumler[0];
  const sn = Math.floor(f / fps);
  const saat = `${String(Math.floor(sn / 60)).padStart(2, "0")}:${String(sn % 60).padStart(2, "0")}`;
  const ilerlemeY = d.H - d.cerceveAlt;
  return (
    <>
      <div style={{ position: "absolute", left: 64, top: d.cerceveUst, display: "flex", alignItems: "center", gap: 14 }}>
        <Isaret />
        <Mono renk={t.yazi} boy={20}>
          {marka}
        </Mono>
      </div>
      {bolum ? (
        <div
          style={{
            position: "absolute",
            right: 64,
            top: d.cerceveUst + 6,
            display: "flex",
            gap: 18,
            flexDirection: "row",
          }}
        >
          <Mono renk={t.vurgu}>{String(bolum.no).padStart(2, "0")}</Mono>
          {bolum.ad ? (
            <>
              <Mono renk={t.koyu}>—</Mono>
              <Mono renk={t.yazi}>{bolum.ad}</Mono>
            </>
          ) : null}
        </div>
      ) : null}
      <div style={{ position: "absolute", left: 64, top: ilerlemeY - 12 }}>
        <Mono boy={17} renk={t.yazi}>
          {saat}
        </Mono>
      </div>
      <div style={{ position: "absolute", left: 210, right: 64, top: ilerlemeY, height: 4, display: "flex", gap: 10 }}>
        {bolumler.map((b) => {
          const dolu = Math.min(1, Math.max(0, (f - b.bas) / Math.max(1, b.bit - b.bas)));
          return (
            <div key={b.no} style={{ flex: Math.max(1, b.bit - b.bas) / Math.max(1, toplam), height: 4, borderRadius: 2, background: t.cizgi, overflow: "hidden" }}>
              <div style={{ height: 4, width: `${dolu * 100}%`, background: t.vurgu }} />
            </div>
          );
        })}
      </div>
      {etiket ? (
        <div style={{ position: "absolute", right: 64, top: ilerlemeY - 36 }}>
          <Mono boy={15} renk={t.soluk}>
            {etiket}
          </Mono>
        </div>
      ) : null}
    </>
  );
};
