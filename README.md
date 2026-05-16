# Personal Inventory Tracker

A self-contained web server for managing inventory records against a SQLite database. Uses only the Python standard library.

## Quick Start

### macOS (arm64)

1. Download `SC PITS.dmg` from the [releases page](#) or build from source (see below).
2. Open the DMG and drag **SC PITS.app** into the **Applications** folder.
3. Launch **SC PITS.app** from Applications.

The app runs as a background server (no dock icon) and opens your browser automatically.

### Windows

1. Download `SC_PITS_Setup.exe` from the [releases page](#) or build from source (see below).
2. Run the installer — it installs to `%PROGRAMFILES%\SC PITS\`.
3. Launch **SC PITS** from the Start Menu.

The app runs as a background process (no window, system tray icon) and opens your browser automatically.

### From source

Requires Python 3.

```bash
python3 app.py
```

## Access

Open the printed URL in your browser. The port is random (49152–65535) on each launch. Other devices on your network can connect to the network URL shown on startup.

Set a specific port:

```bash
PORT=9090 python3 app.py
```

## Features

### Inventory Management

- **Add rows** — select an item, station, set quality (0–100) and quantity in SCU, then submit
- **Edit rows** — click Edit on any row to change item, station, quality, or quantity
- **Delete rows** — click Del to remove an inventory row (with confirmation prompt)
- **Autocomplete** — item and station fields suggest matching entries as you type
- **Pagination** — navigate pages and choose rows-per-page (5/10/25/50)

### Settings

- **Switch database** — enter a file path or upload a `.db` / `.sqlite` file (copied to `dbs/`)
- **Create database** — create a new empty database in the `dbs/` folder or at a custom path
- **Add items** — add new inventory item names with a category ID
- **Add stations** — add new stations with a name, code, and star system

### Database

The app expects a SQLite database with these tables:

- `inventory` — rows with `itemid`, `qual`, `qty` (in cents), `stationid`
- `item` — item catalog keyed by `id`
- `stations` — station list keyed by `id`, with `systemid` foreign key
- `systems` — star systems keyed by `id`

Missing tables trigger an on-screen setup notice.

### Display

- QTY stored as integer cents, displayed as SCU (e.g. `1200` → `12.00 SCU`)
- Dark/light theme toggle (persisted to localStorage + cookie)
- Responsive layout for desktop and mobile

## File Access

After installation, all files are accessible at the install location:

| File | Purpose |
|------|---------|
| `config.json` | Database path setting (edit to switch databases) |
| `mainInventory` | Default SQLite database |
| `dbs/` | Uploaded or created databases |
| `icon_PITS.png` | Application icon |

## Building from Source

### macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install pyinstaller
./build_macos.sh      # creates dist/SC PITS.app
./build_dmg.sh        # creates dist/SC PITS.dmg
```

Result: `dist/SC PITS.dmg` — a distributable disk image with `SC PITS.app` inside.

### Windows

```bat
python -m venv venv
venv\Scripts\activate
pip install pyinstaller pystray pillow
build_windows.bat
```

Result: `dist\SC PITS\` — executable ready to run.

To create an installer, install [Inno Setup](https://jrsoftware.org/isdl.php) and run:

```bat
ISCC installer.iss
```

Result: `dist\SC_PITS_Setup.exe`.

## Project Structure

```
.
├── app.py              # Web server
├── render.py           # HTML template rendering
├── store.py            # Database operations
├── config.json         # Runtime config
├── mainInventory       # Default database
├── icon_PITS.png       # Application icon
├── icon_PITS.icns      # macOS app icon
├── icon_PITS.ico       # Windows app icon
├── static/styles.css   # Stylesheet
├── templates/          # HTML templates
├── build_macos.sh      # macOS build script (PyInstaller)
├── build_dmg.sh        # macOS DMG packaging script
├── build_windows.bat   # Windows build script (PyInstaller)
├── installer.iss       # Inno Setup installer script
└── dist/
    ├── SC PITS.app     # macOS app bundle
    ├── SC PITS.dmg     # Distributable disk image (macOS)
    ├── SC PITS/        # Windows executable directory
    └── SC_PITS_Setup.exe  # Windows installer
```
