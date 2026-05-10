"""Implementations of all 9 MCP tools.

scan_wifi and scan_ble are async because they block for the scan duration.
All other tools are synchronous DB reads and return in well under 500 ms.
"""

import asyncio
import json
import re
import sqlite3
import time
from datetime import datetime, timezone

from bleak import BleakScanner
from bleak.backends.device import BLEDevice as BleakDevice
from bleak.backends.scanner import AdvertisementData
from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11Elt, Dot11ProbeReq, RadioTap  # type: ignore[import-untyped]
from scapy.sendrecv import sniff  # type: ignore[import-untyped]

from ..privacy.hashing import hash_mac, load_or_create_salt
from ..store import queries
from .schemas import (
    AccessPoint,
    BLEDevice,
    BLEScanResult,
    CollectorStats,
    DeviceEntry,
    DeviceIdentity,
    PresenceDiff,
    PresenceReport,
    ProbeRequest,
    RegularDevice,
    Timeline,
    TimelineBucket,
    WiFiScanResult,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SINCE_RE = re.compile(r"^(\d+)(s|m|h|d)$")
_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_PRESENCE_WINDOW_S = 300  # "currently present" means seen in the last 5 minutes


def _parse_since(since: str) -> int:
    """Parse '5m', '1h', '30s', '2d', or an ISO 8601 string into a Unix timestamp."""
    now = int(time.time())
    m = _SINCE_RE.match(since.strip())
    if m:
        return now - int(m.group(1)) * _MULTIPLIERS[m.group(2)]
    try:
        return int(datetime.fromisoformat(since).timestamp())
    except ValueError:
        raise ValueError(f"Cannot parse time {since!r}. Use '5m', '1h', or ISO 8601.")


def _ts_to_iso(ts: int | None) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _rssi_band(rssi: int | None) -> str:
    if rssi is None:
        return "unknown"
    if rssi >= -60:
        return "strong"
    if rssi >= -75:
        return "medium"
    return "weak"


def _resolve_hash(mac_or_hash: str) -> str:
    """Hash the input if it looks like a raw MAC; otherwise pass it through."""
    if ":" in mac_or_hash or "-" in mac_or_hash:
        return hash_mac(mac_or_hash, load_or_create_salt())
    return mac_or_hash


def _row_to_device_entry(row: dict) -> DeviceEntry:  # type: ignore[type-arg]
    return DeviceEntry(
        mac_hash=row["mac_hash"],
        vendor=row.get("vendor_oui"),
        device_class=row.get("inferred_class") or "unknown",
        rssi_min=row.get("rssi_min"),
        rssi_max=row.get("rssi_max"),
        rssi_avg=row.get("rssi_avg"),
        first_seen=_ts_to_iso(row.get("first_seen")),
        last_seen=_ts_to_iso(row.get("last_seen")),
        label=row.get("label"),
    )


def _freq_to_channel(freq: int) -> int | None:
    if 2412 <= freq <= 2472:
        return (freq - 2407) // 5
    if freq == 2484:
        return 14
    if 5180 <= freq <= 5825:
        return 36 + (freq - 5180) // 5
    return None


def _extract_ssids_from_pkt(pkt: object) -> list[str]:
    ssids: list[str] = []
    elt = pkt.getlayer(Dot11Elt)  # type: ignore[union-attr]
    while elt is not None:
        if elt.ID == 0 and elt.info:
            try:
                s = elt.info.decode("utf-8", errors="replace").strip("\x00")
                if s:
                    ssids.append(s)
            except Exception:
                pass
        elt = elt.payload.getlayer(Dot11Elt) if elt.payload else None  # type: ignore[union-attr]
    return ssids


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def who_is_here(
    conn: sqlite3.Connection,
    since: str = "5m",
    min_observations: int = 3,
) -> PresenceReport:
    since_ts = _parse_since(since)
    rows = queries.get_present_devices(conn, since_ts, min_observations)
    return PresenceReport(
        devices=[_row_to_device_entry(r) for r in rows],
        window=since,
        generated_at=_ts_to_iso(int(time.time())),
    )


async def scan_wifi(
    conn: sqlite3.Connection,
    duration_s: int = 10,
    interface: str = "wlan0mon",
) -> WiFiScanResult:
    salt = load_or_create_salt()
    scanned_at = _ts_to_iso(int(time.time()))

    loop = asyncio.get_running_loop()
    packets = await loop.run_in_executor(
        None,
        lambda: sniff(iface=interface, filter="type mgt", timeout=duration_s, store=True),
    )

    aps: dict[str, AccessPoint] = {}
    probes: dict[str, set[str]] = {}

    for pkt in packets:
        rt = pkt[RadioTap] if pkt.haslayer(RadioTap) else None  # type: ignore[index]
        rssi: int | None = getattr(rt, "dBm_AntSignal", None) if rt else None
        freq = getattr(rt, "ChannelFrequency", None) if rt else None
        channel = _freq_to_channel(int(freq)) if freq else None

        if pkt.haslayer(Dot11Beacon):  # type: ignore[union-attr]
            raw_bssid = pkt[Dot11].addr2  # type: ignore[index]
            if not raw_bssid:
                continue
            bssid_hash = hash_mac(raw_bssid, salt)
            if bssid_hash in aps:
                continue

            ssids = _extract_ssids_from_pkt(pkt)
            beacon_interval: int | None = getattr(pkt[Dot11Beacon], "beacon_interval", None)  # type: ignore[index]

            aps[bssid_hash] = AccessPoint(
                ssid=ssids[0] if ssids else None,
                bssid_hash=bssid_hash,
                channel=channel,
                rssi_band=_rssi_band(rssi),
                beacon_interval_ms=int(beacon_interval) if beacon_interval else None,
            )

        elif pkt.haslayer(Dot11ProbeReq):  # type: ignore[union-attr]
            raw_mac = pkt[Dot11].addr2  # type: ignore[index]
            if not raw_mac or raw_mac == "ff:ff:ff:ff:ff:ff":
                continue
            mac_hash = hash_mac(raw_mac, salt)
            ssid_set = probes.setdefault(mac_hash, set())
            ssid_set.update(_extract_ssids_from_pkt(pkt))

    return WiFiScanResult(
        access_points=list(aps.values()),
        probe_requests=[
            ProbeRequest(mac_hash=mh, probed_ssids=sorted(s)) for mh, s in probes.items()
        ],
        duration_s=duration_s,
        scanned_at=scanned_at,
    )


async def scan_ble(
    conn: sqlite3.Connection,
    duration_s: int = 10,
) -> BLEScanResult:
    salt = load_or_create_salt()
    scanned_at = _ts_to_iso(int(time.time()))
    results: dict[str, tuple[BleakDevice, AdvertisementData]] = {}

    def _callback(device: BleakDevice, adv: AdvertisementData) -> None:
        results[device.address] = (device, adv)

    try:
        scanner = BleakScanner(detection_callback=_callback, scanning_mode="passive")
    except (AttributeError, ValueError):
        scanner = BleakScanner(detection_callback=_callback)

    async with scanner:
        await asyncio.sleep(duration_s)

    devices: list[BLEDevice] = []
    for raw_mac, (device, adv) in results.items():
        mac_hash = hash_mac(raw_mac, salt)
        name = ((adv.local_name or device.name or "")[:32]) or None

        manuf_fp: str | None = None
        if adv.manufacturer_data:
            company_id, data = next(iter(adv.manufacturer_data.items()))
            manuf_fp = f"{company_id:04x}:{data[:4].hex()}"

        devices.append(
            BLEDevice(
                mac_hash=mac_hash,
                name=name,
                service_uuids=list(adv.service_uuids),
                manufacturer_fingerprint=manuf_fp,
                rssi=adv.rssi,
            )
        )

    return BLEScanResult(devices=devices, duration_s=duration_s, scanned_at=scanned_at)


def identify(conn: sqlite3.Connection, mac_or_hash: str) -> DeviceIdentity:
    mac_hash = _resolve_hash(mac_or_hash)
    device = queries.get_device(conn, mac_hash)
    if device is None:
        raise ValueError(f"Unknown device: {mac_or_hash!r}")

    obs_list = queries.get_observations_for_device(conn, mac_hash, since_ts=0)

    probed_ssids: set[str] = set()
    advertised_services: set[str] = set()
    observed_channels: set[int] = set()

    for obs in obs_list:
        if obs["channel"]:
            observed_channels.add(int(obs["channel"]))
        if obs["extra_json"]:
            extra = json.loads(obs["extra_json"])
            if obs["frame_type"] == "probe_req":
                probed_ssids.update(extra.get("ssids", []))
            elif obs["frame_type"] == "adv":
                advertised_services.update(extra.get("service_uuids", []))

    return DeviceIdentity(
        mac_hash=mac_hash,
        vendor=device["vendor_oui"],
        device_class=device["inferred_class"] or "unknown",
        probed_ssids=sorted(probed_ssids),
        advertised_services=sorted(advertised_services),
        observed_channels=sorted(observed_channels),
        observation_count=int(device["observation_n"]),
        first_seen=_ts_to_iso(device["first_seen"]),
        last_seen=_ts_to_iso(device["last_seen"]),
        label=queries.get_label(conn, mac_hash),
    )


def presence_timeline(
    conn: sqlite3.Connection,
    mac_or_hash: str,
    hours: int = 24,
    bucket_minutes: int = 15,
) -> Timeline:
    mac_hash = _resolve_hash(mac_or_hash)
    since_ts = int(time.time()) - hours * 3600
    bucket_seconds = bucket_minutes * 60

    rows = queries.get_presence_timeline(conn, mac_hash, since_ts, bucket_seconds)
    buckets = [
        TimelineBucket(
            start=_ts_to_iso(row["bucket_start"]),
            observation_count=row["observation_count"],
        )
        for row in rows
    ]
    return Timeline(
        mac_hash=mac_hash,
        bucket_minutes=bucket_minutes,
        hours=hours,
        buckets=buckets,
    )


def find_regulars(
    conn: sqlite3.Connection,
    hours_back: int = 168,
    min_days_seen: int = 3,
) -> list[RegularDevice]:
    since_ts = int(time.time()) - hours_back * 3600
    rows = queries.get_regulars(conn, since_ts, min_days_seen)
    return [
        RegularDevice(
            mac_hash=row["mac_hash"],
            vendor=row.get("vendor_oui"),
            device_class=row.get("inferred_class") or "unknown",
            days_seen=int(row["days_seen"]),
            label=row.get("label"),
        )
        for row in rows
    ]


def diff_presence(conn: sqlite3.Connection, since: str) -> PresenceDiff:
    since_ts = _parse_since(since)
    now = int(time.time())

    def _hashes_in_range(from_ts: int, to_ts: int) -> set[str]:
        cur = conn.execute(
            "SELECT DISTINCT mac_hash FROM observations WHERE ts >= ? AND ts <= ?",
            (from_ts, to_ts),
        )
        return {row[0] for row in cur.fetchall()}

    def _entries_for_hashes(hashes: set[str]) -> list[DeviceEntry]:
        if not hashes:
            return []
        placeholders = ",".join("?" * len(hashes))
        cur = conn.execute(
            f"""
            SELECT d.mac_hash, d.vendor_oui, d.inferred_class,
                   d.first_seen, d.last_seen, l.name AS label
            FROM devices d
            LEFT JOIN labels l ON l.mac_hash = d.mac_hash
            WHERE d.mac_hash IN ({placeholders})
            """,
            list(hashes),
        )
        cols = [c[0] for c in cur.description]
        return [
            DeviceEntry(
                mac_hash=r["mac_hash"],
                vendor=r.get("vendor_oui"),
                device_class=r.get("inferred_class") or "unknown",
                rssi_min=None,
                rssi_max=None,
                rssi_avg=None,
                first_seen=_ts_to_iso(r.get("first_seen")),
                last_seen=_ts_to_iso(r.get("last_seen")),
                label=r.get("label"),
            )
            for r in [dict(zip(cols, row)) for row in cur.fetchall()]
        ]

    # Use closed time ranges so a device seen in both windows is correctly
    # classified as lingering rather than excluded by a last_seen filter.
    before_hashes = _hashes_in_range(since_ts - _PRESENCE_WINDOW_S, since_ts)
    after_hashes = _hashes_in_range(since_ts, now)

    return PresenceDiff(
        new=_entries_for_hashes(after_hashes - before_hashes),
        departed=_entries_for_hashes(before_hashes - after_hashes),
        lingering=_entries_for_hashes(before_hashes & after_hashes),
        since=_ts_to_iso(since_ts),
    )


def label(conn: sqlite3.Connection, mac_or_hash: str, name: str) -> None:
    mac_hash = _resolve_hash(mac_or_hash)
    queries.set_label(conn, mac_hash, name)


def stats(conn: sqlite3.Connection) -> CollectorStats:
    raw = queries.get_stats(conn)

    minute_ago = int(time.time()) - 60
    recent_count: int = conn.execute(
        "SELECT COUNT(*) FROM observations WHERE ts >= ?", (minute_ago,)
    ).fetchone()[0]

    oldest_ts: int | None = raw.get("oldest_ts")

    return CollectorStats(
        frames_per_second=round(recent_count / 60.0, 2),
        unique_devices_last_hour=int(raw["unique_devices_last_hour"]),
        database_size_bytes=int(raw["database_size_bytes"]),
        oldest_observation=_ts_to_iso(oldest_ts) if oldest_ts else None,
        uptime_seconds=float(int(time.time()) - oldest_ts) if oldest_ts else 0.0,
    )