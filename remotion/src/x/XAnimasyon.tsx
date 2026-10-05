import React from "react";
import { AbsoluteFill, Easing, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { Cerceve, Zemin } from "./Cerceve";
import { fontlariYukle } from "./fontlar";
import { TemaBag, VARSAYILAN_TEMA, type Tema, useAc } from "./parcalar";
import { SahneCiz } from "./sahneler";
import type { XProps } from "./sema";
import { bolumler, zamanla } from "./zaman";

fontlariYukle();

/** Sahne geçişi: kısa yukarı itme + saydamlık. İlk sahne girişsiz, son sahne çıkışsız. */
const Gecis: React.FC<{ uz: number; ilk: boolean; son: boolean; children: React.ReactNode }> = ({ uz, ilk, son, children }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const ac = useAc();
  const g = ilk ? 1 : ac(f, 0, 0.35);
  const c = son
    ? 0
    : interpolate(f, [uz - 0.3 * fps, uz], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.in(Easing.cubic),
      });
  return <AbsoluteFill style={{ opacity: g * (1 - c), transform: `translateY(${(1 - g) * 30 - c * 30}px)` }}>{children}</AbsoluteFill>;
};

const temaKur = (t: XProps["tema"]): Tema => {
  const dolu = Object.fromEntries(Object.entries(t ?? {}).filter(([, v]) => v !== undefined && v !== null));
  const sonuc = { ...VARSAYILAN_TEMA, ...dolu } as Tema;
  if (!sonuc.seri || sonuc.seri.length === 0) sonuc.seri = VARSAYILAN_TEMA.seri;
  return sonuc;
};

export const XAnimasyon: React.FC<XProps> = (props) => {
  const { fps } = useVideoConfig();
  const tema = temaKur(props.tema);
  const z = zamanla(props.sahneler, fps);
  const toplam = z.reduce((t, x) => t + x.uz, 0);
  return (
    <TemaBag.Provider value={tema}>
      <AbsoluteFill style={{ background: tema.zemin }}>
        <div lang="tr" style={{ position: "absolute", inset: 0 }}>
          <Zemin />
          {z.map((x) => (
            <Sequence key={x.i} from={x.bas} durationInFrames={x.uz} name={`${x.i + 1} ${x.sahne.tur}`}>
              <Gecis uz={x.uz} ilk={x.i === 0} son={x.i === z.length - 1}>
                <SahneCiz s={x.sahne} />
              </Gecis>
            </Sequence>
          ))}
          <Cerceve marka={props.marka} etiket={props.etiket} bolumler={bolumler(z)} toplam={toplam} />
        </div>
      </AbsoluteFill>
    </TemaBag.Provider>
  );
};
