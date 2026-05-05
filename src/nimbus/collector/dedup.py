"""Heuristic for correlating a Wi-Fi mac_hash with a BLE mac_hash.

A device is considered the same if:
  - Same vendor OUI
  - Both active within the same 30-second window
  - RSSI values within 10 dBm of each other
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
    raise NotImplementedError