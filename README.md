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

## Requirements

- Raspberry Pi 3B+ or 4 (4 GB RAM recommended)
- Raspberry Pi OS Lite 64-bit (Bookworm or later)
- Wi-Fi adapter that supports **monitor mode** (the Pi's built-in `wlan0` works; a USB adapter gives better range)
- Python 3.11+

---

## Install

### From PyPI (recommended)

```bash
pipx install nimbus
```

### From source

```bash
git clone https://github.com/VarunKausika/nimbus
cd nimbus
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## First-time setup

**1. Initialise the data directory**

Creates `~/.nimbus/` with a default config, a random per-install salt, and an empty SQLite database.

```bash
nimbus init
```

**2. Run full setup**

Downloads the OUI vendor database, installs Ollama, pulls `llama3.2:3b`, and writes systemd unit files.

```bash
nimbus setup
```

Each step can be skipped if you've already done it:

```bash
nimbus setup --skip-ollama      # OUI + systemd only
nimbus setup --skip-systemd     # OUI + Ollama only
nimbus setup --skip-oui         # Ollama + systemd only
```

**3. Put your Wi-Fi adapter into monitor mode**

```bash
sudo ip link set wlan0 down
sudo iw dev wlan0 set type monitor
sudo ip link set wlan0 up
```

If your adapter appears as a different name, update `~/.nimbus/config.toml`:

```toml
[wifi]
interface = "wlan1mon"
```

**4. Start the background services**

```bash
sudo systemctl enable --now ollama
sudo systemctl enable --now nimbus-collector
```

---

## Usage

### Ask a question

```bash
nimbus ask "who is here?"
nimbus ask "has anything new shown up in the last hour?"
nimbus ask "does the device labeled roommate have a routine?"
nimbus ask "is the sensor working?"
nimbus ask "any unusual devices nearby?"
```

The agent starts an MCP session, calls whichever tools it needs, and prints a natural-language answer.

### Check collector health

```bash
nimbus status
```

### Label a device

Find a device's hash from `nimbus ask "who is here?"`, then assign a name:

```bash
nimbus label <mac-hash> "roommate's phone"
```

The label persists in the database and appears in all future tool responses.

### Collector (manual start, for development)

The collector is normally managed by systemd. To run it directly in the foreground:

```bash
sudo nimbus collect
```

---

## Configuration

`~/.nimbus/config.toml` is created by `nimbus init` with sensible defaults:

```toml
[wifi]
interface = "wlan0mon"      # monitor-mode interface name

[retention]
hours       = 48            # raw observation retention
device_days = 30            # device rollup retention after last seen

[privacy]
# MAC addresses or prefixes to ignore entirely — never observed, hashed, or stored.
opt_out = []
# Examples:
# opt_out = ["aa:bb:cc:dd:ee:ff", "11:22:33"]  # full MAC or OUI prefix
```

---

## Development

```bash
git clone https://github.com/VarunKausika/nimbus
cd nimbus
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Run tests:**

```bash
pytest
```

**Lint and format:**

```bash
ruff check src tests
ruff format src tests
```

**Type-check:**

```bash
mypy src
```

A pre-commit hook runs `ruff --fix` and `ruff format` automatically before each commit.

---

## Tool reference

| Tool | Description |
|---|---|
| `who_is_here` | Currently-present devices, deduplicated across Wi-Fi and BLE |
| `scan_wifi` | Fresh 802.11 management frame snapshot (active scan, ~10 s) |
| `scan_ble` | Fresh BLE advertisement snapshot (passive scan, ~10 s) |
| `identify` | Everything known about a specific device hash |
| `presence_timeline` | Bucketed presence timeline for a device over N hours |
| `find_regulars` | Devices seen on multiple distinct days |
| `diff_presence` | What's new, departed, or lingering since a given timestamp |
| `label` | Attach a human name to a device hash |
| `stats` | Collector health and database stats |

---

## Architecture

```
[ Wi-Fi radio ] ──┐
                  ├──► [ Collector ] ──► [ SQLite Store ] ◄── [ MCP Server ]
[ BLE radio   ] ──┘                                                  ▲
                                                             [ Agent (nimbus ask) ]
                                                                      ▲
                                                             [ Ollama / llama3.2:3b ]
                                                                      ▲
                                                             [ User terminal ]
```

- **Collector** (`nimbus collect`): scapy AsyncSniffer for 802.11 management frames + Bleak BleakScanner for BLE advertisements. Runs as a systemd service with `CAP_NET_RAW`/`CAP_NET_ADMIN`.
- **Store**: SQLite in WAL mode at `~/.nimbus/nimbus.db`. Retention loop purges old observations on a background timer.
- **MCP Server** (`nimbus.server.app`): stdio-transport MCP server. Started as a subprocess by the agent on each `nimbus ask` invocation.
- **Agent** (`nimbus ask`): connects to the MCP server, discovers tools, and runs a tool-calling loop with Ollama until a final answer is produced.

---

## Privacy FAQ

**Does any data leave the device?**
No. Inference runs locally via Ollama. The MCP server has no network listener. There is no telemetry or auto-update.

**Are MAC addresses stored?**
Never. Every MAC is immediately HMAC-SHA256'd with a per-install random salt before anything is written to disk. Raw MACs never enter the database or any tool response.

**How long is data retained?**
48 hours of raw observations by default. Device rollups persist for 30 days after last observation. Both are configurable downward in `~/.nimbus/config.toml`.

**Can I exclude specific devices?**
Yes — add MAC prefixes or full MACs to `~/.nimbus/config.toml` under `[privacy] opt_out`. Those devices are silently dropped at capture time and never hashed or stored.

**What if I want to delete everything?**
```bash
sudo systemctl stop nimbus-collector
rm -rf ~/.nimbus
```

---

## Contributing

Issues and PRs welcome. Good first issues are tagged [`good-first-issue`](../../issues?q=label%3Agood-first-issue).

---

## License

MIT
