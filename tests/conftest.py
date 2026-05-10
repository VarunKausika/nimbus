import sqlite3
import time

import pytest

from nimbus.store.queries import insert_observation, upsert_device
from nimbus.store.schema import DDL, Observation


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


@pytest.fixture
def seeded_db(db: sqlite3.Connection) -> sqlite3.Connection:
    """DB with three devices at distinct recency levels.

    - device_a: 5 Wi-Fi probe_req observations, ~1 minute ago  (recent, above threshold)
    - device_b: 1 BLE adv observation, ~2 minutes ago           (recent, below min_observations=3)
    - device_c: 3 Wi-Fi beacon observations, ~6 hours ago       (outside 5-minute window)
    """
    now = int(time.time())

    for i in range(5):
        obs = Observation(
            ts=now - 60 - i * 10,
            radio="wifi",
            mac_hash="device_a_hash_0001",
            rssi=-55,
            channel=6,
            frame_type="probe_req",
            extra_json='{"ssids": ["HomeNetwork"]}',
        )
        insert_observation(db, obs)
        upsert_device(db, obs, "Apple, Inc.", "phone")

    obs_b = Observation(
        ts=now - 120,
        radio="ble",
        mac_hash="device_b_hash_0002",
        rssi=-70,
        channel=None,
        frame_type="adv",
        extra_json='{"name": "Gadget", "service_uuids": [], "manufacturer_fingerprint": null}',
    )
    insert_observation(db, obs_b)
    upsert_device(db, obs_b, "Samsung Electronics", "phone")

    for i in range(3):
        obs = Observation(
            ts=now - 6 * 3600 - i * 60,
            radio="wifi",
            mac_hash="device_c_hash_0003",
            rssi=-80,
            channel=11,
            frame_type="beacon",
            extra_json='{"ssid": "OfficeNet"}',
        )
        insert_observation(db, obs)
        upsert_device(db, obs, "Espressif Inc.", "iot")

    return db
