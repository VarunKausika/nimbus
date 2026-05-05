import sqlite3
from dataclasses import dataclass
from pathlib import Path

NIMBUS_DIR = Path.home() / ".nimbus"
DB_PATH = NIMBUS_DIR / "state.db"

DDL = """
CREATE TABLE IF NOT EXISTS observations (
    id            INTEGER PRIMARY KEY,
    ts            INTEGER NOT NULL,
    radio         TEXT NOT NULL,
    mac_hash      TEXT NOT NULL,
    rssi          INTEGER,
    channel       INTEGER,
    frame_type    TEXT,
    extra_json    TEXT
);
CREATE INDEX IF NOT EXISTS obs_ts  ON observations(ts);
CREATE INDEX IF NOT EXISTS obs_mac ON observations(mac_hash);

CREATE TABLE IF NOT EXISTS devices (
    mac_hash        TEXT PRIMARY KEY,
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL,
    observation_n   INTEGER NOT NULL,
    vendor_oui      TEXT,
    inferred_class  TEXT
);

CREATE TABLE IF NOT EXISTS labels (
    mac_hash TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    set_at   INTEGER NOT NULL
);
"""


@dataclass
class Observation:
    ts: int
    radio: str          # 'wifi' | 'ble'
    mac_hash: str
    rssi: int | None
    channel: int | None
    frame_type: str | None
    extra_json: str | None


def open_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)
    conn.commit()
    return conn
