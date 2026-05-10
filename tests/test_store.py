import sqlite3
import time

import pytest

from nimbus.store.queries import (
    get_device,
    get_label,
    get_present_devices,
    insert_observation,
    set_label,
    upsert_device,
)
from nimbus.store.retention import _purge_devices, _purge_observations
from nimbus.store.schema import Observation


def make_obs(
    ts: int | None = None,
    radio: str = "wifi",
    mac_hash: str = "aabbccdd11223344",
    rssi: int = -60,
    channel: int = 6,
) -> Observation:
    return Observation(
        ts=ts or int(time.time()),
        radio=radio,
        mac_hash=mac_hash,
        rssi=rssi,
        channel=channel,
        frame_type="probe_req",
        extra_json=None,
    )


class TestInsertObservation:
    def test_insert_appears_in_db(self, db: sqlite3.Connection) -> None:
        obs = make_obs()
        insert_observation(db, obs)

        row = db.execute("SELECT mac_hash, radio FROM observations").fetchone()
        assert row is not None
        assert row[0] == obs.mac_hash
        assert row[1] == "wifi"

    def test_upserts_device_row(self, db: sqlite3.Connection) -> None:
        obs = make_obs()
        insert_observation(db, obs)
        upsert_device(db, obs, "Apple, Inc.", "phone")

        device = get_device(db, obs.mac_hash)
        assert device is not None
        assert device["vendor_oui"] == "Apple, Inc."
        assert device["inferred_class"] == "phone"
        assert device["observation_n"] == 1

    def test_upsert_increments_observation_count(self, db: sqlite3.Connection) -> None:
        obs = make_obs()
        for _ in range(3):
            insert_observation(db, obs)
            upsert_device(db, obs, "Apple, Inc.", "phone")

        device = get_device(db, obs.mac_hash)
        assert device is not None
        assert device["observation_n"] == 3

    def test_upsert_keeps_better_inferred_class(self, db: sqlite3.Connection) -> None:
        obs = make_obs()
        insert_observation(db, obs)
        upsert_device(db, obs, "Apple, Inc.", "phone")

        # A subsequent insert with "unknown" should not overwrite "phone"
        insert_observation(db, obs)
        upsert_device(db, obs, "Apple, Inc.", "unknown")

        device = get_device(db, obs.mac_hash)
        assert device is not None
        assert device["inferred_class"] == "phone"


class TestGetPresentDevices:
    def test_returns_devices_within_window(self, db: sqlite3.Connection) -> None:
        now = int(time.time())
        obs = make_obs(ts=now - 60)
        insert_observation(db, obs)
        upsert_device(db, obs, "Apple, Inc.", "phone")

        rows = get_present_devices(db, since_ts=now - 300, min_observations=1)

        assert len(rows) == 1
        assert rows[0]["mac_hash"] == obs.mac_hash

    def test_filters_below_min_observations(self, db: sqlite3.Connection) -> None:
        now = int(time.time())
        obs = make_obs(ts=now - 60)
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        rows = get_present_devices(db, since_ts=now - 300, min_observations=3)

        assert rows == []

    def test_excludes_devices_outside_window(self, db: sqlite3.Connection) -> None:
        now = int(time.time())
        obs = make_obs(ts=now - 3600)  # 1 hour ago
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        rows = get_present_devices(db, since_ts=now - 300, min_observations=1)

        assert rows == []

    def test_returns_multiple_devices(self, db: sqlite3.Connection) -> None:
        now = int(time.time())
        for mac in ["aaaa000000000001", "aaaa000000000002"]:
            obs = make_obs(ts=now - 30, mac_hash=mac)
            for _ in range(3):
                insert_observation(db, obs)
            upsert_device(db, obs, None, "unknown")

        rows = get_present_devices(db, since_ts=now - 300, min_observations=3)
        assert len(rows) == 2


class TestLabels:
    def test_set_and_get_label(self, db: sqlite3.Connection) -> None:
        obs = make_obs()
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        set_label(db, obs.mac_hash, "roommate's phone")
        assert get_label(db, obs.mac_hash) == "roommate's phone"

    def test_label_overwrite(self, db: sqlite3.Connection) -> None:
        obs = make_obs()
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        set_label(db, obs.mac_hash, "old name")
        set_label(db, obs.mac_hash, "new name")
        assert get_label(db, obs.mac_hash) == "new name"

    def test_missing_label_returns_none(self, db: sqlite3.Connection) -> None:
        assert get_label(db, "nonexistent") is None


class TestRetention:
    def test_purge_removes_old_observations(self, db: sqlite3.Connection) -> None:
        obs = make_obs(ts=int(time.time()) - 49 * 3600)  # 49 hours ago
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        _purge_observations(db, ttl_hours=48)

        count = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assert count == 0

    def test_purge_keeps_recent_observations(self, db: sqlite3.Connection) -> None:
        obs = make_obs(ts=int(time.time()) - 10)  # 10 seconds ago
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        _purge_observations(db, ttl_hours=48)

        count = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assert count == 1

    def test_purge_removes_stale_devices(self, db: sqlite3.Connection) -> None:
        obs = make_obs(ts=int(time.time()) - 31 * 86400)  # 31 days ago
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        _purge_devices(db, ttl_days=30)

        count = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        assert count == 0

    def test_purge_keeps_active_devices(self, db: sqlite3.Connection) -> None:
        obs = make_obs(ts=int(time.time()) - 60)  # 1 minute ago
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        _purge_devices(db, ttl_days=30)

        count = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        assert count == 1
