"""OUI vendor lookup and device-class inference.

The OUI database is expected at ~/.nimbus/oui.txt in IEEE plain-text format:
    AA-BB-CC   (hex)    Vendor Name

Download it during `nimbus setup` from:
    https://standards-oui.ieee.org/oui/oui.txt
"""

import re
from functools import lru_cache
from pathlib import Path

_OUI_FILE = Path.home() / ".nimbus" / "oui.txt"

_CLASS_HINTS: dict[str, str] = {
    "apple": "phone",
    "samsung": "phone",
    "google": "phone",
    "huawei": "phone",
    "xiaomi": "phone",
    "oneplus": "phone",
    "sony mobile": "phone",
    "motorola": "phone",
    "lg electronics": "phone",
    "sonos": "audio",
    "bose": "audio",
    "jabra": "audio",
    "sennheiser": "audio",
    "beats electronics": "audio",
    "fitbit": "wearable",
    "garmin": "wearable",
    "polar electro": "wearable",
    "intel corporate": "laptop",
    "hp": "laptop",
    "dell": "laptop",
    "lenovo": "laptop",
    "hewlett packard": "laptop",
    "espressif": "iot",
    "raspberry pi": "iot",
    "tuya": "iot",
}

# BLE GATT service UUID prefix (first 8 hex chars) → device class
_BLE_SERVICE_CLASSES: dict[str, str] = {
    "0000180d": "wearable",  # Heart Rate
    "00001810": "wearable",  # Blood Pressure
    "0000180f": "wearable",  # Battery (common on wearables)
    "0000110b": "audio",     # Audio Sink
    "0000110a": "audio",     # Audio Source
    "0000111e": "audio",     # Handsfree
    "00001812": "laptop",    # HID (keyboard / mouse)
    "00001815": "iot",       # Automation IO
}


@lru_cache(maxsize=1)
def _load_oui_db() -> dict[str, str]:
    if not _OUI_FILE.exists():
        return {}
    db: dict[str, str] = {}
    with _OUI_FILE.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^([0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2})\s+\(hex\)\s+(.+)$", line)
            if m:
                oui = m.group(1).replace("-", ":").lower()
                db[oui] = m.group(2).strip()
    return db


def lookup_vendor(mac: str) -> str | None:
    """Return the vendor name for the first three octets of a MAC address."""
    oui = mac.lower().replace("-", ":")[:8]
    return _load_oui_db().get(oui)


def infer_class(vendor: str | None, service_uuids: list[str] | None = None) -> str:
    """Guess device class from vendor name and/or BLE service UUIDs."""
    if service_uuids:
        for uuid in service_uuids:
            prefix = uuid.lower().replace("-", "")[:8]
            if prefix in _BLE_SERVICE_CLASSES:
                return _BLE_SERVICE_CLASSES[prefix]

    if not vendor:
        return "unknown"

    vendor_lower = vendor.lower()
    for hint, cls in _CLASS_HINTS.items():
        if hint in vendor_lower:
            return cls

    return "unknown"