import html
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode


if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

_templates = {}


def load_templates():
    template_dir = BASE_DIR / "templates"
    for name in ("base", "manage", "setup", "settings"):
        path = template_dir / f"{name}.html"
        if path.exists():
            _templates[name] = path.read_text(encoding="utf-8")
        else:
            _templates[name] = "{{content}}"


def render_template(name, **vars):
    html_content = _templates.get(name, "{{content}}")
    for key, value in vars.items():
        html_content = html_content.replace("{{" + key + "}}", str(value))
    return html_content


def escape(value):
    if value is None or value == "":
        return "&mdash;"
    return html.escape(str(value), quote=True)


def scu_from_cents(value):
    cents = int(value or 0)
    return f"{cents / 100:,.2f} SCU"


def cents_from_scu(value):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None
    if amount <= 0:
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def option_list(options, placeholder, name, value_key="id", label_key="name", required=False, selected=None):
    required_attr = " required" if required else ""
    placeholder_selected = " selected" if selected is None else ""
    items = [f'<option value=""{placeholder_selected}>{html.escape(placeholder)}</option>']
    for option in options:
        is_selected = str(option[value_key]) == str(selected)
        selected_attr = " selected" if is_selected else ""
        items.append(f'<option value="{escape(option[value_key])}"{selected_attr}>{escape(option[label_key])}</option>')
    return f'<select name="{name}" aria-label="{html.escape(placeholder)}"{required_attr}>{"".join(items)}</select>'


def qs_params(base, overrides):
    merged = dict(base)
    merged.update(overrides)
    return "?" + urlencode({k: v for k, v in merged.items() if v is not None and v != ""})


def render_pagination_nav(base_params, total, page, per_page, page_key="page", per_page_key="per_page"):
    if total <= per_page:
        return ""
    pages = max(1, (total + per_page - 1) // per_page)

    def p_link(p):
        return qs_params(base_params, {page_key: str(p)})

    prev_page = str(max(1, page - 1))
    next_page = str(min(pages, page + 1))
    rows = []
    for v, label, disabled in [
        (str(pages), "\u00bb", page >= pages),
        (next_page, "\u203a", page >= pages),
        ("1", "\u2039", page <= 1),
        (prev_page, "\u00ab", page <= 1),
    ]:
        if disabled:
            rows.append(f'<span class="page-btn disabled">{"".join(c for c in label)}</span>')
        else:
            rows.append(f'<a class="page-btn" href="{p_link(v)}">{"".join(c for c in label)}</a>')

    nav = (
        f'<div class="pagination">'
        f'<span class="page-info">Page {page} of {pages}</span>'
        + "".join(rows)
        + f'<select class="page-size" onchange="changePerPage(this)"><option value="">Per page</option>'
        + "".join(
            f'<option value="{qs_params(base_params, {per_page_key: str(v), page_key: "1"})}"{" selected" if int(v) == per_page else ""}>{v} per page</option>'
            for v in (5, 10, 25, 50)
        )
        + f'</select></div>'
    )
    return nav


def ext_context(extensions_ctx=None):
    styles = ""
    scripts = ""
    nav_items = ""
    ext_data = {}
    if extensions_ctx:
        for ext_name, ctx in extensions_ctx.items():
            for k, v in ctx.items():
                if k == "_nav_html":
                    nav_items += str(v)
                elif not k.startswith("_"):
                    ext_data[k] = v
    return {
        "ext_styles": styles,
        "ext_scripts": scripts,
        "ext_nav_items": nav_items,
        "ext_data": ext_data,
        "ext_data_json": json.dumps(ext_data, ensure_ascii=False),
    }


def wrap_page(content, notice="", kind="success", prefs=None, local_url="", network_url="", db_compat_warning=None, ext_ctx=None):
    notice_html = ""
    if db_compat_warning:
        notice_html += f'<div class="messages"><div class="message warning">{escape(db_compat_warning)}</div></div>'
    if notice:
        notice_html += f'<div class="messages"><div class="message {escape(kind)}">{escape(notice)}</div></div>'
    theme_class = "light" if prefs and prefs.get("theme") == "light" else "dark"
    ctx = {"notice_html": notice_html, "content": content,
           "theme_class": theme_class, "local_url": escape(local_url),
           "network_url": escape(network_url)}
    if ext_ctx:
        ec = ext_context(ext_ctx)
        ctx.update(ec)
    return render_template("base", **ctx)


def render_setup(missing, local_url="", network_url="", db_compat_warning=None):
    missing_list = "".join(f"<li>{escape(table)}</li>" for table in missing)
    content = render_template("setup", missing_list=missing_list)
    return wrap_page(content, local_url=local_url, network_url=network_url, db_compat_warning=db_compat_warning)


def render_settings(db_path, db=None, store=None, prefs=None, local_url="", network_url="", db_compat_warning=None, ext_ctx=None):
    system_select = ""
    schema_version = ""
    ext_settings_html = ""
    if db and store:
        systems = store.systems(db)
        system_select = option_list(systems, "Star System", "systemid", value_key="id", label_key="Code", required=True)
        schema_version = str(store.get_schema_version(db))
    if ext_ctx:
        sections = []
        for name, ctx in ext_ctx.items():
            html = ctx.get("_settings_html", "")
            if html:
                sections.append(html)
        ext_settings_html = "\n".join(sections)
    content = render_template("settings", db_path=escape(str(db_path)), system_select=system_select, schema_version=escape(schema_version), ext_settings=ext_settings_html)
    return wrap_page(content, prefs=prefs, local_url=local_url, network_url=network_url, db_compat_warning=db_compat_warning, ext_ctx=ext_ctx)


def render_manage(db, qs, store, prefs=None, local_url="", network_url="", db_compat_warning=None, ext_ctx=None):
    page = int(qs.get("page", "1"))
    per_page = int(qs.get("per_page", prefs.get("per_page", "15") if prefs else "15"))
    search = qs.get("q", "").strip()
    qual_min = qs.get("qual_min")
    qual_max = qs.get("qual_max")
    qty_min = qs.get("qty_min")
    qty_max = qs.get("qty_max")

    qual_min = int(qual_min) if qual_min else None
    qual_max = int(qual_max) if qual_max else None
    qty_min_cents = cents_from_scu(qty_min) if qty_min else None
    qty_max_cents = cents_from_scu(qty_max) if qty_max else None

    rows, total = store.all_inventory_detail(
        db, page, per_page,
        search=search,
        qual_min=qual_min, qual_max=qual_max,
        qty_min=qty_min_cents, qty_max=qty_max_cents,
    )
    items = store.items(db)
    stations = store.stations(db)
    add_items_json = json.dumps([{"id": r["id"], "name": r["name"]} for r in items], ensure_ascii=False)
    add_stations_json = json.dumps([{"id": r["id"], "name": r["name"]} for r in stations], ensure_ascii=False)

    rows_html = []
    for r in rows:
        if r['station_name']:
            label = r['station_code'] if len(r['station_name']) > 15 else r['station_name']
            station_info = f"{escape(label)} ({escape(r['system_code'])})"
        else:
            station_info = "&mdash;"
        eid = f"medit-{r['id']}"
        station_name = escape(r["station_name"]) if r["station_name"] else ""
        station_id = str(r["stationid"] or "")
        edit_station = (
            f'<div class="autocomplete-wrap" style="display:inline-block;position:relative">'
            f'<input type="text" value="{station_name}" placeholder="Station" autocomplete="off" oninput="stationAutocomplete(this)" style="width:140px" class="sm-input">'
            f'<input type="hidden" name="stationid" class="station-id" value="{station_id}">'
            f'<div class="search-suggestions" style="display:none"></div>'
            f'</div>'
        )
        form_html = (
            f'<form action="/manage/update" method="post" class="inline-form">'
            f'<input type="hidden" name="inv_id" value="{r["id"]}">'
            f'{option_list(items, "Item", "itemid", selected=r["itemid"], required=True)}'
            f'{edit_station}'
            f'<input name="qual" type="number" min="0" value="{escape(r["qual"])}" aria-label="Quality" required class="sm-input">'
            f'<input name="qty_scu" type="number" min="0.01" step="0.01" value="{r["qty"] / 100:.2f}" aria-label="QTY in SCU" required class="sm-input">'
            f'<button type="submit">Save</button>'
            f'</form>'
        )
        rows_html.append(
            f"<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{escape(r['item_name'])}</td>"
            f"<td>{station_info}</td>"
            f"<td>{escape(r['qual'])}</td>"
            f"<td>{scu_from_cents(r['qty'])}</td>"
            f'<td class="cell-actions">'
            f'<button class="action-btn" data-modal="{eid}" onclick="openModalFrom(this,\'Edit Inventory Row #{r["id"]}\')">Edit</button>'
            f'<div id="{eid}" style="display:none">{form_html}</div>'
            f'<form action="/manage/delete" method="post" onsubmit="return confirm(\'Delete inventory row #{r["id"]}?\')">'
            f'<input type="hidden" name="inv_id" value="{r["id"]}">'
            f'<button class="danger-button" type="submit">Del</button>'
            f'</form>'
            f"</td>"
            f"</tr>"
        )
    if not rows_html:
        rows_html = ['<tr><td colspan="6" class="empty">No inventory rows yet.</td></tr>']

    nav = render_pagination_nav({k: v for k, v in qs.items() if k not in ("page",)}, total, page, per_page)

    content = render_template(
        "manage",
        add_items_json=add_items_json,
        add_stations_json=add_stations_json,
        inventory_rows="".join(rows_html),
        nav=nav,
        search_query=html.escape(search, quote=True),
        qual_min=html.escape(str(qual_min if qual_min is not None else "0"), quote=True),
        qual_max=html.escape(str(qual_max if qual_max is not None else "1000"), quote=True),
        qty_min=html.escape(str(qty_min if qty_min else ""), quote=True),
        qty_max=html.escape(str(qty_max if qty_max else ""), quote=True),
    )
    return wrap_page(content, prefs=prefs, local_url=local_url, network_url=network_url, db_compat_warning=db_compat_warning, ext_ctx=ext_ctx)
