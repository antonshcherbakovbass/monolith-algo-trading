#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

python3 generate_icon.py
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --noconfirm --clean packaging/macos/GrooveTrainer.spec

APP="dist/Groove Trainer.app"
if [[ ! -d "$APP" ]]; then
  echo "Build failed: $APP was not created"
  exit 1
fi

# Ensure the sun icon is the Dock / Finder icon.
mkdir -p "$APP/Contents/Resources"
cp -f packaging/icons/app_icon.icns "$APP/Contents/Resources/app_icon.icns"
cp -f packaging/macos/AppIcon.iconset/icon_512x512@2x.png "$APP/Contents/Resources/AppIcon.png" 2>/dev/null || true

OUT="dist_installers/macos"
mkdir -p "$OUT"
DMG="$OUT/GrooveTrainer-macOS.dmg"
rm -f "$DMG"
hdiutil create -volname "Groove Trainer" -srcfolder "$APP" -ov -format UDZO "$DMG"
echo "macOS installer image: $DMG"
