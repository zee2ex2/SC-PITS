#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

APP_BUNDLE="$DIR/dist/SC PITS.app"
DMG_PATH="$DIR/dist/SC PITS.dmg"
STAGING="/tmp/sc_pits_dmg"

if [ ! -d "$APP_BUNDLE" ]; then
  echo "Error: Build the app first with ./build_macos.sh"
  exit 1
fi

rm -rf "$STAGING" "$DMG_PATH"
mkdir -p "$STAGING"

# Copy the .app bundle into the staging folder
cp -R "$APP_BUNDLE" "$STAGING/"

# Symlink to /Applications for drag-and-drop install
ln -s /Applications "$STAGING/Applications"

echo "Creating DMG..."
hdiutil create -volname "SC PITS" \
  -srcfolder "$STAGING" \
  -ov -format UDZO \
  -fs HFS+ \
  "$DMG_PATH" 2>&1 | tail -3

rm -rf "$STAGING"

echo ""
echo "DMG created: $DMG_PATH"
echo "Size: $(du -sh "$DMG_PATH" | cut -f1)"