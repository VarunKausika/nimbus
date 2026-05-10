"""Admin CLI — all nimbus user-facing commands.

Entry point: the `nimbus` script defined in pyproject.toml.
"""

import asyncio
import shutil
import subprocess
import sys
import tomllib
from importlib import resources as importlib_resources
from pathlib import Path

import typer

from .privacy.hashing import SALT_PATH, load_or_create_salt
from .store.schema import DB_PATH, NIMBUS_DIR, open_db

app = typer.Typer(name="nimbus", help="Local ambient presence sensing via MCP.", no_args_is_help=True)

_CONFIG_PATH = NIMBUS_DIR / "config.toml"
_OUI_URL = "https://standards-oui.ieee.org/oui/oui.txt"
_OUI_PATH = NIMBUS_DIR / "oui.txt"

_DEFAULT_CONFIG = """\
# nimbus configuration
# See https://github.com/VarunKausika/nimbus for full documentation.

[wifi]
interface = "wlan0mon"

[retention]
hours      = 48   # raw observation retention
device_days = 30  # device rollup retention

[privacy]
# List MAC addresses or prefixes (e.g. "aa:bb:cc") to ignore entirely.
# These are never observed, hashed, or stored.
opt_out = []
"""

_SYSTEMD_DIR = Path("/etc/systemd/system")


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@app.command()
def init() -> None:
    """Initialise ~/.nimbus — create config, generate salt, create database."""
    NIMBUS_DIR.mkdir(parents=True, exist_ok=True)

    if _CONFIG_PATH.exists():
        typer.echo(f"Config already exists at {_CONFIG_PATH} — skipping.")
    else:
        _CONFIG_PATH.write_text(_DEFAULT_CONFIG)
        typer.echo(f"Created {_CONFIG_PATH}")

    salt = load_or_create_salt()
    typer.echo(f"Salt ready at {SALT_PATH} ({len(salt)} bytes)")

    conn = open_db()
    conn.close()
    typer.echo(f"Database ready at {DB_PATH}")

    typer.echo("\nnimbus init complete. Run `nimbus setup` to install Ollama and systemd units.")


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

@app.command()
def setup(
    skip_ollama: bool = typer.Option(False, "--skip-ollama", help="Skip Ollama install and model pull."),
    skip_systemd: bool = typer.Option(False, "--skip-systemd", help="Skip writing systemd unit files."),
    skip_oui: bool = typer.Option(False, "--skip-oui", help="Skip downloading the OUI vendor database."),
) -> None:
    """Post-install setup: Ollama, llama3.2:3b, OUI database, systemd units."""
    # Ensure init has been run
    if not _CONFIG_PATH.exists():
        typer.echo("Running `nimbus init` first...")
        init()

    # --- OUI database ---
    if not skip_oui:
        _setup_oui()

    # --- Ollama ---
    if not skip_ollama:
        _setup_ollama()

    # --- systemd ---
    if not skip_systemd:
        _setup_systemd()

    typer.echo("\nnimbus setup complete.")
    typer.echo("Start the collector:  sudo systemctl start nimbus-collector")
    typer.echo("Ask a question:       nimbus ask 'who is here?'")


def _setup_oui() -> None:
    if _OUI_PATH.exists():
        typer.echo(f"OUI database already present at {_OUI_PATH} — skipping download.")
        return

    typer.echo(f"Downloading OUI vendor database from {_OUI_URL} ...")
    try:
        import urllib.request
        urllib.request.urlretrieve(_OUI_URL, _OUI_PATH)
        typer.echo(f"OUI database saved to {_OUI_PATH} ({_OUI_PATH.stat().st_size // 1024} KB)")
    except Exception as exc:
        typer.echo(f"Warning: OUI download failed ({exc}). Vendor names will be unavailable.", err=True)


def _setup_ollama() -> None:
    if shutil.which("ollama"):
        typer.echo("Ollama already installed.")
    else:
        typer.echo("Installing Ollama...")
        result = subprocess.run(
            ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
            check=False,
        )
        if result.returncode != 0:
            typer.echo("Ollama install failed. Install manually: https://ollama.com", err=True)
            raise typer.Exit(1)
        typer.echo("Ollama installed.")

    typer.echo("Pulling llama3.2:3b (this may take a few minutes on first run)...")
    result = subprocess.run(["ollama", "pull", "llama3.2:3b"], check=False)
    if result.returncode != 0:
        typer.echo("Model pull failed. Is `ollama serve` running?", err=True)
        raise typer.Exit(1)
    typer.echo("llama3.2:3b ready.")


def _setup_systemd() -> None:
    if not _SYSTEMD_DIR.exists():
        typer.echo("systemd not found — skipping unit file installation.")
        return

    nimbus_bin = shutil.which("nimbus") or sys.executable
    units = {
        "nimbus-collector.service": _collector_unit(nimbus_bin),
        "ollama.service": _ollama_unit(),
    }

    for unit_name, content in units.items():
        dest = _SYSTEMD_DIR / unit_name
        try:
            dest.write_text(content)
            typer.echo(f"Wrote {dest}")
        except PermissionError:
            typer.echo(f"Permission denied writing {dest} — re-run with sudo.", err=True)
            raise typer.Exit(1)

    subprocess.run(["systemctl", "daemon-reload"], check=False)
    typer.echo("systemd units installed. Enable with:")
    typer.echo("  sudo systemctl enable --now nimbus-collector ollama")


def _collector_unit(nimbus_bin: str) -> str:
    return f"""\
[Unit]
Description=Nimbus Wi-Fi and BLE collector
After=network.target

[Service]
Type=simple
ExecStart={nimbus_bin} collect
Restart=on-failure
RestartSec=5s
AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN
CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""


def _ollama_unit() -> str:
    return """\
[Unit]
Description=Ollama local inference server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/ollama serve
Restart=on-failure
RestartSec=5s
Environment=OLLAMA_HOST=127.0.0.1:11434
Environment=OLLAMA_ORIGINS=http://127.0.0.1

[Install]
WantedBy=multi-user.target
"""


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show collector health and recent observation counts."""
    if not DB_PATH.exists():
        typer.echo("Database not found. Run `nimbus init` first.", err=True)
        raise typer.Exit(1)

    conn = open_db()
    try:
        from .store.queries import get_stats
        raw = get_stats(conn)

        size_kb = raw["database_size_bytes"] // 1024
        unique = raw["unique_devices_last_hour"]
        total = raw["total_observations"]
        oldest = raw.get("oldest_ts")

        typer.echo(f"Database:          {DB_PATH}")
        typer.echo(f"Size:              {size_kb} KB")
        typer.echo(f"Total observations:{total:>10,}")
        typer.echo(f"Unique devices (1h):{unique:>9,}")

        if oldest:
            import time
            age_h = (time.time() - oldest) / 3600
            typer.echo(f"Oldest observation: {age_h:.1f}h ago")
        else:
            typer.echo("Oldest observation: no data yet")

        # Check whether the collector service is running
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "nimbus-collector"],
            check=False,
        )
        collector_state = "running" if result.returncode == 0 else "stopped"
        typer.echo(f"Collector service:  {collector_state}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# label
# ---------------------------------------------------------------------------

@app.command()
def label(
    mac_hash: str = typer.Argument(..., help="Hashed MAC address to label"),
    name: str = typer.Argument(..., help="Human-readable name to assign"),
) -> None:
    """Assign a friendly name to a device."""
    if not DB_PATH.exists():
        typer.echo("Database not found. Run `nimbus init` first.", err=True)
        raise typer.Exit(1)

    conn = open_db()
    try:
        from .store.queries import get_device, set_label
        device = get_device(conn, mac_hash)
        if device is None:
            typer.echo(f"Device {mac_hash!r} not found in database.", err=True)
            raise typer.Exit(1)

        set_label(conn, mac_hash, name)
        vendor = device.get("vendor_oui") or "unknown vendor"
        typer.echo(f"Labelled {mac_hash} ({vendor}) → {name!r}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# collect  (internal — called by the systemd unit)
# ---------------------------------------------------------------------------

@app.command(hidden=True)
def collect() -> None:
    """Run the Wi-Fi and BLE collector loops (called by the systemd unit)."""
    import asyncio as _asyncio

    from .privacy.optout import load_opt_out_prefixes
    from .collector.wifi import run_wifi_loop
    from .collector.ble import run_ble_loop
    from .store.retention import run_retention_loop

    conn = open_db()
    opt_out = load_opt_out_prefixes()

    config: dict = {}  # type: ignore[type-arg]
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open("rb") as f:
            config = tomllib.load(f)
    interface = config.get("wifi", {}).get("interface", "wlan0mon")
    retention_h = config.get("retention", {}).get("hours", 48)
    device_days = config.get("retention", {}).get("device_days", 30)

    async def _run() -> None:
        await asyncio.gather(
            run_wifi_loop(conn, interface=interface, opt_out_prefixes=opt_out),
            run_ble_loop(conn, opt_out_prefixes=opt_out),
            run_retention_loop(conn, observation_ttl_hours=retention_h, device_ttl_days=device_days),
        )

    typer.echo(f"Collector starting (interface={interface}, opt_out={len(opt_out)} entries)")
    asyncio.run(_run())


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------

@app.command()
def ask(
    prompt: str = typer.Argument(..., help="Natural-language question to ask the agent"),
) -> None:
    """Ask the local agent a question about nearby devices."""
    from .agent import ask as _ask
    answer = asyncio.run(_ask(prompt))
    typer.echo(answer)
