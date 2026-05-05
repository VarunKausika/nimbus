import sqlite3


def presence_current(conn: sqlite3.Connection) -> str:
    """Return a JSON snapshot of who_is_here(), refreshed every 30 seconds."""
    raise NotImplementedError


def presence_config() -> str:
    """Return the active configuration as JSON (no secrets)."""
    raise NotImplementedError


def presence_schema() -> str:
    """Return the full JSON Schema for every tool result type."""
    raise NotImplementedError
