# Privacy Design

<!-- TODO: expand during implementation -->

## Principles

1. Fully local inference — no query or tool result ever leaves the device
2. No raw MACs in the database — HMAC-SHA256 with a per-install salt
3. Short retention — 48h observations, 30d device rollups (configurable downward)
4. Opt-out list — ignored at capture time, before hashing
5. No SSID aggregation across clients — probe SSIDs only returned via `identify()`
6. Write tools gated — only `label` mutates state; deletions require the admin CLI

## Legal

Passive reception of unencrypted 802.11 management frames and BLE advertisements is
generally legal for personal research in the US, UK, and EU, but laws vary. The operator
is responsible for their local jurisdiction.

Relevant instruments: ECPA (US), Wireless Telegraphy Act (UK), GDPR (EU).
