import sqlite3
from .schema import Observation


def insert_observation(conn: sqlite3.Connection, obs: Observation) -> None:
    raise NotImplementedError


def upsert_device(conn: sqlite3.Connection, obs: Observation, vendor_oui: str | None, inferred_class: str) -> None:
    raise NotImplementedError


def get_present_devices(conn: sqlite3.Connection, since_ts: int, min_observations: int) -> list[dict]:  # type: ignore[type-arg]
    raise NotImplementedError


def get_device(conn: sqlite3.Connection, mac_hash: str) -> dict | None:  # type: ignore[type-arg]
    raise NotImplementedError


def get_presence_timeline(conn: sqlite3.Connection, mac_hash: str, since_ts: int, bucket_seconds: int) -> list[dict]:  # type: ignore[type-arg]
    raise NotImplementedError


def get_regulars(conn: sqlite3.Connection, since_ts: int, min_days_seen: int) -> list[dict]:  # type: ignore[type-arg]
    raise NotImplementedError


def get_label(conn: sqlite3.Connection, mac_hash: str) -> str | None:
    raise NotImplementedError


def set_label(conn: sqlite3.Connection, mac_hash: str, name: str) -> None:
    raise NotImplementedError


def get_stats(conn: sqlite3.Connection) -> dict:  # type: ignore[type-arg]
    raise NotImplementedError
