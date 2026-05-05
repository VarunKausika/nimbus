import sqlite3
import time

import pytest

from nimbus.store.schema import Observation
from nimbus.store import queries, retention


def make_obs(ts: int | None = None, radio: str = "wifi", mac_hash: str = "aabbccdd11223344") -> Observation:
    return Observation(
        ts=ts or int(time.time()),
        radio=radio,
        mac_hash=mac_hash,
        rssi=-60,
        channel=6,
        frame_type="probe_req",
        extra_json=None,
    )


class TestInsertObservation:
    def test_insert_appears_in_db(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_upserts_device_row(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestGetPresentDevices:
    def test_returns_devices_within_window(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_filters_below_min_observations(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_excludes_devices_outside_window(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestRetention:
    def test_purge_removes_old_observations(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_purge_keeps_recent_observations(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_purge_removes_stale_devices(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")
