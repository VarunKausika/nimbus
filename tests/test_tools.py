import sqlite3
import time

import pytest

from nimbus.server import tools
from nimbus.server.schemas import (
    CollectorStats,
    DeviceIdentity,
    PresenceDiff,
    PresenceReport,
    Timeline,
)
from nimbus.store.queries import insert_observation, upsert_device
from nimbus.store.schema import Observation


def _obs(
    ts: int,
    mac_hash: str,
    radio: str = "wifi",
    frame_type: str = "probe_req",
    extra_json: str = '{"ssids": []}',
) -> Observation:
    return Observation(
        ts=ts,
        radio=radio,
        mac_hash=mac_hash,
        rssi=-60,
        channel=6,
        frame_type=frame_type,
        extra_json=extra_json,
    )


class TestWhoIsHere:
    def test_returns_presence_report(self, seeded_db: sqlite3.Connection) -> None:
        result = tools.who_is_here(seeded_db, since="5m", min_observations=3)

        assert isinstance(result, PresenceReport)
        hashes = {d.mac_hash for d in result.devices}
        # device_a: 5 obs, 1 min ago → included
        assert "device_a_hash_0001" in hashes
        # device_b: 1 obs → excluded (below min_observations=3)
        assert "device_b_hash_0002" not in hashes
        # device_c: 6h ago → excluded (outside window)
        assert "device_c_hash_0003" not in hashes

    def test_respects_min_observations_filter(self, seeded_db: sqlite3.Connection) -> None:
        # With min_observations=1, device_b should appear
        result = tools.who_is_here(seeded_db, since="5m", min_observations=1)
        hashes = {d.mac_hash for d in result.devices}
        assert "device_b_hash_0002" in hashes

    def test_wider_window_includes_older_device(self, seeded_db: sqlite3.Connection) -> None:
        result = tools.who_is_here(seeded_db, since="12h", min_observations=3)
        hashes = {d.mac_hash for d in result.devices}
        assert "device_c_hash_0003" in hashes

    def test_empty_db_returns_empty_report(self, db: sqlite3.Connection) -> None:
        result = tools.who_is_here(db)
        assert isinstance(result, PresenceReport)
        assert result.devices == []


class TestIdentify:
    def test_returns_device_identity(self, seeded_db: sqlite3.Connection) -> None:
        result = tools.identify(seeded_db, "device_a_hash_0001")

        assert isinstance(result, DeviceIdentity)
        assert result.mac_hash == "device_a_hash_0001"
        assert result.vendor == "Apple, Inc."
        assert result.device_class == "phone"
        assert result.observation_count == 5
        assert "HomeNetwork" in result.probed_ssids

    def test_unknown_hash_raises(self, db: sqlite3.Connection) -> None:
        with pytest.raises(ValueError, match="Unknown device"):
            tools.identify(db, "nonexistent0000000")

    def test_ble_device_has_service_uuids(self, seeded_db: sqlite3.Connection) -> None:
        # Insert a BLE device with service UUIDs
        now = int(time.time())
        obs = Observation(
            ts=now - 30,
            radio="ble",
            mac_hash="ble_device_hash_0004",
            rssi=-65,
            channel=None,
            frame_type="adv",
            extra_json='{"name": "HR Monitor", "service_uuids": ["0000180d-0000-1000-8000-00805f9b34fb"], "manufacturer_fingerprint": null}',
        )
        insert_observation(seeded_db, obs)
        upsert_device(seeded_db, obs, "Fitbit, Inc.", "wearable")

        result = tools.identify(seeded_db, "ble_device_hash_0004")
        assert "0000180d-0000-1000-8000-00805f9b34fb" in result.advertised_services


class TestPresenceTimeline:
    def test_returns_bucketed_results(self, db: sqlite3.Connection) -> None:
        now = int(time.time())
        mac = "timeline_device_0001"
        # Insert 3 observations spread over the past hour
        for offset in [300, 1800, 3300]:
            obs = _obs(ts=now - offset, mac_hash=mac)
            insert_observation(db, obs)
            upsert_device(db, obs, None, "unknown")

        result = tools.presence_timeline(db, mac, hours=2, bucket_minutes=15)

        assert isinstance(result, Timeline)
        assert result.mac_hash == mac
        assert result.bucket_minutes == 15
        assert len(result.buckets) > 0
        assert all(b.observation_count > 0 for b in result.buckets)

    def test_empty_timeline_for_unknown_device(self, db: sqlite3.Connection) -> None:
        result = tools.presence_timeline(db, "unknown_hash_0000", hours=1, bucket_minutes=15)
        assert result.buckets == []


class TestFindRegulars:
    def test_returns_only_multi_day_devices(self, db: sqlite3.Connection) -> None:
        now = int(time.time())
        regular = "regular_device_00001"
        occasional = "occasional_device_01"

        # regular: observed on 4 distinct days
        for day in [1, 2, 3, 4]:
            obs = _obs(ts=now - day * 86400 - 3600, mac_hash=regular)
            insert_observation(db, obs)
            upsert_device(db, obs, "Apple, Inc.", "phone")

        # occasional: observed on only 1 day
        obs = _obs(ts=now - 86400, mac_hash=occasional)
        insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        results = tools.find_regulars(db, hours_back=168, min_days_seen=3)
        hashes = {r.mac_hash for r in results}

        assert regular in hashes
        assert occasional not in hashes

    def test_empty_when_no_regulars(self, db: sqlite3.Connection) -> None:
        results = tools.find_regulars(db)
        assert results == []


class TestDiffPresence:
    def test_correctly_classifies_new_departed_lingering(
        self, db: sqlite3.Connection
    ) -> None:
        now = int(time.time())
        checkpoint = now - 200  # 200 seconds ago

        # device_new: only seen after the checkpoint
        obs = _obs(ts=now - 60, mac_hash="new_device_hash_0001")
        for _ in range(3):
            insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        # device_departed: only seen before the checkpoint
        obs = _obs(ts=checkpoint - 60, mac_hash="departed_device_0002")
        for _ in range(3):
            insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        # device_lingering: seen both before and after the checkpoint
        for ts in [checkpoint - 60, now - 60]:
            obs = _obs(ts=ts, mac_hash="lingering_device_0003")
            for _ in range(3):
                insert_observation(db, obs)
        upsert_device(db, obs, None, "unknown")

        result = tools.diff_presence(db, since=f"{now - checkpoint}s")

        assert isinstance(result, PresenceDiff)
        new_hashes = {d.mac_hash for d in result.new}
        departed_hashes = {d.mac_hash for d in result.departed}
        lingering_hashes = {d.mac_hash for d in result.lingering}

        assert "new_device_hash_0001" in new_hashes
        assert "departed_device_0002" in departed_hashes
        assert "lingering_device_0003" in lingering_hashes


class TestLabel:
    def test_label_persists_in_identify(self, seeded_db: sqlite3.Connection) -> None:
        tools.label(seeded_db, "device_a_hash_0001", "my laptop")
        result = tools.identify(seeded_db, "device_a_hash_0001")
        assert result.label == "my laptop"

    def test_label_appears_in_who_is_here(self, seeded_db: sqlite3.Connection) -> None:
        tools.label(seeded_db, "device_a_hash_0001", "roommate")
        report = tools.who_is_here(seeded_db, since="5m", min_observations=1)
        device_a = next(d for d in report.devices if d.mac_hash == "device_a_hash_0001")
        assert device_a.label == "roommate"


class TestStats:
    def test_returns_collector_stats(self, seeded_db: sqlite3.Connection) -> None:
        result = tools.stats(seeded_db)

        assert isinstance(result, CollectorStats)
        assert result.database_size_bytes > 0
        assert result.unique_devices_last_hour >= 0
        assert result.frames_per_second >= 0.0
        assert result.oldest_observation is not None

    def test_empty_db_returns_zero_stats(self, db: sqlite3.Connection) -> None:
        result = tools.stats(db)

        assert isinstance(result, CollectorStats)
        assert result.oldest_observation is None
        assert result.uptime_seconds == 0.0
        assert result.unique_devices_last_hour == 0