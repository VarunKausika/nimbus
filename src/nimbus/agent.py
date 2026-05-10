"""MCP client + Ollama tool-calling loop.

Spawns the MCP server as a subprocess (stdio transport), connects to a local
Ollama instance, and iterates tool calls until the model produces a final
text answer with no further tool calls.

Usage (via CLI):
    nimbus ask "who is here?"
"""

import asyncio
import sys
from typing import Any

import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ollama import AsyncClient

MODEL = "llama3.2:3b"
OLLAMA_HOST = "http://127.0.0.1:11434"
MAX_TOOL_ITERATIONS = 10

_SYSTEM = """\
You are a local ambient presence assistant running on a Raspberry Pi.
You have access to real-time Wi-Fi and BLE sensor tools. All data is processed
entirely on-device — nothing leaves this machine.

Rules:
- Always call a tool to get current data before answering presence questions.
- Never guess who or what is present; use the tools.
- Be concise: report device counts, vendor names, and labels where available.
- If a response contains a mac_hash, call identify() to retrieve more detail.
- Prefer who_is_here() for general questions; use scan_wifi() or scan_ble()
  only when the user explicitly wants a fresh active scan.\
"""


def _to_ollama_tool(tool: mcp_types.Tool) -> dict[str, Any]:
    """Convert an MCP Tool definition to Ollama's function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def ask(prompt: str) -> str:
    """Run one user prompt through the full agent loop and return the answer."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nimbus.server.app"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            mcp_tools = (await session.list_tools()).tools
            ollama_tools = [_to_ollama_tool(t) for t in mcp_tools]

            messages: list[Any] = [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ]

            client = AsyncClient(host=OLLAMA_HOST)

            for _ in range(MAX_TOOL_ITERATIONS):
                response = await client.chat(
                    model=MODEL,
                    messages=messages,
                    tools=ollama_tools,
                )

                msg = response.message

                # No tool calls — model has reached a final answer.
                if not msg.tool_calls:
                    return msg.content or ""

                # Preserve the assistant turn (including tool_calls) in history.
                messages.append(msg)

                # Execute each requested tool call against the MCP server.
                for call in msg.tool_calls:
                    tool_name = call.function.name
                    tool_args = dict(call.function.arguments)

                    try:
                        result = await session.call_tool(tool_name, tool_args)
                        if result.isError:
                            tool_content = (
                                f"Error: {result.content[0].text}"
                                if result.content
                                else "Error: unknown tool error"
                            )
                        else:
                            tool_content = result.content[0].text if result.content else ""
                    except Exception as exc:
                        tool_content = f"Tool call failed: {exc}"

                    messages.append({"role": "tool", "content": tool_content})

            # Max iterations reached — ask the model to wrap up with what it has.
            messages.append(
                {"role": "user", "content": "Summarise what you have found so far."}
            )
            final = await client.chat(model=MODEL, messages=messages)
            return final.message.content or ""


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "who is here?"
    print(asyncio.run(ask(prompt)))
