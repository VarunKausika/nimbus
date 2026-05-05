import asyncio
import sqlite3


async def run_wifi_loop(
    conn: sqlite3.Connection,
    interface: str = "wlan0mon",
    opt_out_prefixes: list[str] | None = None,
) -> None:
    """Sniff 802.11 management frames and write observations to the store.

    Requires CAP_NET_RAW + CAP_NET_ADMIN or root. The interface must already
    be in monitor mode (e.g. via `iw dev wlan0 set monitor control`).
    """
    raise NotImplementedError
