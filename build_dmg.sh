#!/bin/bash
# Build PITS macOS DMG

set -e
APP="${1:-dist/SC PITS.app}"
DMG="dist/PITS-0.4.0.dmg"
TMP="dist/PITS-tmp.dmg"
VOLNAME="PITS"
BG="PITS_DMG_BG.png"

if [ ! -d "$APP" ]; then
    echo "Error: $APP not found. Build the .app first."
    exit 1
fi

# Set LSUIElement to hide dock icon (menu-bar only app)
PLIST="$APP/Contents/Info.plist"
if grep -q "LSUIElement" "$PLIST" 2>/dev/null; then
    sed -i '' 's|<string>0</string>.*</key>.*LSUIElement|<string>1</string></key><key>LSUIElement|' "$PLIST" 2>/dev/null || true
else
    sed -i '' 's|<key>NSHighResolutionCapable</key>|<key>LSUIElement</key><string>1</string><key>NSHighResolutionCapable</key>|' "$PLIST"
fi

rm -f "$DMG" "$TMP"

hdiutil create -volname "$VOLNAME" -srcfolder "$APP" -ov -format UDRW -fs HFS+ "$TMP"
MOUNT=$(hdiutil attach "$TMP" -nobrowse -mountroot /tmp | tail -1 | awk '{print $NF}')

ln -sf /Applications "$MOUNT/Applications"
mkdir -p "$MOUNT/.background"
cp "$BG" "$MOUNT/.background/"

sleep 1
open "$MOUNT"
sleep 2

osascript << EOF
tell application "Finder"
    set v to (first window whose name = "$VOLNAME")
    set current view of v to icon view
    set toolbar visible of v to false
    set statusbar visible of v to false
    set bounds of v to {200, 200, 840, 712}
    set opts to icon view options of v
    set arrangement of opts to not arranged
    set icon size of opts to 164
    try
        set background picture of opts to POSIX file "$MOUNT/.background/$BG"
    end try
end tell
EOF

sleep 1
osascript << EOF
tell application "Finder"
    set v to (first window whose name = "$VOLNAME")
    set position of item "Applications" of v to {133, 208}
    set position of item "SC PITS.app" of v to {517, 208}
end tell
EOF

sleep 2
osascript -e 'tell application "Finder" to close every window'
sleep 1

hdiutil detach "$MOUNT" -force 2>/dev/null
sleep 1
hdiutil convert "$TMP" -format UDZO -o "$DMG"
rm -f "$TMP"
echo "Created: $DMG"
