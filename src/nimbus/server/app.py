"""MCP server entry point.

Run via the agent script (spawned as a subprocess) or directly for testing:
    python -m nimbus.server.app
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server

from ..store.schema import open_db
from . import resources, tools

app = Server("nimbus")


def register_tools() -> None:
    raise NotImplementedError


def register_resources() -> None:
    raise NotImplementedError


async def main() -> None:
    conn = open_db()
    register_tools()
    register_resources()
    async with stdio_server() as streams:
        await app.run(*streams, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
