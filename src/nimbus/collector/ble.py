"""BLE advertisement scanner using bleak.

Runs in passive scan mode — never attempts to connect or pair with any device.
"""

import asyncio
import json
import sqlite3
import time

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ._vendor import infer_class, lookup_vendor
from ..privacy.hashing import hash_mac, load_or_create_salt
from ..privacy.optout import is_opted_out
from ..store.queries import insert_observation, upsert_device
from ..store.schema import Observation

_NAME_MAX_LEN = 32


def _manufacturer_fingerprint(manufacturer_data: dict[int, bytes]) -> str | None:
    """Return a short fingerprint of manufacturer data without exposing raw bytes."""
    if not manufacturer_data:
        return None
    company_id, data = next(iter(manufacturer_data.items()))
    return f"{company_id:04x}:{data[:4].hex()}"


async def run_ble_loop(
    conn: sqlite3.Connection,
    opt_out_prefixes: list[str] | None = None,
) -> None:
    """Passively scan BLE advertisements and write observations to the store.

    Falls back to active scanning if the adapter does not support passive mode.
    """
    salt = load_or_create_salt()
    prefixes = opt_out_prefixes or []
    queue: asyncio.Queue[tuple[Observation, str | None, str]] = asyncio.Queue()

    def _callback(device: BLEDevice, adv: AdvertisementData) -> None:
        raw_mac = device.address
        if is_opted_out(raw_mac, prefixes):
            return

        vendor = lookup_vendor(raw_mac)
        service_uuids = list(adv.service_uuids)
        device_class = infer_class(vendor, service_uuids)
        mac_hash = hash_mac(raw_mac, salt)

        name = ((adv.local_name or device.name or "")[:_NAME_MAX_LEN]) or None
        extra = {
            "name": name,
            "service_uuids": service_uuids,
            "manufacturer_fingerprint": _manufacturer_fingerprint(adv.manufacturer_data),
        }

        obs = Observation(
            ts=int(time.time()),
            radio="ble",
            mac_hash=mac_hash,
            rssi=adv.rssi,
            channel=None,
            frame_type="adv",
            extra_json=json.dumps(extra),
        )
        # Called from within the event loop — put_nowait is safe here.
        queue.put_nowait((obs, vendor, device_class))

    try:
        scanner = BleakScanner(detection_callback=_callback, scanning_mode="passive")
    except (AttributeError, ValueError):
        # Adapter or BlueZ version does not support passive scanning.
        scanner = BleakScanner(detection_callback=_callback)

    async with scanner:
        while True:
            obs, vendor, device_class = await queue.get()
            insert_observation(conn, obs)
            upsert_device(conn, obs, vendor, device_class)