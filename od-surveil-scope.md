# mcp-presence — Scope Document

**Version:** 0.2 (pre-build draft)
**Author:** Varun Kausika
**Target platform:** Raspberry Pi (3B+ or 4), Linux
**Expected build time:** 12–18 hours across a weekend
**License:** MIT (planned)

---

## 1. Elevator Pitch

`mcp-presence` is a fully local, fully private Model Context Protocol server that gives an LLM a *sense of place*. Running on a single Raspberry Pi with nothing but its built-in radios, it passively observes the Wi-Fi and Bluetooth Low Energy (BLE) signals in the air around it and exposes that activity to a local agent as a set of structured, privacy-aware tools and resources. Inference runs entirely on-device via Ollama — no data ever leaves the machine.

The project's novelty is not the underlying sniffing — that technology is decades old — but the *tool surface design*. There is no published MCP server today that lets an agent ask questions like "who is around right now?", "has anyone new shown up in the last hour?", or "is this MAC address a regular visitor?" in a clean, turn-based, privacy-respecting way. Translating a continuous, high-volume stream of radio observations into a finite set of agent-legible tool calls is a genuinely interesting MCP design problem and is the core technical contribution of the project.

---

## 2. Goals and Non-Goals

### Goals

- Ship a polished, installable MCP server that runs on a stock Raspberry Pi OS image with under ten minutes of setup.
- Expose six to ten carefully chosen MCP tools that cover the useful ambient-presence question space without overwhelming the model's context.
- Demonstrate at least five agent demo scenarios end-to-end, captured as short screen recordings or terminal transcripts in the README.
- Treat privacy as a first-class design constraint: local-only storage, MAC hashing by default, clear retention policy, and an explicit opt-out list.
- Be a strong open-source artifact: clean code, typed Python, tests for the non-hardware logic, CI, and a README that a casual GitHub browser can understand in under two minutes.

### Non-Goals

- This is not a network intrusion tool. No active probing, no deauthentication, no handshake capture, no packet injection.
- This is not a people-tracking or employee-monitoring product. The tools are deliberately coarse-grained and log-retention is short by default.
- This is not a full Wi-Fi analytics platform. No channel sweeping optimization, no GPS-assisted wardriving, no cloud sync.
- No attempt at MAC-to-identity resolution beyond OUI vendor lookup (which is already public information).
- Not a commercial product. The README will explicitly discourage deployment in contexts where consent is ambiguous (e.g., shared workspaces).

---

## 3. Target Audience and Success Criteria

### Audience

Primary: the "hardware-curious AI engineer" demographic on GitHub and Hacker News — people who already follow MCP developments and are looking for concrete, runnable examples of novel server designs.

Secondary: home-lab and self-hosting communities (r/selfhosted, r/homelab) who will care about the "what's on my network" utility angle.

### Success Criteria

- **Launch week:** 250+ GitHub stars, one front-page HN or Lobste.rs submission, at least three forks that run the code.
- **Technical:** the server runs for 24 hours on a Pi 4 without crashing or exceeding 150 MB RAM. Ninety percent of tool calls return in under 500 ms.
- **Demo:** a first-time user can clone, install, run, and get a correct answer to "who is around me right now?" within 15 minutes.
- **Narrative:** a follow-up blog post that generalizes the "continuous signals → turn-based tools" design pattern to other MCP servers (SDR, sensor arrays, etc.).

---

## 4. Technical Architecture

The system is four cooperating processes, each with a single responsibility:

**Collector.** A long-running Python process with `CAP_NET_RAW` capability. Runs two asynchronous loops: a Wi-Fi loop that uses `scapy` to sniff 802.11 management frames on a monitor-mode interface, and a BLE loop that uses `bleak` to run passive BLE advertisements scans. Every observation is normalized into a single `Observation` record and appended to a SQLite WAL database.

**Store.** A thin SQLite database (`~/.mcp-presence/state.db`) with three tables: `observations` (append-only ring buffer, default 48-hour retention), `devices` (hashed-MAC-keyed rollups with first-seen / last-seen / observation count), and `labels` (user-assigned friendly names, optional). WAL mode so the MCP server can read while the collector writes.

**MCP server.** A `stdio`-transport MCP server using the official Python SDK. Reads from the Store (never writes observations — it can only update `labels`) and exposes the tool and resource surfaces described in sections 7 and 8. Holds no long-lived state of its own; every tool call is a read-mostly query against SQLite.

**Agent script.** A small custom Python script (~50–80 lines) that acts as the MCP client. It spawns the MCP server as a subprocess, connects to Ollama's local API (using the `ollama` Python library), and runs a simple tool-calling loop: send user message → model picks a tool → script executes the tool against the MCP server → result fed back to model → repeat until model gives a final answer. This replaces cloud-based clients (Claude Desktop, Claude Code) entirely.

**Ollama** runs as a local service on the same machine, serving `llama3.2:3b`. All inference is on-device; no data leaves the Pi.

```
[ Wi-Fi radio ] ──┐
                  │
                  ├──► [ Collector ] ──► [ SQLite Store ] ◄── [ MCP Server ]
                  │                                                  ▲
[ BLE radio   ] ──┘                                         [ Agent script ]
                                                                     ▲
                                                              [ Ollama / llama3.2:3b ]
                                                                     ▲
                                                              [ User terminal ]
```

The separation matters because the collector needs elevated privileges and runs continuously, while the MCP server and agent script run on demand and should be cheap to start and stop.

### Runtime topology

- Collector as a `systemd` service (`mcp-presence-collector.service`), enabled at boot.
- Ollama as a `systemd` service (`ollama.service`), enabled at boot.
- MCP server spawned as a subprocess by the agent script on each invocation.
- Agent script launched interactively by the user (`mcp-presence ask "who is here?"`).
- No network listeners. The MCP server is stdio-only; the collector only opens raw sockets on the local radio interfaces; Ollama listens on localhost only.

---

## 5. Hardware Requirements

| Component | Required / Optional | Notes |
|---|---|---|
| Raspberry Pi 3B+ or 4 | Required | Pi 4 preferred for headroom on concurrent Wi-Fi + BLE. Pi Zero 2 W works but will drop frames under load. |
| microSD card (16 GB+) | Required | Standard Raspberry Pi OS (64-bit) |
| Power supply | Required | Official Pi 4 PSU or equivalent; undervolting breaks the Wi-Fi radio |
| USB Wi-Fi adapter with monitor-mode support | Optional | Only needed if the onboard `brcmfmac` driver refuses monitor mode on your Pi revision. An Alfa AWUS036ACM or similar costs ~$25 but is genuinely optional — most Pi 4s work fine with onboard |
| External antenna | Not required | Onboard antennas are sufficient for a single-room demo |

**Total out-of-pocket cost, typical case:** $0. The project assumes the user already has a Pi, power supply, and SD card.

---

## 6. Software Stack

- **OS:** Raspberry Pi OS Lite (64-bit), Bookworm or later
- **Language:** Python 3.11+
- **MCP SDK:** `mcp` (official Python SDK, `>=1.0`) — used for both the server and the client-side subprocess connection in the agent script
- **Local inference:** Ollama (installed via official install script), model `llama3.2:3b`
- **Ollama Python client:** `ollama>=0.3` — used in the agent script to drive the tool-calling loop
- **Packet capture:** `scapy>=2.5` for Wi-Fi, `bleak>=0.21` for BLE
- **Storage:** stdlib `sqlite3` with WAL mode
- **Config:** `tomllib` (stdlib), single `~/.mcp-presence/config.toml` file
- **CLI / lifecycle:** `typer` for the admin CLI (`mcp-presence init`, `mcp-presence status`, `mcp-presence label`, `mcp-presence ask`)
- **Dev tooling:** `ruff`, `mypy --strict`, `pytest`, `pytest-asyncio`
- **CI:** GitHub Actions matrix on Python 3.11 / 3.12, `ubuntu-latest` (hardware tests gated behind a self-hosted Pi runner, stretch goal)

Installed via `pipx install mcp-presence` with one post-install helper (`mcp-presence setup`) that writes the systemd unit files, installs Ollama, pulls `llama3.2:3b`, and offers to enable monitor mode.

---

## 7. MCP Tool Surface

The tool surface is deliberately small. Each tool answers a question a human operator would plausibly ask aloud. Every tool accepts an optional `since` parameter (ISO 8601 timestamp or relative like `"1h"`, `"30m"`) defaulting to "the last 5 minutes" so the model never accidentally drags a 48-hour window into context.

### `who_is_here(since: str = "5m", min_observations: int = 3) -> PresenceReport`

Returns a list of currently-present devices, deduplicated across Wi-Fi and BLE where possible. Each entry includes the hashed MAC, inferred vendor (OUI lookup), device-class guess (phone / laptop / audio / wearable / IoT / unknown), signal-strength summary, first- and last-seen timestamps in the window, and a human label if one has been assigned. Filters out devices with fewer than `min_observations` hits to suppress noise from randomized MACs that only broadcast once.

### `scan_wifi(duration_s: int = 10) -> WiFiScanResult`

Triggers a short fresh scan of 802.11 management frames and returns access points (SSID, BSSID, channel, RSSI band, beacon interval) and probe-request traffic (hashed client MAC, probed SSIDs). The model gets a snapshot of the RF environment without having to reason about passive-observation windows.

### `scan_ble(duration_s: int = 10) -> BLEScanResult`

Same idea for BLE: returns advertising devices with advertised names (truncated to 32 bytes), service UUIDs, manufacturer data fingerprint, and RSSI. Deliberately does not attempt to connect or pair.

### `identify(mac_or_hash: str) -> DeviceIdentity`

Given a hashed MAC or raw MAC (raw only accepted from within the local config, not from remote tool calls), returns everything the system knows about that device: vendor, probed SSIDs if Wi-Fi, advertised services if BLE, observed channels, observation count, first- and last-seen, and any user-assigned label.

### `presence_timeline(mac_or_hash: str, hours: int = 24, bucket_minutes: int = 15) -> Timeline`

Returns a bucketed timeline showing when a given device was observed. Intentionally bucketed, not raw, because a 24-hour timeline at one-second resolution is both privacy-toxic and context-toxic. The agent can use this to answer questions like "does this device show up every morning?"

### `find_regulars(hours_back: int = 168, min_days_seen: int = 3) -> list[RegularDevice]`

Returns devices that have been observed on at least `min_days_seen` distinct days in the lookback window. This is the "who are my regular neighbors / housemates" query. Hashed MACs only.

### `diff_presence(since: str) -> PresenceDiff`

Returns `{new: [...], departed: [...], lingering: [...]}` relative to a prior timestamp. Useful for "what's changed since I last asked" loops.

### `label(mac_or_hash: str, name: str) -> None`

Lets the operator (via the agent) attach a human-readable label to a device, persisted in the `labels` table. Write-scoped; will prompt for explicit confirmation via the MCP sampling hook if available.

### `stats() -> CollectorStats`

Returns collector health: frames per second, unique devices seen in the last hour, database size, oldest retained observation. The agent can use this to sanity-check whether the sensor is actually working before answering presence questions.

**Total: 9 tools.** Small enough to fit in a single prompt alongside a reasonable system message.

---

## 8. MCP Resource Surface

Resources are for read-often, low-query-cost data. The server exposes three:

- `presence://current` — a point-in-time snapshot of the "who is here" report as JSON, refreshed every 30 seconds. Lets a client watch the room without polling a tool.
- `presence://config` — the active configuration (retention window, MAC hashing salt *prefix* only, opt-out list size). Never exposes secrets.
- `presence://schema` — the full JSON Schema for every tool result, so the agent can reason about fields without trial and error.

---

## 9. Data Model

```sql
CREATE TABLE observations (
    id            INTEGER PRIMARY KEY,
    ts            INTEGER NOT NULL,        -- unix epoch seconds
    radio         TEXT NOT NULL,            -- 'wifi' | 'ble'
    mac_hash      TEXT NOT NULL,            -- HMAC-SHA256 of MAC, truncated to 16 hex chars
    rssi          INTEGER,
    channel       INTEGER,
    frame_type    TEXT,                     -- 'probe_req' | 'beacon' | 'adv' | ...
    extra_json    TEXT                      -- SSID, service UUIDs, manufacturer data fingerprint
);
CREATE INDEX obs_ts ON observations(ts);
CREATE INDEX obs_mac ON observations(mac_hash);

CREATE TABLE devices (
    mac_hash        TEXT PRIMARY KEY,
    first_seen      INTEGER NOT NULL,
    last_seen       INTEGER NOT NULL,
    observation_n   INTEGER NOT NULL,
    vendor_oui      TEXT,
    inferred_class  TEXT
);

CREATE TABLE labels (
    mac_hash TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    set_at   INTEGER NOT NULL
);
```

Retention: a background task in the collector truncates `observations` older than the configured window (default 48h). `devices` rollups persist until the device has not been seen for 30 days, then are garbage-collected.

---

## 10. Privacy and Safety

Privacy is a scope item, not a stretch goal. The design decisions:

1. **Fully local inference.** The agent runs `llama3.2:3b` via Ollama on the same machine. No query, tool result, or presence data is ever sent to a cloud API. This is a stronger privacy guarantee than MAC hashing alone — the data never leaves the device at any layer of the stack.
2. **Local-only by default.** No network listener. No telemetry. No auto-update. The first line of the README will say so.
3. **MAC hashing.** Every MAC is immediately HMAC-SHA256'd with a per-install random salt stored in `~/.mcp-presence/salt`. Raw MACs never enter the database or any tool response. Hashes are consistent within an install so regulars can be identified over time, but cannot be correlated across installs.
4. **Short retention.** 48 hours of raw observations, 30 days of rolled-up device metadata. Both configurable downward (not upward without editing source).
5. **Opt-out list.** A simple config file where the operator can paste MAC prefixes or full MACs that should be ignored entirely — never observed, never hashed, never stored.
6. **No SSID leakage of probed networks belonging to observed clients.** Probe-request SSIDs are captured but only returned by `identify()` for the device making the probe, never in aggregate listings.
7. **Explicit deployment guidance.** The README's first section is titled "Should you run this?" and explicitly says no to offices, coffee shops, conference venues, and shared housing without housemate consent.
8. **Write tools are gated.** The only write-capable tool is `label`, which mutates a user-facing label on a device the operator already knows about. No deletion tools via MCP; deletion requires the admin CLI.

### Legal considerations

Passive reception of unencrypted Wi-Fi management frames and BLE advertisements is generally legal in the US, UK, and EU for personal research purposes, but laws vary by jurisdiction and change. The README will include a clear statement that the operator is responsible for understanding their local law (specifically mentioning the ECPA in the US, the Wireless Telegraphy Act in the UK, and the GDPR in the EU) and will not ship with a "production" marketing pitch.

---

## 11. Implementation Plan (Weekend Timebox)

### Saturday morning (4 hours) — Plumbing

- Scaffold repo (`pyproject.toml`, ruff/mypy/pytest configs, GitHub Actions skeleton).
- Implement the Store layer with SQLite WAL and retention task. Unit-test with fixtures.
- Implement MAC hashing module with property-based tests.
- Stub collector with a fake observation generator so the MCP server can be developed in parallel without hardware.

### Saturday afternoon (4 hours) — MCP server + agent script

- Wire the MCP Python SDK, define tool schemas in Pydantic models.
- Implement all 9 tools against the Store, using the fake collector as fixture data.
- Write integration tests using the MCP SDK's in-process test harness.
- Implement the 3 resources.
- Write the agent script: spawn MCP server subprocess, connect to Ollama (`llama3.2:3b`), implement the tool-calling loop. Verify end-to-end with fake collector data before touching hardware.

### Saturday evening (2 hours) — Real Wi-Fi

- Bring up monitor mode on the Pi (`iw dev wlan0 set monitor control`), capture probe-requests and beacons with scapy.
- Replace the fake collector's Wi-Fi loop with the real one. Verify devices appear in the Store with correct RSSI and channel.

### Sunday morning (3 hours) — Real BLE

- Implement the BLE loop with `bleak`, passive mode.
- Handle the Wi-Fi + BLE dedup heuristic (same vendor OUI + overlapping active window + similar RSSI → probably one device).
- End-to-end test: real radios → Store → MCP server → agent answers "who is here."

### Sunday afternoon (3 hours) — Polish and ship

- Write the README (see section 13).
- Record 5 demo prompts + agent responses as terminal transcripts (via `mcp-presence ask`).
- Draft the systemd unit files and `mcp-presence setup` helper (includes Ollama install + model pull).
- Tag v0.1.0, publish to PyPI, open HN submission in a draft window.

### Buffer: 2 hours for the inevitable monitor-mode driver fight, plus Ollama cold-start tuning on Pi hardware.

---

## 12. Demo Scenarios

Each of these should be captured verbatim in the README:

1. **Ambient sense.** *"Describe what's around me right now."* → Agent calls `who_is_here()`, responds with a natural-language summary: "Three phones (two Apple, one Samsung), one Sonos speaker, your laptop, seven neighbor Wi-Fi networks, and two AirTags — one of which has been here for nine hours."

2. **Change detection.** *"Has anything new shown up in the last hour?"* → Agent calls `diff_presence(since="1h")`, identifies a newly-appeared hashed MAC with vendor "Espressif", correctly infers it's a new IoT device, and asks the operator if they just plugged something in.

3. **Regulars.** *"Who are my regulars?"* → Agent calls `find_regulars(hours_back=168)`, returns hashed MACs that appear on 5+ days of the past week, prompts the operator to label them.

4. **Pattern detection.** *"Does the device labeled 'roommate' have a routine?"* → Agent calls `presence_timeline(mac_or_hash="<labeled>", hours=168)`, summarizes: "Present Mon–Fri from ~8pm to ~8am, absent weekends."

5. **Sanity check.** *"Is the sensor working?"* → Agent calls `stats()`, reports "2,430 frames/sec, 47 unique devices last hour, 120 MB of observations on disk, oldest obs 47h52m ago."

6. **Vendor spotting.** *"Any unusual devices nearby?"* → Agent calls `scan_ble(30)`, identifies a device with manufacturer data fingerprint matching a known model of security camera the operator doesn't own.

---

## 13. Repository Structure

```
mcp-presence/
├── README.md                    # see section 14
├── LICENSE                      # MIT
├── pyproject.toml
├── src/mcp_presence/
│   ├── __init__.py
│   ├── collector/
│   │   ├── wifi.py
│   │   ├── ble.py
│   │   └── dedup.py
│   ├── store/
│   │   ├── schema.py
│   │   ├── queries.py
│   │   └── retention.py
│   ├── privacy/
│   │   ├── hashing.py
│   │   └── optout.py
│   ├── server/
│   │   ├── app.py               # MCP server entry point
│   │   ├── tools.py
│   │   ├── resources.py
│   │   └── schemas.py           # Pydantic models
│   ├── agent.py                 # MCP client + Ollama tool-calling loop
│   └── cli.py                   # typer admin CLI (includes `ask` subcommand)
├── systemd/
│   ├── mcp-presence-collector.service
│   └── ollama.service           # local Ollama daemon
├── tests/
│   ├── test_store.py
│   ├── test_privacy.py
│   ├── test_tools.py
│   ├── test_agent.py            # agent loop tests with mocked Ollama + MCP
│   └── fixtures/
└── docs/
    ├── design.md
    ├── privacy.md
    └── demos/
        ├── 01-ambient-sense.md
        └── ...
```

---

## 14. README and Launch Plan

### README sections (in order)

1. One-sentence pitch and a 20-second animated terminal demo (asciinema).
2. **"Should you run this?"** — deployment guidance / explicit "not this" list.
3. Install — `pipx install mcp-presence && mcp-presence setup` (installs Ollama, pulls `llama3.2:3b`, writes systemd units).
4. Usage — `mcp-presence ask "who is here?"` and how the agent loop works locally.
5. Six demo prompts with real transcripts.
6. Tool reference (auto-generated from `schemas.py`).
7. Architecture diagram (inline Mermaid).
8. Privacy FAQ — including explicit note that inference is local via Ollama and no data reaches any cloud API.
9. Contributing.

### Launch plan

- Day 0: tag v0.1.0, publish to PyPI, push docs.
- Day 1: Show HN submission titled *"Show HN: mcp-presence — I gave an LLM a sense of the room via a Raspberry Pi"*. Pre-drafted to avoid post-hoc editing.
- Day 1: /r/selfhosted, /r/raspberry_pi, /r/LocalLLaMA cross-posts with scenario-specific framing.
- Day 2: short blog post — *"Turning continuous radio into turn-based tool calls: the core MCP design problem."* Generalizes beyond this project.
- Week 1: respond to every issue and PR. Set a `good-first-issue` label on three deliberately scoped items (new vendor lookups, additional device-class heuristics, Docker packaging).

---

## 15. Risks and Open Questions

| Risk | Likelihood | Mitigation |
|---|---|---|
| Onboard Pi Wi-Fi refuses monitor mode on the user's specific Pi revision | Medium | Fall back to `brcmfmac` firmware nexmon patch, or document the USB dongle option. Test on Pi 4B and Pi 3B+ before publishing. |
| MAC randomization hides most phones | High | Accept it; design presence heuristics around vendor + probe-SSID patterns rather than raw MAC continuity. Document the limitation prominently. |
| BLE and Wi-Fi compete for the same 2.4 GHz radio on some Pi revisions, causing frame drops | Medium | Document expected performance; add a config option to run BLE-only or Wi-Fi-only. |
| `llama3.2:3b` tool-calling reliability is inconsistent | Medium | Test tool-calling accuracy with all 9 tools early. If reliability is poor, add a tighter system prompt constraining output format; fall back to structured output mode if the `ollama` library supports it. |
| Ollama + `llama3.2:3b` is slow on Pi 4 (potentially 5–15s per response) | High | Set user expectations in the README. For demo transcripts, note response times. Consider running Ollama on a laptop on the same LAN and pointing the agent script at it via `OLLAMA_HOST` env var. |
| Pi 4 runs out of RAM with Ollama + collector both active | Medium | `llama3.2:3b` needs ~2 GB; the collector needs <100 MB. Should be fine on a 4 GB Pi 4. Document minimum hardware as Pi 4 4 GB; explicitly unsupported on 1 GB or 2 GB variants. |
| Privacy blowback on launch | Low | Local inference via Ollama is a strong answer to this concern. Lead with it. |
| Scope creep into people-tracking features | Medium (self-inflicted) | This scope doc is the defense. Any feature that increases identifiability is a v0.2+ question at the earliest, and probably a hard no. |
| Weekend overruns into a week | High | Cut scope in this order: stretch goals → `diff_presence` → `find_regulars` → the dedup heuristic. Ship with a smaller tool surface rather than skipping polish. |

### Open questions to resolve before coding

- Which Python MCP SDK version is current and stable on the day of the build? Pin accordingly.
- Is there a well-maintained OUI vendor database we can ship (IEEE list is ~3 MB) or should we query at runtime? Decision: ship, avoid network dependency.
- Does the collector need root, or is `CAP_NET_RAW` + `CAP_NET_ADMIN` sufficient? Verify during Saturday morning setup.
- Does the `ollama` Python library's tool-calling interface match what `llama3.2:3b` expects natively, or does it need a custom system prompt to drive reliable JSON tool calls? Prototype this first before building the full agent loop.

---

## 16. Stretch Goals (Post-v0.1)

- **Acoustic sense.** If the operator has any USB microphone, add a parallel collector for ambient sound classification (YAMNet or similar). Adds a `listen(duration)` tool and a `recent_sounds()` resource. Generalizes the "sense of place" story.
- **Named-device graph.** Once enough labels exist, auto-infer relationships ("laptop-Varun and phone-Varun are always co-present"). Purely local, purely descriptive.
- **Multi-Pi federation.** A second Pi in a different room, talking to the first over a local-only protocol. "Where in the house is device X?" becomes answerable.
- **Presence webhooks.** Not an MCP feature, but a useful companion — fire a local HTTP callback when a specific labeled device arrives or departs.
- **Home Assistant integration.** Expose the presence data as HA sensors.

---

## 17. Definition of Done for v0.1

- [ ] `pipx install mcp-presence && mcp-presence setup` works on a fresh Pi OS image in under 10 minutes (including Ollama install and model pull).
- [ ] All 9 tools and 3 resources implemented, tested, and documented.
- [ ] Agent script (`mcp-presence ask`) drives end-to-end tool-calling loop via Ollama locally.
- [ ] Collector runs for 24 hours without OOM or crash alongside Ollama on a Pi 4 4 GB.
- [ ] README includes 6 real demo transcripts captured via `mcp-presence ask`.
- [ ] Privacy section, opt-out list, and MAC hashing verified working.
- [ ] CI green on Python 3.11 and 3.12.
- [ ] Published to PyPI and GitHub with v0.1.0 tag.
- [ ] One Show HN submission drafted and ready.