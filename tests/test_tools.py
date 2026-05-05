import sqlite3

import pytest

from nimbus.server import tools


class TestWhoIsHere:
    def test_returns_presence_report(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_respects_min_observations_filter(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_parses_relative_since(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestIdentify:
    def test_returns_device_identity(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")

    def test_unknown_hash_raises(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestPresenceTimeline:
    def test_returns_bucketed_results(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestFindRegulars:
    def test_returns_only_multi_day_devices(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestDiffPresence:
    def test_correctly_classifies_new_departed_lingering(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestLabel:
    def test_label_persists(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")


class TestStats:
    def test_returns_collector_stats(self, db: sqlite3.Connection) -> None:
        pytest.skip("not implemented")
