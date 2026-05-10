"""MCP server entry point.

Registers all 9 tools and 3 resources against the MCP Server instance, then
runs the stdio transport loop. Spawned as a subprocess by the agent script.

    python -m nimbus.server.app
"""

import asyncio
import sqlite3
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl

from ..store.schema import open_db
from . import resources, tools

app = Server("nimbus")

# Set by main() before the server starts accepting requests.
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("DB connection not initialised — call main() first.")
    return _conn


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="who_is_here",
            description=(
                "Returns currently-present devices, deduplicated across Wi-Fi and BLE. "
                "Filters out devices with fewer than min_observations hits to suppress "
                "noise from randomised MACs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "Lookback window — relative ('5m', '1h', '2d') or ISO 8601.",
                        "default": "5m",
                    },
                    "min_observations": {
                        "type": "integer",
                        "description": "Minimum observation count to include a device.",
                        "default": 3,
                    },
                },
            },
        ),
        types.Tool(
            name="scan_wifi",
            description=(
                "Triggers a short fresh 802.11 management frame scan and returns "
                "access points and probe-request traffic seen during the window."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "duration_s": {
                        "type": "integer",
                        "description": "Scan duration in seconds.",
                        "default": 10,
                    },
                },
            },
        ),
        types.Tool(
            name="scan_ble",
            description=(
                "Triggers a short fresh BLE advertisement scan. Never connects or pairs. "
                "Returns advertising devices with name, service UUIDs, and RSSI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "duration_s": {
                        "type": "integer",
                        "description": "Scan duration in seconds.",
                        "default": 10,
                    },
                },
            },
        ),
        types.Tool(
            name="identify",
            description=(
                "Returns everything known about a specific device: vendor, device class, "
                "probed SSIDs (Wi-Fi), advertised services (BLE), observed channels, "
                "observation count, first/last seen, and any user-assigned label."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mac_or_hash": {
                        "type": "string",
                        "description": "16-char hashed MAC address returned by other tools.",
                    },
                },
                "required": ["mac_or_hash"],
            },
        ),
        types.Tool(
            name="presence_timeline",
            description=(
                "Returns a bucketed timeline showing when a device was observed. "
                "Use this to answer questions like 'does this device show up every morning?'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mac_or_hash": {
                        "type": "string",
                        "description": "16-char hashed MAC address.",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Lookback window in hours.",
                        "default": 24,
                    },
                    "bucket_minutes": {
                        "type": "integer",
                        "description": "Bucket size in minutes.",
                        "default": 15,
                    },
                },
                "required": ["mac_or_hash"],
            },
        ),
        types.Tool(
            name="find_regulars",
            description=(
                "Returns devices seen on at least min_days_seen distinct days in the "
                "lookback window — the 'who are my regular neighbours' query."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Lookback window in hours (default 168 = 1 week).",
                        "default": 168,
                    },
                    "min_days_seen": {
                        "type": "integer",
                        "description": "Minimum number of distinct days a device must appear.",
                        "default": 3,
                    },
                },
            },
        ),
        types.Tool(
            name="diff_presence",
            description=(
                "Returns {new, departed, lingering} device sets relative to a prior "
                "timestamp. Useful for 'what changed since I last asked' loops."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "Reference timestamp — relative ('1h') or ISO 8601.",
                    },
                },
                "required": ["since"],
            },
        ),
        types.Tool(
            name="label",
            description="Attach a human-readable name to a device, persisted in the database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mac_or_hash": {
                        "type": "string",
                        "description": "16-char hashed MAC address.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable label to assign (e.g. 'roommate phone').",
                    },
                },
                "required": ["mac_or_hash", "name"],
            },
        ),
        types.Tool(
            name="stats",
            description=(
                "Returns collector health: frames per second, unique devices last hour, "
                "database size, oldest retained observation, and approximate uptime."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    conn = _get_conn()
    args: dict[str, Any] = arguments or {}

    match name:
        case "who_is_here":
            result = tools.who_is_here(conn, **args)
        case "scan_wifi":
            result = await tools.scan_wifi(conn, **args)
        case "scan_ble":
            result = await tools.scan_ble(conn, **args)
        case "identify":
            result = tools.identify(conn, **args)
        case "presence_timeline":
            result = tools.presence_timeline(conn, **args)
        case "find_regulars":
            result = tools.find_regulars(conn, **args)
        case "diff_presence":
            result = tools.diff_presence(conn, **args)
        case "label":
            tools.label(conn, **args)
            return [types.TextContent(type="text", text="Label saved.")]
        case "stats":
            result = tools.stats(conn)
        case _:
            raise ValueError(f"Unknown tool: {name!r}")

    return [types.TextContent(type="text", text=result.model_dump_json())]


# ---------------------------------------------------------------------------
# Resource registry
# ---------------------------------------------------------------------------

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri=AnyUrl("presence://current"),
            name="Current Presence",
            description="Point-in-time who_is_here snapshot, refreshed every 30 seconds.",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("presence://config"),
            name="Configuration",
            description="Active nimbus configuration. Never exposes the salt or raw opt-out list.",
            mimeType="application/json",
        ),
        types.Resource(
            uri=AnyUrl("presence://schema"),
            name="Tool Schema",
            description="Full JSON Schema for every tool result type.",
            mimeType="application/json",
        ),
    ]


@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    conn = _get_conn()
    match str(uri):
        case "presence://current":
            return resources.presence_current(conn)
        case "presence://config":
            return resources.presence_config()
        case "presence://schema":
            return resources.presence_schema()
        case _:
            raise ValueError(f"Unknown resource URI: {uri!r}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    global _conn
    _conn = open_db()

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="nimbus",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
