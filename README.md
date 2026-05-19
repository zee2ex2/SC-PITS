# P.I.T.S.

**P**ersonal **I**nventory **T**racker **S**ystem

A desktop inventory manager for Star Citizen. Track your items, quantities, and station locations across all your org's operations.

## Features

- Full inventory management with item/station autocomplete
- Search, filter, and sort your inventory
- Multiple database profiles
- Extension system for plugins
- **JOCKstrap** extension for real-time sync with Community ShoWER
- Dark/light theme toggle
- Auto-update checking via GitHub releases
- Cross-platform (macOS, Windows, Linux)

## Download

Download the latest release from the [Releases page](https://github.com/zee2ex2/SC-PITS/releases).

### macOS
Open `PITS-x.x.x.dmg` and drag `PITS.app` to Applications.

## Quick Start

1. Launch PITS
2. Click **Settings** to configure your database
3. Start adding inventory via the **Add Inventory** form

### Connecting to Community ShoWER (via JOCKstrap)

1. Install the [JOCKstrap](https://github.com/zee2ex2/SC-PITS-JOCKstrap-Extension) extension
2. Go to **Settings → JOCKstrap**
3. Enter your Community ShoWER server URL
4. Click **Login with Discord**
5. Enable **Auto-sync**

## Building from Source

### Dependencies

```bash
pip install -r requirements.txt
```

### Run

```bash
python app.py
```

### Build macOS App + DMG

```bash
pip install pyinstaller
pyinstaller --windowed --name "PITS" --icon "icon_PITS.icns" \
  --add-data "templates:templates" --add-data "static:static" \
  --add-data "extensions:extensions" --add-data "icon_PITS.icns:." \
  --hidden-import "extensions" --hidden-import "websocket" \
  --collect-submodules "extensions" --collect-all "websocket" app.py
./build_dmg.sh
```

## Extensions

PITS supports third-party extensions. Extensions are installed via ZIP files in **Settings → Manage Extensions**.

### Available Extensions

- [JOCKstrap](https://github.com/zee2ex2/SC-PITS-JOCKstrap-Extension) — Community ShoWER inventory sync

## License

MIT
