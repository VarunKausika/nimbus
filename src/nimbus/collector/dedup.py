"""Heuristic for correlating a Wi-Fi mac_hash with a BLE mac_hash.

A device is considered the same physical device if all three conditions hold:
  1. Same vendor OUI (both must be known; unknown vendors are not correlated)
  2. Both last seen within `window_seconds` of each other
  3. RSSI values within `rssi_tolerance_db` dBm (if both are available)
"""


def maybe_same_device(
    wifi_mac_hash: str,
    wifi_vendor: str | None,
    wifi_rssi: int | None,
    wifi_last_seen: int,
    ble_mac_hash: str,
    ble_vendor: str | None,
    ble_rssi: int | None,
    ble_last_seen: int,
    window_seconds: int = 30,
    rssi_tolerance_db: int = 10,
) -> bool:
    if wifi_mac_hash == ble_mac_hash:
        return True

    # Require both vendors to be known and matching
    if not wifi_vendor or not ble_vendor:
        return False
    if wifi_vendor.lower() != ble_vendor.lower():
        return False

    # Both must have been active within the same time window
    if abs(wifi_last_seen - ble_last_seen) > window_seconds:
        return False

    # If both have RSSI readings, they must be within tolerance
    if wifi_rssi is not None and ble_rssi is not None:
        if abs(wifi_rssi - ble_rssi) > rssi_tolerance_db:
            return False

    return True