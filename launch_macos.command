#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
clear
echo "SC Personal Inventory Tracker"
echo "============================"
echo ""
cd "$DIR"
exec "$DIR/InventoryTracker/InventoryTracker"
