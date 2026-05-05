"""MCP client + Ollama tool-calling loop.

Spawns the MCP server as a subprocess, connects to Ollama running locally,
and runs a turn-based tool-calling loop until the model returns a final answer.

Usage (via CLI):
    nimbus ask "who is here?"
"""

import asyncio

MODEL = "llama3.2:3b"
OLLAMA_HOST = "http://127.0.0.1:11434"


async def ask(prompt: str) -> str:
    """Run one user prompt through the full agent loop and return the answer."""
    raise NotImplementedError


if __name__ == "__main__":
    import sys
    prompt = " ".join(sys.argv[1:]) or "who is here?"
    print(asyncio.run(ask(prompt)))
