#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

source venv/bin/activate

rm -rf dist build

# Build with --windowed to create a .app bundle
pyinstaller --windowed --onedir \
  --name "PITS" \
  --icon "$DIR/AppIcon.icns" \
  --add-data "$DIR/templates:templates" \
  --add-data "$DIR/static:static" \
  --add-data "$DIR/extensions:extensions" \
  --add-data "$DIR/config.json:." \
  --add-data "$DIR/mainInventory:." \
  --add-data "$DIR/AppIcon.icns:." \
  --hidden-import rumps \
  --distpath "$DIR/dist" \
  --workpath "$DIR/build" \
  --specpath "$DIR/build" \
  --contents-directory "_internal" \
  "$DIR/app.py"

APP_BUNDLE="$DIR/dist/PITS.app"

# Frameworks must contain a Python symlink for the windowed bootloader
mkdir -p "$APP_BUNDLE/Contents/Frameworks"
ln -sf "../Resources/Python" "$APP_BUNDLE/Contents/Frameworks/Python"

# Create dbs/ directory in Resources for user data
mkdir -p "$APP_BUNDLE/Contents/Resources/dbs"

# Add LSUIElement so the app runs as an agent (no dock icon)
plutil -insert LSUIElement -bool YES "$APP_BUNDLE/Contents/Info.plist" 2>/dev/null || true

rm -rf "$DIR/build"

echo ""
echo "Build complete!"
echo "  App bundle: $APP_BUNDLE"
echo ""
echo "To create distributable DMG:"
echo "  ./build_dmg.sh"