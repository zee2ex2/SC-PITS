# P.I.T.S.

Personal Inventory Tracker System — desktop inventory manager for Star Citizen.

## Features

- Full inventory management (items, stations, quantities)
- Item/station autocomplete with search and filter
- Extension system for plugins
- JOCK Strap extension for real-time community sync
- Dark/light theme toggle
- Auto-update checking via GitHub releases
- Cross-platform (macOS, Windows, Linux)

## Download

Download the latest release from the [Releases page](https://github.com/zee2ex2/SC-PITS/releases).

### macOS
- Download `PITS-x.x.x.dmg`, open it, and drag `PITS.app` to Applications.

## Building from Source

```bash
pip install -r requirements.txt
python app.py
```

### Building standalone executable

```bash
pip install pyinstaller
pyinstaller --windowed --name "PITS" --add-data "templates:templates" \
  --add-data "static:static" --add-data "extensions:extensions" \
  --hidden-import "extensions" --hidden-import "websocket" \
  --collect-submodules "extensions" --collect-all "websocket" app.py
```

### Building DMG

```bash
./build_dmg.sh
```

## License

MIT
