# nimbus

> Give your LLM a sense of the room.

`nimbus` is a fully local, fully private [Model Context Protocol](https://modelcontextprotocol.io) server running on a Raspberry Pi. It passively observes Wi-Fi and Bluetooth Low Energy signals and exposes that activity to a local agent as structured, privacy-aware tool calls. Inference runs entirely on-device via [Ollama](https://ollama.com) — no data ever leaves the machine.

<!-- TODO: insert asciinema demo here -->

---

## Should you run this?

`nimbus` is designed for **personal, single-operator use in spaces you control** — your home, your desk, your lab.

**Do not run this in:**
- Shared workspaces or offices without the knowledge of everyone present
- Coffee shops, conference venues, or any public space
- Shared housing without explicit consent from all housemates
- Any jurisdiction where passive RF observation is restricted

You are responsible for understanding the laws in your jurisdiction (ECPA in the US, Wireless Telegraphy Act in the UK, GDPR in the EU).

---

## Install

```bash
pipx install nimbus
nimbus setup   # installs Ollama, pulls llama3.2:3b, writes systemd units
```

Requirements: Raspberry Pi 3B+ or 4 (4 GB recommended), Raspberry Pi OS Lite 64-bit (Bookworm+).

---

## Usage

```bash
nimbus ask "who is here?"
nimbus ask "has anything new shown up in the last hour?"
nimbus ask "does the device labeled roommate have a routine?"
```

Start, stop, and inspect the background collector:

```bash
nimbus status
nimbus label <mac-hash> "roommate's phone"
```

---

## Demo scenarios

<!-- TODO: replace with real terminal transcripts captured via `nimbus ask` -->

1. **Ambient sense** — *"Describe what's around me right now."*
2. **Change detection** — *"Has anything new shown up in the last hour?"*
3. **Regulars** — *"Who are my regulars?"*
4. **Pattern detection** — *"Does the device labeled 'roommate' have a routine?"*
5. **Sanity check** — *"Is the sensor working?"*
6. **Vendor spotting** — *"Any unusual devices nearby?"*

---

## Tool reference

<!-- TODO: auto-generate from schemas.py -->

| Tool | Description |
|---|---|
| `who_is_here` | Currently-present devices, deduplicated across Wi-Fi and BLE |
| `scan_wifi` | Fresh 802.11 management frame snapshot |
| `scan_ble` | Fresh BLE advertisement snapshot |
| `identify` | Everything known about a specific device |
| `presence_timeline` | Bucketed presence timeline for a device |
| `find_regulars` | Devices seen on multiple distinct days |
| `diff_presence` | What's changed since a given timestamp |
| `label` | Attach a human name to a device |
| `stats` | Collector health and database stats |

---

## Architecture

```
[ Wi-Fi radio ] ──┐
                  ├──► [ Collector ] ──► [ SQLite Store ] ◄── [ MCP Server ]
[ BLE radio   ] ──┘                                                  ▲
                                                             [ Agent script ]
                                                                      ▲
                                                             [ Ollama / llama3.2:3b ]
                                                                      ▲
                                                             [ User terminal ]
```

---

## Privacy FAQ

**Does any data leave the device?**
No. Inference runs locally via Ollama. The MCP server has no network listener. There is no telemetry or auto-update.

**Are MAC addresses stored?**
Never. Every MAC is immediately HMAC-SHA256'd with a per-install random salt. Raw MACs never enter the database or any tool response.

**How long is data retained?**
48 hours of raw observations by default. Device rollups persist for 30 days after last observation. Both are configurable downward.

**Can I exclude specific devices?**
Yes — add MAC prefixes or full MACs to `~/.nimbus/config.toml` under `[privacy] opt_out`. Those devices are never observed, hashed, or stored.

---

## Contributing

Issues and PRs welcome. Good first issues are tagged [`good-first-issue`](../../issues?q=label%3Agood-first-issue).

---

## License

MIT