// Repo kökündeki fontlar/ klasörünü public/fonts/'a kopyalar (Remotion yalnız public/'ten servis eder).
// Tek kaynak fontlar/: OFL lisans metinleri de birlikte kopyalanır. npm install sonrası kendiliğinden çalışır.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const burasi = dirname(fileURLToPath(import.meta.url));
const kaynak = join(burasi, "..", "..", "fontlar");
const hedef = join(burasi, "..", "public", "fonts");
// Yalnız bu üç aile kullanılır; Caveat animasyon skill'inin (PIL) fontu, buraya gerekmez.
const gerekli = [
  "Newsreader.ttf", "Newsreader-Italic.ttf", "Inter.ttf",
  "IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "IBMPlexMono-SemiBold.ttf",
  "OFL-Newsreader.txt", "OFL-Inter.txt", "OFL-IBMPlexMono.txt",
];

if (!existsSync(kaynak)) {
  console.error(`fontlar klasörü bulunamadı: ${kaynak}`);
  process.exit(1);
}
mkdirSync(hedef, { recursive: true });
const var_ = new Set(readdirSync(kaynak));
const eksik = gerekli.filter((d) => !var_.has(d));
if (eksik.length) {
  console.error("Eksik font dosyası: " + eksik.join(", "));
  process.exit(1);
}
for (const d of gerekli) copyFileSync(join(kaynak, d), join(hedef, d));
console.log(`fontlar kopyalandı -> public/fonts (${gerekli.length} dosya)`);
