#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "$0")/dist/SC PITS" && pwd)"
DEST="$HOME/Applications/SC PITS"

echo "Installing SC Personal Inventory Tracker..."
echo "  Source: $SRC"
echo "  Target: $DEST"

mkdir -p "$DEST"
cp -R "$SRC/InventoryTracker" "$DEST/"
cp "$DEST/InventoryTracker/icon_PITS.png" "$DEST/"
cp "$SRC/launch_macos.command" "$DEST/"

echo ""
echo "Installed to $DEST"
echo ""
echo "Launch by double-clicking: $DEST/launch_macos.command"
echo "Or run from terminal:     $DEST/InventoryTracker/InventoryTracker"