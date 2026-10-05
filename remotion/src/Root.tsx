import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import ornek from "../../ornekler/x-animasyon/ornek.json";
import { XAnimasyon } from "./x/XAnimasyon";
import { xSema, type XProps } from "./x/sema";
import { toplamKare } from "./x/zaman";

/**
 * İki boy, tek bileşen. Süre sahnelerin toplamından hesaplanır (calculateMetadata).
 *   XAnimasyon16x9  1920x1080 @ 60 fps  — X, YouTube araya
 *   XAnimasyon9x16  1080x1920 @ 30 fps  — Reels, Shorts, TikTok
 * Kompozisyon kimliğinde alt çizgi kullanılmaz (Remotion kabul etmiyor).
 */
const sure =
  (fps: number): CalculateMetadataFunction<XProps> =>
  ({ props }) => ({ durationInFrames: Math.max(1, toplamKare(props.sahneler, fps)) });

// Örnek yalnız Studio önizlemesi için varsayılan. Remotion --props ile gelen JSON'u varsayılanla
// birleştirir: JSON'da olmayan alan örnekten sızar. "örnek veri" etiketi gerçek ölçümün üstüne
// düşmesin diye etiket varsayılana konmaz; örneğin kendisi render edilince JSON'dan gelir.
const { etiket: _ornekEtiketi, ...ornekGovde } = ornek as unknown as XProps;
const varsayilan = ornekGovde as XProps;

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="XAnimasyon16x9"
      component={XAnimasyon}
      schema={xSema}
      defaultProps={varsayilan}
      calculateMetadata={sure(60)}
      width={1920}
      height={1080}
      fps={60}
      durationInFrames={600}
    />
    <Composition
      id="XAnimasyon9x16"
      component={XAnimasyon}
      schema={xSema}
      defaultProps={varsayilan}
      calculateMetadata={sure(30)}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={300}
    />
  </>
);
