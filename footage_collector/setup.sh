#!/usr/bin/env bash
# Footage Collector - one-time setup for macOS / Linux
set -e
cd "$(dirname "$0")"

echo "================================================"
echo "   Footage Collector  -  one-time setup"
echo "================================================"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[X] python3 not found. Install Python 3.10+ first:"
  echo "    macOS:  brew install python   (or https://www.python.org/downloads/)"
  echo "    Ubuntu: sudo apt install python3 python3-pip python3-tk"
  exit 1
fi

echo "[1/2] Installing Python packages..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "[2/2] Checking ffmpeg..."
if command -v ffmpeg >/dev/null 2>&1; then
  echo "    ffmpeg found: $(command -v ffmpeg)"
else
  echo "    ffmpeg NOT found. Install it:"
  echo "      macOS:  brew install ffmpeg"
  echo "      Ubuntu: sudo apt install ffmpeg"
fi

echo "Done. Run:  ./run.sh"
