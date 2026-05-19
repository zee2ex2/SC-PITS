import json
import os
import random
import shutil
import socket
import sqlite3
import sys
import threading
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from store import InventoryStore
from render import load_templates, render_manage, render_settings, render_setup, escape, cents_from_scu, ext_context
from extensions import discover_extensions, Extension

PITS_VERSION = "0.4.0"
PITS_REPO = "zee2ex2/SC-PITS"

try:
    import rumps
except ImportError:
    rumps = None

try:
    import pystray
    from PIL import Image as PILImage
except ImportError:
    pystray = None


if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    if sys.platform == "darwin":
        DATA_DIR = Path.home() / "Library" / "Application Support" / "SC PITS"
    elif sys.platform == "win32":
        DATA_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "SC PITS"
    else:
        exe_dir = Path(sys.executable).resolve().parent
        DATA_DIR = exe_dir
else:
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR

ICON_NAMES = ["icon_PITS.icns", "icon_PITS.png"]

DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DATA_DIR / "config.json"
DEFAULT_DB = DATA_DIR / "mainInventory"
UPLOAD_DIR = DATA_DIR / "dbs"
UPLOAD_DIR.mkdir(exist_ok=True)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT_ENV = os.environ.get("PORT")


def is_port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", port))
            return True
        except OSError:
            return False


def find_port(preferred=None):
    if preferred and is_port_available(preferred):
        return preferred
    while True:
        port = random.randint(49152, 65535)
        if is_port_available(port):
            return port


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            bak = CONFIG_PATH.with_suffix(".json.bak")
            if bak.exists():
                try:
                    return json.loads(bak.read_text())
                except (json.JSONDecodeError, OSError):
                    pass
            return {}
    return {}


def save_config(updates):
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    config.update(updates)
    bak = CONFIG_PATH.with_suffix(".json.bak")
    try:
        if CONFIG_PATH.exists():
            shutil.copy2(str(CONFIG_PATH), str(bak))
    except OSError:
        pass
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


DB_COMPAT_WARNING = None

config = load_config()
db_path = config.get("db_path", "")
DATABASE = Path(db_path) if db_path else DEFAULT_DB

store = InventoryStore(DATABASE)
LOCAL_URL = ""
NETWORK_URL = ""

EXTENSIONS = []
EXTENSION_CONTEXTS = {}


class AppHandler(BaseHTTPRequestHandler):
    @staticmethod
    def _parse_prefs(headers):
        cookie_header = headers.get("Cookie", "")
        prefs = {}
        if not cookie_header:
            return prefs
        c = SimpleCookie()
        c.load(cookie_header)
        theme = c.get("pref_theme")
        if theme and theme.value:
            prefs["theme"] = theme.value
        per_page = c.get("pref_per_page")
        if per_page and per_page.value:
            prefs["per_page"] = per_page.value
        return prefs

    def do_GET(self):
        try:
            self._handle_get()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.respond(f"<h1>Server Error</h1><pre>{escape(str(e))}</pre>", HTTPStatus.INTERNAL_SERVER_ERROR)

    def _handle_get(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/favicon" or path == "/favicon.ico":
            icon = BASE_DIR / "icon_PITS.png"
            if not icon.exists():
                icon = DATA_DIR / "icon_PITS.png"
            if icon.exists():
                self.serve_static(icon, "image/png")
            else:
                self.respond("Not found", HTTPStatus.NOT_FOUND)
            return

        if path == "/static/styles.css":
            self.serve_static(BASE_DIR / "static" / "styles.css", "text/css; charset=utf-8")
            return

        if path == "/static/pits.js":
            self.serve_static(BASE_DIR / "static" / "pits.js", "application/javascript; charset=utf-8")
            return

        raw = urllib.parse.parse_qs(parsed.query)
        qs = {k: v[0] for k, v in raw.items() if v[0]}
        notice = qs.pop("notice", "")
        kind = qs.pop("kind", "success")
        prefs = self._parse_prefs(self.headers)

        for ext in EXTENSIONS:
            resp, handled = ext.on_route(path, qs, None, "GET")
            if handled:
                _refresh_ext_contexts()
                if isinstance(resp, tuple):
                    body, _ = resp
                    self.respond(body)
                else:
                    self.respond(resp)
                return

        with store.connect() as db:
            missing = store.missing_tables(db)
            if missing:
                body = render_setup(missing, local_url=LOCAL_URL, network_url=NETWORK_URL, db_compat_warning=DB_COMPAT_WARNING)
                self.respond(body)
                return

            if path == "/" or path == "/manage":
                body = render_manage(db, qs, store, prefs=prefs, local_url=LOCAL_URL, network_url=NETWORK_URL, db_compat_warning=DB_COMPAT_WARNING, ext_ctx=EXTENSION_CONTEXTS, pits_version=PITS_VERSION)
                self.respond(body)
                return

            if path == "/settings":
                ext_list = []
                cfg = load_config()
                exts_cfg = cfg.get("extensions", {})
                for ext in discover_extensions():
                    enabled = exts_cfg.get(ext.name, {}).get("enabled", True)
                    ctx = EXTENSION_CONTEXTS.get(ext.name, {})
                    connected = ctx.get("ext_jock_connected", "false") == "true"
                    ext_list.append({"name": ext.name, "version": ext.version, "enabled": enabled, "connected": connected})
                body = render_settings(DATABASE, db=db, store=store, prefs=prefs, local_url=LOCAL_URL, network_url=NETWORK_URL, db_compat_warning=DB_COMPAT_WARNING, ext_ctx=EXTENSION_CONTEXTS, extensions_list=ext_list, pits_version=PITS_VERSION)
                self.respond(body)
                return

            self.respond("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/settings/upload-db":
            self._settings_upload_db()
            return

        if parsed.path == "/settings/toggle-extension":
            self._settings_toggle_extension()
            return

        if parsed.path == "/settings/install-extension":
            self._settings_install_extension()
            return

        if parsed.path == "/settings/remove-extension":
            self._settings_remove_extension()
            return

        if parsed.path == "/settings/check-updates":
            self._settings_check_updates()
            return

        if parsed.path == "/settings/apply-updates":
            self._settings_apply_updates()
            return

        length = int(self.headers.get("Content-Length", "0"))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        data = {key: values[0].strip() for key, values in form.items() if values}

        for ext in EXTENSIONS:
            resp, handled = ext.on_route(parsed.path, {}, data, "POST")
            if handled:
                _refresh_ext_contexts()
                if isinstance(resp, tuple):
                    body, _ = resp
                    self.respond(body)
                else:
                    self.respond(resp)
                return

        if parsed.path == "/settings/save":
            self.settings_save(data)
            return
        if parsed.path == "/settings/create":
            self.settings_create(data)
            return

        with store.connect() as db:
            if store.missing_tables(db):
                self.redirect("Database tables are missing.", "error")
                return
            try:
                if parsed.path == "/manage/add":
                    added_id = None
                    self.manage_add(db, data)
                    for ext in EXTENSIONS:
                        ext.on_inventory_add(db, added_id, data)
                    return
                if parsed.path == "/manage/update":
                    inv_id = data.get("inv_id", "")
                    self.manage_update(db, data)
                    for ext in EXTENSIONS:
                        ext.on_inventory_update(db, inv_id, data)
                    return
                if parsed.path == "/manage/delete":
                    inv_id = data.get("inv_id", "")
                    self.manage_delete(db, data)
                    for ext in EXTENSIONS:
                        ext.on_inventory_delete(db, inv_id)
                    return
                if parsed.path == "/manage/add-item":
                    self.manage_add_item(db, data)
                    return
                if parsed.path == "/manage/add-station":
                    self.manage_add_station(db, data)
                    return
            except (sqlite3.Error, TypeError, ValueError) as exc:
                self.redirect(f"Request failed: {exc}", "error")
                return
        self.respond("Not found", HTTPStatus.NOT_FOUND)

    def _refresh_compat_warning(self):
        global DB_COMPAT_WARNING
        DB_COMPAT_WARNING = None
        if DATABASE.exists():
            try:
                with store.connect() as db:
                    compatible, ver, warnings = store.check_compatibility(db)
                    if warnings:
                        if isinstance(warnings, list):
                            DB_COMPAT_WARNING = " ".join(warnings)
                        else:
                            DB_COMPAT_WARNING = warnings
            except Exception:
                pass

    def manage_add(self, db, data):
        itemid = data.get("itemid", "")
        stationid = data.get("stationid", "")
        qual = data.get("qual", "")
        qty_scu = data.get("qty_scu", "")
        if not itemid:
            self.redirect("Item is required.", "error", "/manage")
            return
        qty = cents_from_scu(qty_scu)
        if qty is None:
            self.redirect("Enter a valid QTY in SCU.", "error", "/manage")
            return
        store.add_inventory(db, itemid, qual, qty, stationid)
        self.redirect("Inventory added.", "success", "/manage")

    def manage_update(self, db, data):
        inv_id = data.get("inv_id", "")
        itemid = data.get("itemid", "")
        stationid = data.get("stationid", "")
        qual = data.get("qual", "")
        qty_scu = data.get("qty_scu", "")
        if not inv_id or not itemid:
            self.redirect("Missing required fields.", "error", "/manage")
            return
        qty = cents_from_scu(qty_scu)
        if qty is None:
            self.redirect("Enter a valid QTY in SCU.", "error", "/manage")
            return
        store.update_inventory(db, inv_id, itemid, qual, qty, stationid)
        self.redirect("Inventory updated.", "success", "/manage")

    def manage_delete(self, db, data):
        inv_id = data.get("inv_id", "")
        if not inv_id:
            self.redirect("Missing inventory ID.", "error", "/manage")
            return
        store.delete_inventory(db, inv_id)
        self.redirect("Inventory deleted.", "success", "/manage")

    def manage_add_item(self, db, data):
        name = data.get("name", "")
        catid = data.get("catid", "")
        if not name:
            self.redirect("Item name is required.", "error", "/manage")
            return
        store.add_item(db, name, catid)
        self.redirect("Item added.", "success", "/settings")

    def manage_add_station(self, db, data):
        name = data.get("name", "")
        code = data.get("code", "")
        systemid = data.get("systemid", "68")
        if not name or not code:
            self.redirect("Station name and code are required.", "error", "/settings")
            return
        store.add_station(db, name, code, systemid)
        self.redirect("Station added.", "success", "/settings")

    def respond_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _settings_upload_db(self):
        import base64
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = urllib.parse.parse_qs(body)
        filename = form.get("filename", [""])[0]
        filedata = form.get("filedata", [""])[0]
        if not filename or not filedata:
            self.respond_json({"error": "Missing file data"})
            return
        try:
            file_bytes = base64.b64decode(filedata)
        except Exception:
            self.respond_json({"error": "Invalid file data"}, HTTPStatus.BAD_REQUEST)
            return
        save_path = (UPLOAD_DIR / os.path.basename(filename)).resolve()
        save_path.write_bytes(file_bytes)
        global DATABASE, db_path, DB_COMPAT_WARNING
        save_config({"db_path": str(save_path)})
        DATABASE = save_path
        db_path = str(save_path)
        store.set_database(str(DATABASE))
        self._refresh_compat_warning()
        self.respond_json({"success": True, "path": str(save_path)})

    @staticmethod
    def _check_updates():
        """Check GitHub for newer versions of PITS and installed extensions."""
        import urllib.request
        results = {"pits": {"current": PITS_VERSION, "latest": None, "update_available": False, "zip_url": ""},
                   "extensions": {}}
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{PITS_REPO}/releases/latest",
                headers={"User-Agent": "PITS/0.3.0", "Accept": "application/vnd.github.v3+json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                tag = data.get("tag_name", "").lstrip("v")
                import re
                if re.match(r'^\d+\.\d+', tag) and tag != PITS_VERSION:
                    results["pits"]["latest"] = tag
                    results["pits"]["update_available"] = True
                    for a in data.get("assets", []):
                        if a.get("name", "").endswith(".dmg"):
                            results["pits"]["zip_url"] = a.get("browser_download_url", "")
        except Exception:
            pass

        for ext in EXTENSIONS:
            repo = getattr(ext, "repo_url", "")
            if not repo:
                continue
            try:
                req = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/releases/latest",
                    headers={"User-Agent": "PITS/0.3.0", "Accept": "application/vnd.github.v3+json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    tag = data.get("tag_name", "").lstrip("v")
                    current = getattr(ext, "version", "0")
                    if tag and tag != current:
                        zip_url = ""
                        for a in data.get("assets", []):
                            if a.get("name", "").endswith(".zip"):
                                zip_url = a.get("browser_download_url", "")
                        results["extensions"][ext.name] = {"current": current, "latest": tag, "update_available": True, "zip_url": zip_url}
            except Exception:
                pass
        return results

    @staticmethod
    def _apply_updates(data):
        """Apply extension updates, then restart PITS."""
        import urllib.request
        import zipfile, io
        # Apply extension updates first
        for ext_name, info in data.get("extensions", {}).items():
            if info.get("zip_url"):
                try:
                    dl = urllib.request.Request(info["zip_url"], headers={"User-Agent": "PITS/0.3.0"})
                    with urllib.request.urlopen(dl, timeout=30) as resp:
                        z = zipfile.ZipFile(io.BytesIO(resp.read()))
                        target = BASE_DIR / "extensions" / ext_name
                        if target.exists():
                            shutil.rmtree(target)
                        for name in z.namelist():
                            parts = name.split("/")
                            if len(parts) >= 2 and parts[0] == "extensions" and parts[1]:
                                rel = "/".join(parts[2:]) if len(parts) > 2 else ""
                                if rel:
                                    dest = target / rel
                                    dest.parent.mkdir(parents=True, exist_ok=True)
                                    if not name.endswith("/"):
                                        dest.write_bytes(z.read(name))
                except Exception:
                    pass

    def _settings_check_updates(self):
        results = self._check_updates()
        self.respond_json(results)

    def _settings_apply_updates(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        import json as _json
        data = _json.loads(body)
        self._apply_updates(data)
        self.respond_json({"success": True})
        self._schedule_restart()

    def _schedule_restart(self):
        import subprocess, sys, time
        time.sleep(0.5)
        try:
            subprocess.Popen([sys.executable, "-u"] + sys.argv)
        except Exception:
            pass
        os._exit(0)

    def _settings_toggle_extension(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = urllib.parse.parse_qs(body)
        ext_name = form.get("name", [""])[0]
        if not ext_name:
            self.respond_json({"error": "Missing extension name"})
            return
        cfg = load_config()
        exts_cfg = cfg.get("extensions", {})
        current = exts_cfg.get(ext_name, {}).get("enabled", True)
        if ext_name not in exts_cfg:
            exts_cfg[ext_name] = {}
        exts_cfg[ext_name]["enabled"] = not current
        save_config({"extensions": exts_cfg})
        new_enabled = not current

        if new_enabled:
            for ext_candidate in discover_extensions():
                if ext_candidate.name == ext_name:
                    ext_candidate.on_startup(globals())
                    EXTENSIONS.append(ext_candidate)
                    ctx = ext_candidate.get_context()
                    if hasattr(ext_candidate, "get_settings_html"):
                        ctx["_settings_html"] = ext_candidate.get_settings_html()
                    EXTENSION_CONTEXTS[ext_name] = ctx
                    break
        else:
            for i, ext in enumerate(EXTENSIONS):
                if ext.name == ext_name:
                    if hasattr(ext, "_ws_close"):
                        ext._ws_close()
                    del EXTENSIONS[i]
                    break
            EXTENSION_CONTEXTS.pop(ext_name, None)

        _refresh_ext_contexts()
        self.respond_json({"success": True, "enabled": new_enabled})

    def _settings_install_extension(self):
        import base64, zipfile, tempfile, shutil
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = urllib.parse.parse_qs(body)
        filename = form.get("filename", [""])[0]
        filedata = form.get("filedata", [""])[0]
        if not filename or not filedata:
            self.respond_json({"error": "Missing file data"})
            return
        try:
            file_bytes = base64.b64decode(filedata)
        except Exception:
            self.respond_json({"error": "Invalid file data"}, HTTPStatus.BAD_REQUEST)
            return

        ext_dir = BASE_DIR / "extensions"
        ext_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_zip = Path(tmpdir) / "upload.zip"
            tmp_zip.write_bytes(file_bytes)

            with zipfile.ZipFile(tmp_zip, 'r') as zf:
                names = zf.namelist()
                ext_subdirs = set()
                for name in names:
                    parts = name.split('/')
                    if len(parts) >= 3 and parts[0] == 'extensions' and parts[1] and not name.endswith('/'):
                        ext_subdirs.add(parts[1])

                if not ext_subdirs:
                    self.respond_json({"error": "No extension found. ZIP must contain extensions/<name>/__init__.py"})
                    return

                results = []
                for ext_name in ext_subdirs:
                    prefix = f"extensions/{ext_name}/"
                    target = ext_dir / ext_name
                    if target.exists():
                        shutil.rmtree(target)
                    for name in names:
                        if name.startswith(prefix) and not name.endswith('/'):
                            rel = name[len(prefix):]
                            dest = target / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(zf.read(name))

                    init_file = target / "__init__.py"
                    if not init_file.exists():
                        shutil.rmtree(target)
                        self.respond_json({"error": f"Missing __init__.py in {ext_name}"})
                        return

                    try:
                        import importlib
                        import sys
                        base_str = str(BASE_DIR.resolve())
                        if base_str not in sys.path:
                            sys.path.insert(0, base_str)
                        importlib.invalidate_caches()
                        if "extensions.jock_strap" in sys.modules:
                            del sys.modules["extensions.jock_strap"]
                        mod = importlib.import_module(f"extensions.{ext_name}")
                        found = None
                        for attr_name in dir(mod):
                            attr = getattr(mod, attr_name)
                            if isinstance(attr, type) and issubclass(attr, Extension) and attr is not Extension:
                                inst = attr()
                                found = {"ext_name": ext_name, "name": inst.name, "version": inst.version}
                                results.append(found)
                                inst.on_startup(globals())
                                EXTENSIONS.append(inst)
                                ctx = inst.get_context()
                                if hasattr(inst, "get_settings_html"):
                                    ctx["_settings_html"] = inst.get_settings_html()
                                EXTENSION_CONTEXTS[ext_name] = ctx
                                break
                        if not found:
                            shutil.rmtree(target)
                            self.respond_json({"error": f"No Extension subclass in {ext_name}"})
                            return
                    except Exception as e:
                        shutil.rmtree(target)
                        self.respond_json({"error": f"Failed to load {ext_name}: {e}"})
                        return

        _refresh_ext_contexts()
        self.respond_json({"success": True, "name": results[0]["name"], "version": results[0]["version"]})

    def _settings_remove_extension(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = urllib.parse.parse_qs(body)
        ext_name = form.get("name", [""])[0]
        if not ext_name:
            self.respond_json({"error": "Missing extension name"})
            return
        target = BASE_DIR / "extensions" / ext_name
        if target.exists():
            shutil.rmtree(target)
        cfg = load_config()
        exts_cfg = cfg.get("extensions", {})
        exts_cfg.pop(ext_name, None)
        save_config({"extensions": exts_cfg})
        self.respond_json({"success": True})

    def settings_save(self, data):
        global DATABASE, db_path, DB_COMPAT_WARNING
        new_path = data.get("db_path", "").strip()
        if not new_path:
            self.redirect("Database path is required.", "error", "/settings")
            return
        save_config({"db_path": new_path})
        DATABASE = Path(new_path)
        db_path = new_path
        store.set_database(str(DATABASE))
        self._refresh_compat_warning()
        self.redirect(f"Database path saved to {new_path}.", "success", "/manage")

    def settings_create(self, data):
        global DATABASE, db_path, DB_COMPAT_WARNING
        if "db_name" in data:
            db_name = data.get("db_name", "").strip()
            if not db_name:
                self.redirect("Database name is required.", "error", "/settings")
                return
            if not db_name.endswith(".db"):
                db_name += ".db"
            new_path = str((UPLOAD_DIR / db_name).resolve())
        else:
            new_path = data.get("db_path", "").strip()
        if not new_path:
            self.redirect("Database path is required.", "error", "/settings")
            return
        p = Path(new_path)
        if p.exists():
            self.redirect(f"File already exists: {new_path}", "error", "/settings")
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        save_config({"db_path": str(p)})
        DATABASE = p
        db_path = str(p)
        store.set_database(str(DATABASE))
        with store.connect() as db:
            store.create_tables(db)
            if DEFAULT_DB.exists():
                try:
                    src_db = sqlite3.connect(str(DEFAULT_DB))
                    src_db.row_factory = sqlite3.Row
                    for row in src_db.execute("SELECT id, Name, Code FROM systems").fetchall():
                        db.execute("INSERT OR IGNORE INTO systems (id, Name, Code) VALUES (?, ?, ?)", (row["id"], row["Name"], row["Code"]))
                    for row in src_db.execute("SELECT id, name, catid FROM item").fetchall():
                        db.execute("INSERT OR IGNORE INTO item (id, name, catid) VALUES (?, ?, ?)", (row["id"], row["name"], row["catid"]))
                    for row in src_db.execute("SELECT id, name, code, systemid FROM stations").fetchall():
                        db.execute("INSERT OR IGNORE INTO stations (id, name, code, systemid) VALUES (?, ?, ?, ?)", (row["id"], row["name"], row["code"], row["systemid"]))
                    db.commit()
                    src_db.close()
                except sqlite3.Error:
                    pass
        self._refresh_compat_warning()
        self.redirect(f"New database created at {new_path}.", "success", "/manage")

    def redirect(self, notice, kind="success", location="/manage"):
        from urllib.parse import urlencode
        sep = "&" if "?" in location else "?"
        location = location + sep + urlencode({"notice": notice, "kind": kind})
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

    def serve_static(self, path, content_type):
        if not path.exists():
            self.respond("Not found", HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def respond(self, body, status=HTTPStatus.OK):
        body_bytes = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):
        if "Bad request version" in str(args):
            return
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    load_templates()

    if PORT_ENV:
        PORT = int(PORT_ENV)
    else:
        PORT = find_port(preferred=config.get("port"))
        if config.get("port") != PORT:
            save_config({"port": PORT})

    local_ip = get_local_ip()
    LOCAL_URL = f"http://localhost:{PORT}"
    NETWORK_URL = f"http://{local_ip}:{PORT}"

    for ext in discover_extensions():
        cfg_exts = load_config().get("extensions", {})
        ext_cfg = cfg_exts.get(ext.name, {})
        if not ext_cfg.get("enabled", True):
            print(f"  Extension: {ext.name} v{ext.version} (disabled)")
            EXTENSION_CONTEXTS[ext.name] = {}
            continue
        ext.on_startup(globals())
        EXTENSIONS.append(ext)
        print(f"  Extension: {ext.name} v{ext.version}")

    def _refresh_ext_contexts():
        for ext in EXTENSIONS:
            ctx = ext.get_context()
            ctx["_settings_html"] = ext.get_settings_html() if hasattr(ext, "get_settings_html") else ""
            EXTENSION_CONTEXTS[ext.name] = ctx

    _refresh_ext_contexts()

    existing_db = DATABASE.exists()
    if not existing_db and DATABASE == DEFAULT_DB:
        bundled = BASE_DIR / "mainInventory"
        if bundled.exists():
            shutil.copy(str(bundled), str(DEFAULT_DB))

    if existing_db:
        with store.connect() as db:
            compatible, ver, warnings = store.check_compatibility(db)
            if warnings:
                if isinstance(warnings, list):
                    DB_COMPAT_WARNING = " ".join(warnings)
                else:
                    DB_COMPAT_WARNING = warnings

    with store.connect() as db:
        store.create_tables(db)

    print(f"Personal Inventory Tracker")
    print(f"  Local:    {LOCAL_URL}")
    print(f"  Network:  {NETWORK_URL}")
    print(f"  Database: {DATABASE}")
    webbrowser.open(LOCAL_URL)

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)

    if rumps and sys.platform == "darwin":
        icon_path = None
        for name in ICON_NAMES:
            for base in (BASE_DIR, DATA_DIR):
                p = base / name
                if p.exists():
                    icon_path = str(p)
                    break
            if icon_path:
                break

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        app_inst = rumps.App("PITS", icon=icon_path)
        app_inst.menu.add(rumps.MenuItem("Open", callback=lambda _: webbrowser.open(LOCAL_URL)))
        app_inst.run()

    elif pystray and sys.platform == "win32":
        icon_path = str(DATA_DIR / "icon_PITS.ico")
        if not os.path.exists(icon_path):
            icon_path = str(BASE_DIR / "icon_PITS.ico")
        if not os.path.exists(icon_path):
            icon_path = str(BASE_DIR / "icon_PITS.png")
        if not os.path.exists(icon_path):
            icon_path = None

        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        tray_icon = pystray.Icon(
            "PITS",
            PILImage.open(icon_path) if icon_path else PILImage.new("RGBA", (16, 16), (0, 0, 0, 0)),
            "Personal Inventory Tracker",
            pystray.Menu(
                pystray.MenuItem("Open", lambda: webbrowser.open(LOCAL_URL)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda: (server.shutdown(), tray_icon.stop())),
            ),
        )
        tray_icon.run()

    else:
        server.serve_forever()
