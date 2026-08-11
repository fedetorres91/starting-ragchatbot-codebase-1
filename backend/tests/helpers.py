"""Shared test helper functions for building mock Anthropic API responses."""
from unittest.mock import MagicMock


def make_text_response(text: str) -> MagicMock:
    """Mock Anthropic Message with stop_reason='end_turn'."""
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [content_block]
    return response


def make_tool_use_response(tool_name: str, tool_id: str, tool_input: dict) -> MagicMock:
    """Mock Anthropic Message with stop_reason='tool_use'."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id = tool_id
    tool_block.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    return response
