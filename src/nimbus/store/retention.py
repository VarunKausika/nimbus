import asyncio
import sqlite3
import time


DEFAULT_OBSERVATION_TTL_HOURS = 48
DEFAULT_DEVICE_TTL_DAYS = 30


async def run_retention_loop(
    conn: sqlite3.Connection,
    observation_ttl_hours: int = DEFAULT_OBSERVATION_TTL_HOURS,
    device_ttl_days: int = DEFAULT_DEVICE_TTL_DAYS,
    interval_seconds: int = 3600,
) -> None:
    """Periodically purge expired rows. Runs forever; cancel the task to stop."""
    while True:
        _purge_observations(conn, observation_ttl_hours)
        _purge_devices(conn, device_ttl_days)
        await asyncio.sleep(interval_seconds)


def _purge_observations(conn: sqlite3.Connection, ttl_hours: int) -> None:
    cutoff = int(time.time()) - ttl_hours * 3600
    conn.execute("DELETE FROM observations WHERE ts < ?", (cutoff,))
    conn.commit()


def _purge_devices(conn: sqlite3.Connection, ttl_days: int) -> None:
    cutoff = int(time.time()) - ttl_days * 86400
    conn.execute("DELETE FROM devices WHERE last_seen < ?", (cutoff,))
    conn.commit()
