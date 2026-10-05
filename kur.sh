#!/bin/sh
# macOS kurulumu: ffmpeg + Python sanal ortamı + bağımlılıklar. Remotion skill'i için ayrıca Node 18+ gerekir.
set -e
command -v brew >/dev/null || { echo "Önce Homebrew kur: https://brew.sh"; exit 1; }
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v python3 >/dev/null || brew install python@3.12
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
echo "Tamam. Bu klasörde Claude Code'u aç: claude"
