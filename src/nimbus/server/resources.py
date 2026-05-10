"""MCP resource implementations.

Resources are read-only, low-query-cost data exposed at stable URIs.
presence://current is cached for 30 seconds to avoid hammering the DB
on every client poll.
"""

import json
import sqlite3
import time
import tomllib
from pathlib import Path

_CONFIG_PATH = Path.home() / ".nimbus" / "config.toml"
_CACHE_TTL_S = 30.0

_presence_cache: str | None = None
_presence_cache_ts: float = 0.0


def presence_current(conn: sqlite3.Connection) -> str:
    """Point-in-time JSON snapshot of who_is_here(), cached for 30 seconds."""
    global _presence_cache, _presence_cache_ts

    now = time.monotonic()
    if _presence_cache is None or now - _presence_cache_ts >= _CACHE_TTL_S:
        from .tools import who_is_here
        _presence_cache = who_is_here(conn).model_dump_json()
        _presence_cache_ts = now

    return _presence_cache


def presence_config() -> str:
    """Active configuration as JSON. Never exposes the salt or full opt-out list."""
    raw: dict = {}  # type: ignore[type-arg]
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open("rb") as f:
            raw = tomllib.load(f)

    privacy = raw.get("privacy", {})
    retention = raw.get("retention", {})

    safe = {
        "wifi_interface": raw.get("wifi", {}).get("interface", "wlan0mon"),
        "retention_hours": retention.get("hours", 48),
        "device_ttl_days": retention.get("device_days", 30),
        "opt_out_count": len(privacy.get("opt_out", [])),
    }
    return json.dumps(safe)


def presence_schema() -> str:
    """Full JSON Schema for every tool result type."""
    from .schemas import (
        BLEScanResult,
        CollectorStats,
        DeviceIdentity,
        PresenceDiff,
        PresenceReport,
        RegularDevice,
        Timeline,
        WiFiScanResult,
    )

    schema = {
        "PresenceReport": PresenceReport.model_json_schema(),
        "WiFiScanResult": WiFiScanResult.model_json_schema(),
        "BLEScanResult": BLEScanResult.model_json_schema(),
        "DeviceIdentity": DeviceIdentity.model_json_schema(),
        "Timeline": Timeline.model_json_schema(),
        "RegularDevice": RegularDevice.model_json_schema(),
        "PresenceDiff": PresenceDiff.model_json_schema(),
        "CollectorStats": CollectorStats.model_json_schema(),
    }
    return json.dumps(schema)