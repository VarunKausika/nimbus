from pydantic import BaseModel


class DeviceEntry(BaseModel):
    mac_hash: str
    vendor: str | None
    device_class: str  # 'phone' | 'laptop' | 'audio' | 'wearable' | 'iot' | 'unknown'
    rssi_min: int | None
    rssi_max: int | None
    rssi_avg: int | None
    first_seen: str  # ISO 8601
    last_seen: str  # ISO 8601
    label: str | None


class PresenceReport(BaseModel):
    devices: list[DeviceEntry]
    window: str
    generated_at: str  # ISO 8601


class AccessPoint(BaseModel):
    ssid: str | None
    bssid_hash: str
    channel: int | None
    rssi_band: str  # 'strong' | 'medium' | 'weak'
    beacon_interval_ms: int | None


class ProbeRequest(BaseModel):
    mac_hash: str
    probed_ssids: list[str]


class WiFiScanResult(BaseModel):
    access_points: list[AccessPoint]
    probe_requests: list[ProbeRequest]
    duration_s: int
    scanned_at: str  # ISO 8601


class BLEDevice(BaseModel):
    mac_hash: str
    name: str | None  # truncated to 32 chars
    service_uuids: list[str]
    manufacturer_fingerprint: str | None
    rssi: int | None


class BLEScanResult(BaseModel):
    devices: list[BLEDevice]
    duration_s: int
    scanned_at: str  # ISO 8601


class DeviceIdentity(BaseModel):
    mac_hash: str
    vendor: str | None
    device_class: str
    probed_ssids: list[str]
    advertised_services: list[str]
    observed_channels: list[int]
    observation_count: int
    first_seen: str  # ISO 8601
    last_seen: str  # ISO 8601
    label: str | None


class TimelineBucket(BaseModel):
    start: str  # ISO 8601
    observation_count: int


class Timeline(BaseModel):
    mac_hash: str
    bucket_minutes: int
    hours: int
    buckets: list[TimelineBucket]


class RegularDevice(BaseModel):
    mac_hash: str
    vendor: str | None
    device_class: str
    days_seen: int
    label: str | None


class PresenceDiff(BaseModel):
    new: list[DeviceEntry]
    departed: list[DeviceEntry]
    lingering: list[DeviceEntry]
    since: str  # ISO 8601


class CollectorStats(BaseModel):
    frames_per_second: float
    unique_devices_last_hour: int
    database_size_bytes: int
    oldest_observation: str | None  # ISO 8601
    uptime_seconds: float
