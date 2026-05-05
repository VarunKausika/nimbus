import asyncio
import sqlite3


async def run_ble_loop(
    conn: sqlite3.Connection,
    opt_out_prefixes: list[str] | None = None,
) -> None:
    """Passively scan BLE advertisements and write observations to the store.

    Uses bleak in passive scan mode — never attempts to connect or pair.
    """
    raise NotImplementedError
