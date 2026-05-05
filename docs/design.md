# Design Notes

<!-- TODO: expand during implementation -->

## Continuous signals → turn-based tools

The core design problem in nimbus is translating a high-volume, continuous stream of
radio observations into a finite set of agent-legible tool calls. See the scope document
for the full rationale.

## SQLite WAL mode

The collector writes continuously while the MCP server reads on demand. WAL mode allows
concurrent reads without blocking writes, which avoids the need for a separate IPC layer.

## MAC hashing

See `src/nimbus/privacy/hashing.py` and `docs/privacy.md`.

## Deduplication heuristic

Wi-Fi and BLE may observe the same physical device under different (randomized) MACs.
The heuristic in `src/nimbus/collector/dedup.py` correlates observations by vendor OUI,
active window overlap, and RSSI proximity.
