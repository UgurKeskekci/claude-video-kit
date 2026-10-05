import { cancelRender, continueRender, delayRender, staticFile } from "remotion";

/**
 * Yalnız OFL fontlar (repo kökündeki fontlar/, `npm install` public/fonts'a kopyalar):
 *   serif  Newsreader (+ italik)  -> başlık, vurgu kelimesi
 *   sans   Inter                  -> sayılar, listeler (sıkı kalın grotesk)
 *   mono   IBM Plex Mono          -> küçük aralıklı BÜYÜK HARF etiketler
 * Aile adları özel: sistemde kurulu aynı adlı bir fontla karışmasın.
 *
 * FontFace API ile modül seviyesinde yüklenir (her render sekmesinde bir kez).
 * `document.fonts.ready` BEKLENMEZ: uzun render'da bir sekmede hiç çözülmediği ölçüldü.
 * Font yüklenemezse render SESSİZCE yedek fonta düşmez, hata verip durur.
 */
export const SERIF = "KitSerif";
export const SANS = "KitSans";
export const MONO = "KitMono";

const YUZLER: [string, "normal" | "italic", string, string][] = [
  [SERIF, "normal", "200 800", "Newsreader.ttf"],
  [SERIF, "italic", "200 800", "Newsreader-Italic.ttf"],
  [SANS, "normal", "100 900", "Inter.ttf"],
  [MONO, "normal", "400", "IBMPlexMono-Regular.ttf"],
  [MONO, "normal", "500", "IBMPlexMono-Medium.ttf"],
  [MONO, "normal", "600", "IBMPlexMono-SemiBold.ttf"],
];

let basladi = false;

export const fontlariYukle = () => {
  if (basladi || typeof document === "undefined") return;
  basladi = true;
  const h = delayRender("fontlar yükleniyor", { timeoutInMilliseconds: 60000 });
  Promise.all(
    YUZLER.map(([aile, stil, agirlik, dosya]) => {
      const yuz = new FontFace(aile, `url("${staticFile("fonts/" + dosya)}") format("truetype")`, {
        style: stil,
        weight: agirlik,
      });
      return yuz.load().then((y) => {
        document.fonts.add(y);
      });
    })
  )
    .then(() => continueRender(h))
    .catch((e) =>
      cancelRender(new Error(`Font yüklenemedi (remotion/ içinde 'npm run fontlar' çalıştır): ${e}`))
    );
};
