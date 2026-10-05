import { Config } from "@remotion/cli/config";

// Opak h264 çıktı. JPEG ara kare kalitesi yüksek tutulur: ince ızgara ve gren düşük kalitede çamurlaşıyor.
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(92);
Config.setOverwriteOutput(true);
