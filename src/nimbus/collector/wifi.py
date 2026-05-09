"""Wi-Fi 802.11 management frame collector using scapy.

The interface must already be in monitor mode before this loop starts:
    iw dev wlan0 interface add wlan0mon type monitor
    ip link set wlan0mon up
"""

import asyncio
import json
import sqlite3
import time

from scapy.layers.dot11 import Dot11, Dot11Beacon, Dot11Elt, Dot11ProbeReq, RadioTap  # type: ignore[import-untyped]
from scapy.sendrecv import AsyncSniffer  # type: ignore[import-untyped]

from ._vendor import infer_class, lookup_vendor
from ..privacy.hashing import hash_mac, load_or_create_salt
from ..privacy.optout import is_opted_out
from ..store.queries import insert_observation, upsert_device
from ..store.schema import Observation

_BROADCAST_MACS = {"ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"}


def _freq_to_channel(freq: int) -> int | None:
    if 2412 <= freq <= 2472:
        return (freq - 2407) // 5
    if freq == 2484:
        return 14
    if 5180 <= freq <= 5825:
        return 36 + (freq - 5180) // 5
    return None


def _extract_ssids(pkt: object) -> list[str]:
    """Walk the Dot11Elt chain and collect SSID elements (ID=0)."""
    ssids: list[str] = []
    elt = pkt.getlayer(Dot11Elt)  # type: ignore[union-attr]
    while elt is not None:
        if elt.ID == 0 and elt.info:
            try:
                ssid = elt.info.decode("utf-8", errors="replace").strip("\x00")
                if ssid:
                    ssids.append(ssid)
            except Exception:
                pass
        elt = elt.payload.getlayer(Dot11Elt) if elt.payload else None  # type: ignore[union-attr]
    return ssids


def _parse_packet(
    pkt: object,
    salt: bytes,
    opt_out_prefixes: list[str],
) -> tuple[Observation, str | None, str] | None:
    """Convert a scapy packet into an (Observation, vendor, device_class) triple.

    Returns None if the packet should be skipped.
    """
    if not pkt.haslayer(Dot11):  # type: ignore[union-attr]
        return None

    dot11 = pkt[Dot11]  # type: ignore[index]

    if pkt.haslayer(Dot11ProbeReq):  # type: ignore[union-attr]
        raw_mac = dot11.addr2
        frame_type = "probe_req"
        extra: dict[str, object] = {"ssids": _extract_ssids(pkt)}
    elif pkt.haslayer(Dot11Beacon):  # type: ignore[union-attr]
        raw_mac = dot11.addr2
        frame_type = "beacon"
        ssids = _extract_ssids(pkt)
        extra = {"ssid": ssids[0] if ssids else None}
    else:
        return None

    if not raw_mac or raw_mac in _BROADCAST_MACS:
        return None

    if is_opted_out(raw_mac, opt_out_prefixes):
        return None

    # Resolve vendor and class from raw MAC before it's hashed
    vendor = lookup_vendor(raw_mac)
    device_class = infer_class(vendor)
    mac_hash = hash_mac(raw_mac, salt)

    rssi: int | None = None
    channel: int | None = None
    if pkt.haslayer(RadioTap):  # type: ignore[union-attr]
        rt = pkt[RadioTap]  # type: ignore[index]
        rssi = getattr(rt, "dBm_AntSignal", None)
        freq = getattr(rt, "ChannelFrequency", None)
        if freq:
            channel = _freq_to_channel(int(freq))

    obs = Observation(
        ts=int(time.time()),
        radio="wifi",
        mac_hash=mac_hash,
        rssi=rssi,
        channel=channel,
        frame_type=frame_type,
        extra_json=json.dumps(extra),
    )
    return obs, vendor, device_class


async def run_wifi_loop(
    conn: sqlite3.Connection,
    interface: str = "wlan0mon",
    opt_out_prefixes: list[str] | None = None,
) -> None:
    """Sniff 802.11 management frames and write observations to the store.

    Requires CAP_NET_RAW + CAP_NET_ADMIN or root. The interface must already
    be in monitor mode (e.g. via `iw dev wlan0 set monitor control`).
    """
    salt = load_or_create_salt()
    prefixes = opt_out_prefixes or []
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[Observation, str | None, str]] = asyncio.Queue()

    def _callback(pkt: object) -> None:
        result = _parse_packet(pkt, salt, prefixes)
        if result is not None:
            # Called from scapy's sniffer thread — hand off to the event loop.
            loop.call_soon_threadsafe(queue.put_nowait, result)

    sniffer = AsyncSniffer(iface=interface, prn=_callback, filter="type mgt", store=False)
    sniffer.start()

    try:
        while True:
            obs, vendor, device_class = await queue.get()
            insert_observation(conn, obs)
            upsert_device(conn, obs, vendor, device_class)
    finally:
        sniffer.stop()