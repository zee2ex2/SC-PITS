import json
import os
import threading
import urllib.parse
import urllib.request
from http import HTTPStatus
from pathlib import Path

from extensions import Extension

AUTH_FILE = None
DISCORD_API = "https://discord.com/api/v10"

CONFIG_DEFAULTS = {
    "client_id": "",
    "client_secret": "",
    "guild_id": "",
    "required_roles": "",
}

SYNC_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS ext_discord_users (
    discord_id TEXT PRIMARY KEY,
    discord_tag TEXT,
    access_token TEXT,
    refresh_token TEXT,
    expires_at REAL,
    guild_roles TEXT,
    linked_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ext_discord_config (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS ext_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT,
    status TEXT,
    message TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ext_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    title TEXT,
    body TEXT,
    read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ext_order_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT,
    min_quality INTEGER DEFAULT 1,
    quantity INTEGER DEFAULT 1,
    created_by_discord TEXT,
    status TEXT DEFAULT 'open',
    assigned_to_discord TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def get_data_dir():
    if getattr(os, 'environ', None):
        return Path(os.environ.get("EXT_DISCORD_DATA", str(Path.home() / ".config" / "sc-pits-discord")))
    return Path(__file__).resolve().parent / "data"


def load_auth():
    global AUTH_FILE
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    AUTH_FILE = d / "auth.json"
    if AUTH_FILE.exists():
        try:
            return json.loads(AUTH_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_auth(data):
    if AUTH_FILE:
        AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTH_FILE.write_text(json.dumps(data, indent=2))


def discord_api_request(method, endpoint, token=None, body=None):
    url = f"{DISCORD_API}/{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        detail = e.read().decode() if e.fp else ""
        return None, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return None, str(e)


def exchange_code(code, redirect_uri, client_id, client_secret):
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode()
    resp, err = discord_api_request("POST", "oauth2/token", body=data)
    return resp, err


def refresh_access_token(refresh_token, client_id, client_secret):
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    resp, err = discord_api_request("POST", "oauth2/token", body=data)
    return resp, err


def get_guild_member(guild_id, user_id, bot_token):
    resp, err = discord_api_request("GET", f"guilds/{guild_id}/members/{user_id}", token=bot_token)
    return resp, err


class DiscordAuthExtension(Extension):
    name = "discord_auth"
    version = "1.0"
    description = "Discord OAuth login, guild verification, role sync"

    def on_startup(self, g):
        self.g = g
        auth = load_auth()
        g["ext_discord_auth"] = auth
        g["ext_discord_config"] = CONFIG_DEFAULTS.copy()

    def get_context(self):
        auth = self.g.get("ext_discord_auth", {})
        config = self.g.get("ext_discord_config", {})
        logged_in = bool(auth.get("access_token"))
        return {
            "ext_discord_logged_in": str(logged_in).lower(),
            "ext_discord_tag": auth.get("discord_tag", ""),
            "ext_discord_guild_verified": str(auth.get("guild_verified", False)).lower(),
            "ext_discord_roles": auth.get("guild_roles", ""),
            "ext_discord_client_id": config.get("client_id", ""),
        }

    def get_settings_html(self):
        config = self.g.get("ext_discord_config", {})
        auth = self.g.get("ext_discord_auth", {})
        logged_in = bool(auth.get("access_token"))
        tag = auth.get("discord_tag", "")
        roles = auth.get("guild_roles", "")
        verified = auth.get("guild_verified", False)
        rows = ""
        for key, default in CONFIG_DEFAULTS.items():
            val = config.get(key, default)
            rows += f"""
            <tr>
                <td><label for="discord_{key}">{key.replace('_', ' ').title()}</label></td>
                <td><input type="text" id="discord_{key}" name="discord_{key}" value="{val}" style="width:100%;font-family:monospace"></td>
            </tr>"""
        status_color = "var(--accent)" if verified else "var(--danger)"
        status_text = "Verified" if verified else "Not Verified"
        login_section = ""
        if logged_in:
            login_section = f"""
            <p style="margin:12px 0">Logged in as <strong>{tag}</strong></p>
            <p style="margin:4px 0">Guild: <span style="color:{status_color}">{status_text}</span></p>
            <p style="margin:4px 0">Roles: {roles}</p>
            <form action="/ext/discord/logout" method="post" style="display:inline">
                <button type="submit" class="danger-button">Disconnect Discord</button>
            </form>
            <form action="/ext/discord/sync" method="post" style="display:inline;margin-left:8px">
                <button type="submit">Sync Now</button>
            </form>
            """
        else:
            cid = config.get("client_id", "")
            if cid:
                redirect = self.g.get("LOCAL_URL", "http://localhost:9100")
                encoded = urllib.parse.quote(f"{redirect}/ext/discord/callback")
                url = f"https://discord.com/api/oauth2/authorize?client_id={cid}&response_type=code&redirect_uri={encoded}&scope=identify+guilds+guilds.members.read"
                login_section = f'<a class="button" href="{url}" style="margin-top:8px;display:inline-block">Login with Discord</a>'
            else:
                login_section = '<p class="subtle">Set Client ID above, then save to enable Discord login.</p>'

        return f"""
        <section class="panel">
            <div class="section-heading"><h2>Discord Auth</h2></div>
            <form action="/ext/discord/config" method="post">
                <table class="settings-table" style="width:100%">
                    <tbody>{rows}</tbody>
                </table>
                <div style="margin-top:12px;display:flex;gap:8px;align-items:center">
                    <button type="submit">Save Config</button>
                </div>
            </form>
            <hr style="border:none;border-top:1px solid var(--line);margin:16px 0">
            {login_section}
        </section>
        <section class="panel">
            <div class="section-heading"><h2>Community Sync</h2></div>
            <p>Sync your local inventory with the community database.</p>
            <form action="/ext/discord/sync-settings" method="post" style="margin-top:8px">
                <label class="checkbox-label">
                    <input type="checkbox" name="auto_sync" value="1" checked>
                    Auto-sync changes to community
                </label>
                <div style="margin-top:12px">
                    <label style="display:block;margin-bottom:4px;font-size:13px;color:var(--muted)">Community API URL</label>
                    <input type="text" name="community_url" value="" placeholder="http://localhost:9200" style="width:100%;font-family:monospace">
                </div>
                <button type="submit" style="margin-top:8px">Save Sync Settings</button>
            </form>
        </section>
        """

    def on_route(self, path, qs, data, method):
        if not path.startswith("/ext/discord/"):
            return None, False
        handlers = {
            "/ext/discord/callback": self._handle_callback,
            "/ext/discord/config": self._handle_config,
            "/ext/discord/logout": self._handle_logout,
            "/ext/discord/sync": self._handle_sync,
            "/ext/discord/sync-settings": self._handle_sync_settings,
        }
        handler = handlers.get(path)
        if not handler:
            return None, False
        return handler(qs, data, method)

    def _handle_config(self, qs, data, method):
        if method != "POST" or not data:
            return self._redirect("/settings")
        config = self.g.get("ext_discord_config", {})
        for key in CONFIG_DEFAULTS:
            val = data.get(f"discord_{key}", "")
            config[key] = val
        self.g["ext_discord_config"] = config
        return self._redirect("/settings", "Discord config saved.")

    def _handle_logout(self, qs, data, method):
        if method != "POST":
            return None, False
        save_auth({})
        self.g["ext_discord_auth"] = {}
        return self._redirect("/settings", "Disconnected from Discord.")

    def _handle_callback(self, qs, data, method):
        code = qs.get("code", "")
        error = qs.get("error", "")
        if error or not code:
            return self._redirect("/settings", f"Discord auth error: {error}", "error")
        config = self.g.get("ext_discord_config", {})
        cid = config.get("client_id", "")
        secret = config.get("client_secret", "")
        guild_id = config.get("guild_id", "")
        if not cid or not secret:
            return self._redirect("/settings", "Discord not configured.", "error")
        local_url = self.g.get("LOCAL_URL", "http://localhost:9100")
        redirect_uri = f"{local_url}/ext/discord/callback"
        token_data, err = exchange_code(code, redirect_uri, cid, secret)
        if err or not token_data:
            return self._redirect("/settings", f"Token exchange failed: {err}", "error")
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        user_data, err = discord_api_request("GET", "users/@me", token=access_token)
        if err or not user_data:
            return self._redirect("/settings", f"Failed to get user: {err}", "error")
        discord_id = user_data.get("id")
        discord_tag = f"{user_data.get('username')}#{user_data.get('discriminator', '0')}"
        guild_verified = False
        guild_roles = ""
        if guild_id:
            member_data, m_err = get_guild_member(guild_id, discord_id, None)
            if member_data:
                guild_verified = True
                guild_roles = ", ".join(member_data.get("roles", []))
        auth = {
            "discord_id": discord_id,
            "discord_tag": discord_tag,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": token_data.get("expires_in", 0),
            "guild_verified": guild_verified,
            "guild_roles": guild_roles,
        }
        save_auth(auth)
        self.g["ext_discord_auth"] = auth
        status = "Connected!" if guild_verified else "Connected but guild not verified."
        return self._redirect("/settings", status)

    def _handle_sync(self, qs, data, method):
        if method != "POST":
            return None, False
        auth = self.g.get("ext_discord_auth", {})
        if not auth.get("access_token"):
            return self._redirect("/settings", "Not connected to Discord.", "error")
        return self._redirect("/settings", "Sync initiated (placeholder).")

    def _handle_sync_settings(self, qs, data, method):
        if method != "POST":
            return None, False
        return self._redirect("/settings", "Sync settings saved.")

    def _redirect(self, location, notice="", kind="success"):
        from urllib.parse import urlencode
        sep = "&" if "?" in location else "?"
        if notice:
            location += sep + urlencode({"notice": notice, "kind": kind})
        body = f"""<!doctype html><html><body>
        <script>window.location.href='{location}';</script>
        <a href="{location}">Redirect</a></body></html>"""
        return body, True
