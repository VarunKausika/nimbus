import sqlite3
import pytest

from nimbus.store.schema import DDL


@pytest.fixture
def db() -> sqlite3.Connection:
    """In-memory SQLite database pre-populated with the nimbus schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(DDL)
    conn.commit()
    return conn


@pytest.fixture
def salt() -> bytes:
    return b"test-salt-fixed-32-bytes-padding!"
