"""Agent loop tests — Ollama and the MCP stdio transport are fully mocked."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nimbus.agent import ask


def _make_tool_mock(name: str = "stats") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = f"Mock tool: {name}"
    tool.inputSchema = {"type": "object", "properties": {}}
    return tool


def _make_ollama_response(
    content: str,
    tool_calls: list[MagicMock] | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls
    response = MagicMock()
    response.message = msg
    return response


def _make_tool_call(name: str, arguments: dict) -> MagicMock:  # type: ignore[type-arg]
    call = MagicMock()
    call.function.name = name
    call.function.arguments = arguments
    return call


def _patch_transport(p_stdio: MagicMock, p_session: MagicMock, mock_session: AsyncMock) -> None:
    p_stdio.return_value.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
    p_stdio.return_value.__aexit__ = AsyncMock(return_value=False)
    p_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    p_session.return_value.__aexit__ = AsyncMock(return_value=False)


class TestAgentLoop:
    def test_no_tool_call_returns_direct_answer(self) -> None:
        """Model answers without calling any tool — single Ollama round-trip."""
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=[])

        mock_ollama = AsyncMock()
        mock_ollama.chat.return_value = _make_ollama_response("42 devices nearby.")

        with (
            patch("nimbus.agent.stdio_client") as p_stdio,
            patch("nimbus.agent.ClientSession") as p_session,
            patch("nimbus.agent.AsyncClient", return_value=mock_ollama),
        ):
            _patch_transport(p_stdio, p_session, mock_session)
            result = asyncio.run(ask("how many devices are nearby?"))

        assert result == "42 devices nearby."
        mock_ollama.chat.assert_called_once()
        mock_session.call_tool.assert_not_called()

    def test_single_tool_call_cycle(self) -> None:
        """Model picks one tool, receives the result, then gives a final answer."""
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=[_make_tool_mock("stats")])
        mock_session.call_tool.return_value = MagicMock(
            isError=False,
            content=[MagicMock(text='{"frames_per_second": 2.5}')],
        )

        mock_ollama = AsyncMock()
        mock_ollama.chat.side_effect = [
            _make_ollama_response("", tool_calls=[_make_tool_call("stats", {})]),
            _make_ollama_response("The sensor is running at 2.5 frames per second."),
        ]

        with (
            patch("nimbus.agent.stdio_client") as p_stdio,
            patch("nimbus.agent.ClientSession") as p_session,
            patch("nimbus.agent.AsyncClient", return_value=mock_ollama),
        ):
            _patch_transport(p_stdio, p_session, mock_session)
            result = asyncio.run(ask("is the sensor working?"))

        assert result == "The sensor is running at 2.5 frames per second."
        assert mock_ollama.chat.call_count == 2
        mock_session.call_tool.assert_called_once_with("stats", {})

    def test_multi_tool_call_cycle(self) -> None:
        """Model chains two tool calls before returning a final answer."""
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(
            tools=[_make_tool_mock("stats"), _make_tool_mock("who_is_here")]
        )
        mock_session.call_tool.return_value = MagicMock(
            isError=False,
            content=[MagicMock(text="{}")],
        )

        mock_ollama = AsyncMock()
        mock_ollama.chat.side_effect = [
            _make_ollama_response("", tool_calls=[_make_tool_call("stats", {})]),
            _make_ollama_response("", tool_calls=[_make_tool_call("who_is_here", {"since": "5m"})]),
            _make_ollama_response("Sensor healthy. Three devices nearby."),
        ]

        with (
            patch("nimbus.agent.stdio_client") as p_stdio,
            patch("nimbus.agent.ClientSession") as p_session,
            patch("nimbus.agent.AsyncClient", return_value=mock_ollama),
        ):
            _patch_transport(p_stdio, p_session, mock_session)
            result = asyncio.run(ask("is the sensor working and who is here?"))

        assert result == "Sensor healthy. Three devices nearby."
        assert mock_ollama.chat.call_count == 3
        assert mock_session.call_tool.call_count == 2

    def test_failed_tool_call_surfaces_error_to_model(self) -> None:
        """A tool error is returned as text so the model can handle it gracefully."""
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = MagicMock(tools=[_make_tool_mock("stats")])
        mock_session.call_tool.side_effect = RuntimeError("collector not running")

        mock_ollama = AsyncMock()
        mock_ollama.chat.side_effect = [
            _make_ollama_response("", tool_calls=[_make_tool_call("stats", {})]),
            _make_ollama_response("The collector does not appear to be running."),
        ]

        with (
            patch("nimbus.agent.stdio_client") as p_stdio,
            patch("nimbus.agent.ClientSession") as p_session,
            patch("nimbus.agent.AsyncClient", return_value=mock_ollama),
        ):
            _patch_transport(p_stdio, p_session, mock_session)
            result = asyncio.run(ask("is the sensor working?"))

        assert "collector" in result.lower()
        second_call_messages = mock_ollama.chat.call_args_list[1][1]["messages"]
        tool_msg = next(m for m in second_call_messages if m.get("role") == "tool")  # type: ignore[union-attr]
        assert "Tool call failed" in tool_msg["content"]