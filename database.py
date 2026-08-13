"""
SQLite persistence layer.

The GUI talks to repositories (plain dicts), never SQL directly.
"""

import os, sqlite3
from datetime import datetime

def app_data_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    p = os.path.join(base, "DailyDispatch")
    os.makedirs(p, exist_ok=True)
    return p

DEFAULT_SETTINGS = {
    "printer_name": "", "location_mode": "query", "location_query": "",
    "latitude": None, "longitude": None, "resolved_name": "",
    "unit_system": "metric", "time_format": "24h",
    "opt_qr": 1, "opt_logo": 0, "opt_barcode": 0, "updated_at": "",
}

DEFAULT_SCHEDULE = {
    "name": "Morning briefing",
    "enabled": 0,
    "days": "mon,tue,wed,thu,fri",
    "hour": 6,
    "minute": 0,
    "task_name": "",        # Windows Task Scheduler task name
    "created_at": "",
    "updated_at": "",
}

DAY_KEYS   = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL   = ["Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday"]


class Database:
    def __init__(self, path=None):
        self.path = path or os.path.join(app_data_dir(), "dispatch.db")
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                printer_name TEXT, location_mode TEXT, location_query TEXT,
                latitude REAL, longitude REAL, resolved_name TEXT,
                unit_system TEXT, time_format TEXT,
                opt_qr INTEGER, opt_logo INTEGER, opt_barcode INTEGER,
                updated_at TEXT
            )""")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                days TEXT NOT NULL DEFAULT '',
                hour INTEGER NOT NULL DEFAULT 6,
                minute INTEGER NOT NULL DEFAULT 0,
                task_name TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )""")
        # Migration: add task_name if upgrading from Phase 4
        try:
            self.conn.execute("SELECT task_name FROM schedules LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute(
                "ALTER TABLE schedules ADD COLUMN task_name TEXT DEFAULT ''")
        self.conn.commit()

    def close(self):
        try: self.conn.close()
        except Exception: pass


class SettingsRepository:
    _KEYS = list(DEFAULT_SETTINGS.keys())

    def __init__(self, db: Database):
        self.db = db

    def load(self) -> dict:
        row = self.db.conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        if row is None:
            return dict(DEFAULT_SETTINGS)
        d = dict(DEFAULT_SETTINGS)
        for k in self._KEYS:
            if k in row.keys():
                d[k] = row[k]
        return d

    def save(self, data: dict) -> dict:
        m = dict(DEFAULT_SETTINGS)
        m.update({k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
        m["updated_at"] = datetime.now().isoformat(timespec="seconds")
        cols = ["id"] + self._KEYS
        ph = ", ".join("?" for _ in cols)
        vals = [1] + [m[k] for k in self._KEYS]
        self.db.conn.execute(
            f"INSERT OR REPLACE INTO settings ({', '.join(cols)}) VALUES ({ph})", vals)
        self.db.conn.commit()
        return m


class ScheduleRepository:

    def __init__(self, db: Database):
        self.db = db

    def list_all(self) -> list[dict]:
        rows = self.db.conn.execute(
            "SELECT * FROM schedules ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get(self, schedule_id: int) -> dict | None:
        row = self.db.conn.execute(
            "SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
        return dict(row) if row else None

    def save(self, data: dict) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        sid = data.get("id")
        if sid:
            self.db.conn.execute("""
                UPDATE schedules SET name=?, enabled=?, days=?,
                    hour=?, minute=?, task_name=?, updated_at=?
                WHERE id=?""",
                (data["name"], int(data["enabled"]), data["days"],
                 int(data["hour"]), int(data["minute"]),
                 data.get("task_name", ""), now, sid))
        else:
            cur = self.db.conn.execute("""
                INSERT INTO schedules (name, enabled, days, hour, minute,
                    task_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["name"], int(data["enabled"]), data["days"],
                 int(data["hour"]), int(data["minute"]),
                 data.get("task_name", ""), now, now))
            data["id"] = cur.lastrowid
        self.db.conn.commit()
        data["updated_at"] = now
        return data

    def delete(self, schedule_id: int):
        self.db.conn.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        self.db.conn.commit()

    def duplicate(self, schedule_id: int) -> dict | None:
        src = self.get(schedule_id)
        if not src:
            return None
        src.pop("id", None)
        src["name"] = src["name"] + " (copy)"
        src["enabled"] = 0
        src["task_name"] = ""
        return self.save(src)
