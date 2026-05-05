import sqlite3

from .schemas import (
    BLEScanResult,
    CollectorStats,
    DeviceIdentity,
    PresenceDiff,
    PresenceReport,
    RegularDevice,
    Timeline,
    WiFiScanResult,
)


def who_is_here(conn: sqlite3.Connection, since: str = "5m", min_observations: int = 3) -> PresenceReport:
    raise NotImplementedError


def scan_wifi(conn: sqlite3.Connection, duration_s: int = 10) -> WiFiScanResult:
    raise NotImplementedError


def scan_ble(conn: sqlite3.Connection, duration_s: int = 10) -> BLEScanResult:
    raise NotImplementedError


def identify(conn: sqlite3.Connection, mac_or_hash: str) -> DeviceIdentity:
    raise NotImplementedError


def presence_timeline(
    conn: sqlite3.Connection,
    mac_or_hash: str,
    hours: int = 24,
    bucket_minutes: int = 15,
) -> Timeline:
    raise NotImplementedError


def find_regulars(
    conn: sqlite3.Connection,
    hours_back: int = 168,
    min_days_seen: int = 3,
) -> list[RegularDevice]:
    raise NotImplementedError


def diff_presence(conn: sqlite3.Connection, since: str) -> PresenceDiff:
    raise NotImplementedError


def label(conn: sqlite3.Connection, mac_or_hash: str, name: str) -> None:
    raise NotImplementedError


def stats(conn: sqlite3.Connection) -> CollectorStats:
    raise NotImplementedError
