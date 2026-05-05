"""Agent loop tests using mocked Ollama + MCP server."""

import pytest

from nimbus.agent import ask


class TestAgentLoop:
    async def test_single_tool_call_cycle(self) -> None:
        """Model picks one tool, result is fed back, model gives final answer."""
        pytest.skip("not implemented")

    async def test_multi_tool_call_cycle(self) -> None:
        """Model chains multiple tool calls before returning an answer."""
        pytest.skip("not implemented")

    async def test_no_tool_call_returns_direct_answer(self) -> None:
        """Model answers directly without calling any tool."""
        pytest.skip("not implemented")
