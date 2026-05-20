import sqlite3

SCHEMA_VERSION = 2


def db_connect(database, timeout=10):
    db = sqlite3.connect(database, timeout=timeout)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        db.execute("PRAGMA journal_mode=DELETE")
    db.execute("PRAGMA foreign_keys = ON")
    return db


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


class InventoryStore:
    REQUIRED_TABLES = ("inventory", "item", "stations", "systems")

    def __init__(self, database):
        self.database = database

    def set_database(self, path):
        self.database = path

    def connect(self):
        return db_connect(self.database)

    def get_schema_version(self, db):
        if not self.table_exists(db, "_meta"):
            return 0
        row = db.execute("SELECT value FROM _meta WHERE key = 'schema_version'").fetchone()
        return int(row["value"]) if row else 0

    def set_schema_version(self, db, version):
        db.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )
        db.commit()

    def check_compatibility(self, db):
        warnings = []
        current_version = self.get_schema_version(db)
        missing = self.missing_tables(db)

        if missing:
            return False, current_version, f"Missing tables: {', '.join(missing)}"

        if current_version == 0:
            warnings.append("Database has no schema version — may be from an older app version.")
            return True, 0, warnings
        elif current_version < SCHEMA_VERSION:
            warnings.append(
                f"Database schema v{current_version} is older than app schema v{SCHEMA_VERSION}. "
                "The app will attempt to use it, but some features may not work."
            )
            return True, current_version, warnings
        elif current_version > SCHEMA_VERSION:
            warnings.append(
                f"Database schema v{current_version} is newer than app schema v{SCHEMA_VERSION}. "
                "The app may not function correctly with this database."
            )
            return True, current_version, warnings

        return True, current_version, None

    def create_tables(self, db):
        db.execute("CREATE TABLE IF NOT EXISTS item (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, catid INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS systems (id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT NOT NULL, Code TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS stations (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL, systemid INTEGER, FOREIGN KEY (systemid) REFERENCES systems(id))")
        db.execute("""CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            itemid INTEGER NOT NULL,
            qual INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            stationid INTEGER,
            FOREIGN KEY (itemid) REFERENCES item(id),
            FOREIGN KEY (stationid) REFERENCES stations(id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS itemcategory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER DEFAULT 0
        )""")
        db.commit()
        db.execute("INSERT OR IGNORE INTO systems (id, Name, Code) VALUES (68, 'Stanton', 'ST')")
        db.commit()
        db.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)")
        current_v = self.get_schema_version(db)
        if current_v < 2:
            self._migrate_to_v2(db)
        if current_v == 0:
            self.set_schema_version(db, SCHEMA_VERSION)
        db.commit()

    def _migrate_to_v2(self, db):
        olds = [row["name"] for row in db.execute("PRAGMA table_info(item)").fetchall()]
        if "hasquality" not in olds:
            db.execute("ALTER TABLE item ADD COLUMN hasquality INTEGER DEFAULT 0")
        if "code" not in olds:
            db.execute("ALTER TABLE item ADD COLUMN code TEXT DEFAULT ''")
        if db.execute("SELECT COUNT(*) FROM itemcategory").fetchone()[0] == 0:
            cats = [(1, "Commodity", 0), (2, "Ores", 1), (3, "Vehicle Mining", 1),
                    (4, "FPS Mining", 1), (5, "Harvestable", 1), (6, "Salvage", 1)]
            for c in cats:
                db.execute("INSERT OR IGNORE INTO itemcategory (id, name, parent_id) VALUES (?, ?, ?)", c)
        # Set catid assignments
        cat_map = {
            2: [1, 5, 7, 11, 13, 15, 20, 22, 33, 39, 101, 44, 47, 184, 194, 58, 60, 124, 188, 100, 122, 73, 103, 75, 190, 77],
            3: [167, 170, 169, 168],
            4: [8, 179, 178, 28, 36, 171, 46, 200, 172],
            5: [105, 24, 35, 37, 55, 57, 65, 66, 72, 198, 18],
            6: [63, 181, 182, 183],
        }
        for catid, ids in cat_map.items():
            for iid in ids:
                db.execute("UPDATE item SET catid=? WHERE id=?", (catid, iid))
        db.execute("UPDATE item SET hasquality=1 WHERE catid IN (2,3,4)")
        # Add new items with IDs
        new_items = [
            (178, "Carinite Pure", 4, "CARIP"),
            (172, "Saldynium", 4, "SALD"),
        ]
        for iid, name, catid, code in new_items:
            db.execute("INSERT OR IGNORE INTO item (id, name, catid, code, hasquality) VALUES (?, ?, ?, ?, 1)", (iid, name, catid, code))
        # Add items without fixed IDs
        for name, catid, code in [("Amiant", 4, "AMIA"), ("Flareweed", 4, "FLWD"), ("Fotia", 4, "FTIA"), ("Pingala", 4, "PNGL")]:
            existing = db.execute("SELECT id FROM item WHERE name=?", (name,)).fetchone()
            if not existing:
                db.execute("INSERT INTO item (name, catid, code, hasquality) VALUES (?, ?, ?, 1)", (name, catid, code))
        self.set_schema_version(db, 2)
        db.execute("INSERT OR IGNORE INTO systems (id, Name, Code) VALUES (68, 'Stanton', 'ST')")
        db.commit()

        db.execute("CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)")
        if self.get_schema_version(db) == 0:
            self.set_schema_version(db, SCHEMA_VERSION)
        db.commit()

        # Migrate old databases: remove userid column from inventory, then drop users
        cols = [row["name"] for row in db.execute("PRAGMA table_info(inventory)")]
        if "userid" in cols or self.table_exists(db, "users"):
            mig = sqlite3.connect(self.database)
            mig.row_factory = sqlite3.Row
            mig.execute("PRAGMA foreign_keys = OFF")
            try:
                mcols = [row["name"] for row in mig.execute("PRAGMA table_info(inventory)")]
                if "userid" in mcols:
                    mig.execute("DROP TABLE IF EXISTS inventory_new")
                    mig.execute("""CREATE TABLE inventory_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        itemid INTEGER NOT NULL,
                        qual INTEGER NOT NULL,
                        qty INTEGER NOT NULL,
                        stationid INTEGER,
                        FOREIGN KEY (itemid) REFERENCES item(id),
                        FOREIGN KEY (stationid) REFERENCES stations(id)
                    )""")
                    mig.execute("INSERT INTO inventory_new (id, itemid, qual, qty, stationid) SELECT id, itemid, qual, qty, stationid FROM inventory")
                    mig.execute("DROP TABLE inventory")
                    mig.execute("ALTER TABLE inventory_new RENAME TO inventory")
                if mig.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
                    mig.execute("DROP TABLE IF EXISTS users")
                mig.commit()
            finally:
                mig.execute("PRAGMA foreign_keys = ON")
                mig.close()

    def table_exists(self, db, table):
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def table_columns(self, db, table):
        if not self.table_exists(db, table):
            return []
        return [row["name"] for row in db.execute(f"PRAGMA table_info({quote_identifier(table)})")]

    def missing_tables(self, db):
        return [
            table
            for table in self.REQUIRED_TABLES
            if not self.table_exists(db, table)
        ]

    def items(self, db):
        return db.execute("SELECT id, name FROM item ORDER BY name").fetchall()

    def all_items(self, db, page=1, per_page=50):
        count_row = db.execute("SELECT COUNT(*) AS cnt FROM item").fetchone()
        total = count_row["cnt"] if count_row else 0
        offset = (int(page) - 1) * int(per_page)
        rows = db.execute(
            "SELECT id, name, catid FROM item ORDER BY name LIMIT ? OFFSET ?",
            (int(per_page), offset),
        ).fetchall()
        return rows, total

    def items(self, db):
        return db.execute("SELECT id, name, catid, hasquality, code FROM item ORDER BY name").fetchall()

    def all_items(self, db, page=1, per_page=50):
        count_row = db.execute("SELECT COUNT(*) AS cnt FROM item").fetchone()
        total = count_row["cnt"] if count_row else 0
        offset = (int(page) - 1) * int(per_page)
        rows = db.execute(
            "SELECT id, name, catid, hasquality, code FROM item ORDER BY name LIMIT ? OFFSET ?",
            (int(per_page), offset),
        ).fetchall()
        return rows, total

    def add_item(self, db, name, catid, item_id=None, hasquality=0, code=""):
        if item_id:
            db.execute("INSERT INTO item (id, name, catid, hasquality, code) VALUES (?, ?, ?, ?, ?)",
                       (int(item_id), name, int(catid) if catid else None, int(hasquality), code))
        else:
            db.execute("INSERT INTO item (name, catid, hasquality, code) VALUES (?, ?, ?, ?)",
                       (name, int(catid) if catid else None, int(hasquality), code))
        db.commit()

    def update_item(self, db, item_id, name, catid, hasquality=0, code=""):
        db.execute("UPDATE item SET name=?, catid=?, hasquality=?, code=? WHERE id=?",
                   (name, int(catid) if catid else None, int(hasquality), code, int(item_id)))
        db.commit()

    def delete_item(self, db, item_id):
        db.execute("DELETE FROM item WHERE id=?", (int(item_id),))
        db.commit()

    def categories(self, db):
        return db.execute("SELECT * FROM itemcategory ORDER BY id").fetchall()

    def systems(self, db):
        return db.execute("SELECT id, Name, Code FROM systems ORDER BY Name").fetchall()

    def stations(self, db):
        return db.execute(
            """
            SELECT s.id, s.name, s.code, sy.Code AS system_code
            FROM stations s
            LEFT JOIN systems sy ON sy.id = s.systemid
            ORDER BY s.name
            """
        ).fetchall()

    def all_stations(self, db, page=1, per_page=50):
        count_row = db.execute("SELECT COUNT(*) AS cnt FROM stations").fetchone()
        total = count_row["cnt"] if count_row else 0
        offset = (int(page) - 1) * int(per_page)
        rows = db.execute(
            """
            SELECT s.id, s.name, s.code, s.systemid, sy.Code AS system_code
            FROM stations s
            LEFT JOIN systems sy ON sy.id = s.systemid
            ORDER BY s.name LIMIT ? OFFSET ?
            """,
            (int(per_page), offset),
        ).fetchall()
        return rows, total

    def add_station(self, db, name, code, systemid):
        db.execute(
            "INSERT INTO stations (name, code, systemid) VALUES (?, ?, ?)",
            (name, code, int(systemid) if systemid else None),
        )
        db.commit()

    def update_station(self, db, station_id, name, code, systemid):
        db.execute(
            "UPDATE stations SET name=?, code=?, systemid=? WHERE id=?",
            (name, code, int(systemid) if systemid else None, int(station_id)),
        )
        db.commit()

    def delete_station(self, db, station_id):
        db.execute("DELETE FROM stations WHERE id=?", (int(station_id),))
        db.commit()

    def all_inventory_detail(self, db, page=1, per_page=15, search="",
                              qual_min=None, qual_max=None,
                              qty_min=None, qty_max=None):
        conditions = []
        params = []

        if search:
            conditions.append("item.name LIKE ?")
            params.append(f"%{search}%")
        if qual_min is not None:
            conditions.append("inv.qual >= ?")
            params.append(int(qual_min))
        if qual_max is not None:
            conditions.append("inv.qual <= ?")
            params.append(int(qual_max))
        if qty_min is not None:
            conditions.append("inv.qty >= ?")
            params.append(int(qty_min))
        if qty_max is not None:
            conditions.append("inv.qty <= ?")
            params.append(int(qty_max))

        where_clause = ""
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)

        count_row = db.execute(
            f"SELECT COUNT(*) AS cnt FROM inventory inv LEFT JOIN item ON item.id = inv.itemid{where_clause}",
            params,
        ).fetchone()
        total = count_row["cnt"] if count_row else 0
        offset = (int(page) - 1) * int(per_page)

        query = f"""
            SELECT inv.*, item.name AS item_name,
                   st.name AS station_name, st.code AS station_code, sy.Code AS system_code
            FROM inventory inv
            LEFT JOIN item ON item.id = inv.itemid
            LEFT JOIN stations st ON st.id = inv.stationid
            LEFT JOIN systems sy ON sy.id = st.systemid
            {where_clause}
            ORDER BY inv.id DESC
            LIMIT ? OFFSET ?
        """
        rows = db.execute(query, params + [int(per_page), offset]).fetchall()
        return rows, total

    def add_inventory(self, db, itemid, qual, qty, stationid):
        existing = db.execute(
            "SELECT id, qty FROM inventory WHERE itemid=? AND qual=? AND stationid IS ?",
            (int(itemid), int(qual), int(stationid) if stationid else None)
        ).fetchone()
        if existing:
            db.execute("UPDATE inventory SET qty=qty+? WHERE id=?", (int(qty), existing["id"]))
        else:
            db.execute(
                "INSERT INTO inventory (itemid, qual, qty, stationid) VALUES (?, ?, ?, ?)",
                (int(itemid), int(qual), int(qty), int(stationid) if stationid else None),
            )
        db.commit()

    def update_inventory(self, db, inv_id, itemid, qual, qty, stationid):
        db.execute(
            "UPDATE inventory SET itemid=?, qual=?, qty=?, stationid=? WHERE id=?",
            (int(itemid), int(qual), int(qty), int(stationid) if stationid else None, int(inv_id)),
        )
        db.commit()

    def delete_inventory(self, db, inv_id):
        db.execute("DELETE FROM inventory WHERE id=?", (int(inv_id),))
        db.commit()
