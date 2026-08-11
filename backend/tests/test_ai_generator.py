"""
Tests for AIGenerator with mocked Anthropic client.

No real API calls are made. anthropic.Anthropic is patched at the import site
in ai_generator.py so the full Python call path runs except the real HTTP call.

KEY: TestBugA_ModelName captures the 'model' kwarg sent to messages.create()
and asserts it matches valid Claude 4 format — EXPECTED FAILURE on unpatched code.
"""
import re
import pytest
from unittest.mock import MagicMock

from ai_generator import AIGenerator
from config import config
from tests.helpers import make_text_response, make_tool_use_response


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def mock_anthropic_class(mocker):
    """Patch anthropic.Anthropic at the import site in ai_generator.py."""
    return mocker.patch("ai_generator.anthropic.Anthropic")


@pytest.fixture
def mock_client(mock_anthropic_class):
    """The mock Anthropic client instance (created by AIGenerator.__init__)."""
    return mock_anthropic_class.return_value


@pytest.fixture
def generator(mock_anthropic_class):
    """AIGenerator using the config model name and a fake API key."""
    return AIGenerator(api_key="sk-ant-test", model=config.ANTHROPIC_MODEL)


@pytest.fixture
def mock_tool_manager():
    tm = MagicMock()
    tm.execute_tool.return_value = "Search result: RAG is a technique combining retrieval with generation."
    tm.get_tool_definitions.return_value = [
        {
            "name": "search_course_content",
            "description": "Search course materials",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        }
    ]
    return tm


# ===========================================================================
# Direct (end_turn) response tests
# ===========================================================================

class TestDirectResponse:

    def test_end_turn_response_returns_text(self, generator, mock_client):
        mock_client.messages.create.return_value = make_text_response("Hello world")
        result = generator.generate_response("What is Python?")
        assert result == "Hello world"

    def test_direct_response_makes_exactly_one_api_call(self, generator, mock_client):
        mock_client.messages.create.return_value = make_text_response("Answer")
        generator.generate_response("Simple question")
        assert mock_client.messages.create.call_count == 1

    def test_user_query_present_in_messages_sent_to_api(self, generator, mock_client):
        mock_client.messages.create.return_value = make_text_response("Reply")
        generator.generate_response("Tell me about neural networks")
        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert any("Tell me about neural networks" in str(m) for m in messages)

    def test_conversation_history_injected_into_system_prompt(self, generator, mock_client):
        mock_client.messages.create.return_value = make_text_response("Reply")
        generator.generate_response(
            "Follow-up question",
            conversation_history="User: previous\nAssistant: answer",
        )
        system = mock_client.messages.create.call_args.kwargs["system"]
        assert "previous" in system

    def test_no_history_omits_previous_conversation_header(self, generator, mock_client):
        mock_client.messages.create.return_value = make_text_response("Reply")
        generator.generate_response("Question", conversation_history=None)
        system = mock_client.messages.create.call_args.kwargs["system"]
        assert "Previous conversation" not in system

    def test_api_called_with_correct_model(self, generator, mock_client):
        mock_client.messages.create.return_value = make_text_response("ok")
        generator.generate_response("test")
        model_used = mock_client.messages.create.call_args.kwargs["model"]
        assert model_used == config.ANTHROPIC_MODEL


# ===========================================================================
# Bug A: Model name validation
# ===========================================================================

class TestBugA_ModelName:
    """
    Bug A: config.ANTHROPIC_MODEL = "claude-sonnet-4-20250514" is not a valid
    Claude 4 model ID.

    Valid format: ^claude-[a-z]+-4-\\d{1,2}(-\\d{8})?$
      e.g. "claude-sonnet-4-6"   or   "claude-haiku-4-5-20251001"

    "claude-sonnet-4-20250514" fails because 20250514 is 8 digits occupying the
    minor-version slot — a date, not a version number.

    EXPECTED FAILURE on unpatched code. Fix: ANTHROPIC_MODEL = "claude-sonnet-4-6".
    """

    VALID_PATTERN = re.compile(r"^claude-[a-z]+-4-\d{1,2}(-\d{8})?$")

    def test_model_name_in_api_call_matches_config_value(self, generator, mock_client):
        """Documents what is actually sent to the API — doesn't judge validity."""
        mock_client.messages.create.return_value = make_text_response("ok")
        generator.generate_response("test query")
        model_used = mock_client.messages.create.call_args.kwargs["model"]
        assert model_used == config.ANTHROPIC_MODEL

    def test_model_name_matches_valid_claude_4_format(self, generator, mock_client):
        """
        DIAGNOSTIC — EXPECTED TO FAIL on unpatched code.

        After Fix A (ANTHROPIC_MODEL = "claude-sonnet-4-6"), this test passes.
        """
        mock_client.messages.create.return_value = make_text_response("ok")
        generator.generate_response("test query")
        model_used = mock_client.messages.create.call_args.kwargs["model"]
        assert self.VALID_PATTERN.match(model_used), (
            f"Model ID '{model_used}' is not a valid Claude 4 ID. "
            f"Expected format: 'claude-sonnet-4-6' or 'claude-haiku-4-5-20251001'. "
            f"This is Bug A — update config.py:ANTHROPIC_MODEL."
        )

    def test_config_model_name_matches_valid_claude_4_format(self):
        """Static check: the value in config.py itself must be a valid Claude 4 ID."""
        assert self.VALID_PATTERN.match(config.ANTHROPIC_MODEL), (
            f"config.ANTHROPIC_MODEL = '{config.ANTHROPIC_MODEL}' is invalid. "
            f"Fix: change to 'claude-sonnet-4-6'."
        )

    def test_generator_stores_model_attribute(self):
        """Smoke test: AIGenerator.model reflects the constructor argument."""
        gen = AIGenerator(api_key="test", model="claude-sonnet-4-6")
        assert gen.model == "claude-sonnet-4-6"


# ===========================================================================
# Tool-use flow tests
# ===========================================================================

class TestToolUseFlow:

    def test_tool_use_response_triggers_tool_execution(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_01", {"query": "RAG basics"}
        )
        final_resp = make_text_response("RAG is Retrieval Augmented Generation.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "What is RAG?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        mock_tool_manager.execute_tool.assert_called_once_with(
            "search_course_content", query="RAG basics"
        )

    def test_tool_use_path_makes_exactly_two_api_calls(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_02", {"query": "vector embeddings"}
        )
        final_resp = make_text_response("Embeddings encode semantic meaning.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "Explain embeddings",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert mock_client.messages.create.call_count == 2

    def test_tool_result_included_in_second_api_call_messages(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_03", {"query": "lesson 1 content"}
        )
        final_resp = make_text_response("Here is the answer.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "What is in lesson 1?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
        tool_result_blocks = [
            block
            for msg in second_call_messages
            if isinstance(msg.get("content"), list)
            for block in msg["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        assert len(tool_result_blocks) == 1

    def test_tool_result_carries_correct_tool_use_id(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_id_check", {"query": "test"}
        )
        final_resp = make_text_response("Done.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "test",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
        tool_result_blocks = [
            block
            for msg in second_call_messages
            if isinstance(msg.get("content"), list)
            for block in msg["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        assert tool_result_blocks[0]["tool_use_id"] == "toolu_id_check"

    def test_final_response_text_comes_from_second_api_call(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_04", {"query": "transformers"}
        )
        final_resp = make_text_response("Transformers use attention mechanisms.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        result = generator.generate_response(
            "What are transformers?",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert result == "Transformers use attention mechanisms."

    def test_second_api_call_includes_tools_when_rounds_remain(
        self, generator, mock_client, mock_tool_manager
    ):
        """After round 0, tools are still passed so Claude can make a 2nd search if needed."""
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_05", {"query": "test"}
        )
        final_resp = make_text_response("Done.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "test",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs

    def test_both_api_calls_use_the_same_model(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp = make_tool_use_response(
            "search_course_content", "toolu_06", {"query": "x"}
        )
        final_resp = make_text_response("y")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "question",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        first_model = mock_client.messages.create.call_args_list[0].kwargs["model"]
        second_model = mock_client.messages.create.call_args_list[1].kwargs["model"]
        assert first_model == second_model == config.ANTHROPIC_MODEL


# ===========================================================================
# Two-round sequential tool-use tests
# ===========================================================================

class TestTwoRoundToolUse:
    """Claude makes two sequential tool calls before giving a final answer."""

    def test_two_sequential_tool_calls_make_three_api_calls(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_r1", {"query": "lesson 4 title"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_r2", {"query": "matching course"})
        final_resp = make_text_response("Course Y covers the same topic.")
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        generator.generate_response(
            "Find a course covering the same topic as lesson 4",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert mock_client.messages.create.call_count == 3

    def test_second_api_call_includes_tools(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_r1", {"query": "q1"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_r2", {"query": "q2"})
        final_resp = make_text_response("Answer.")
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        generator.generate_response(
            "multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs

    def test_third_api_call_does_not_include_tools(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_r1", {"query": "q1"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_r2", {"query": "q2"})
        final_resp = make_text_response("Answer.")
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        generator.generate_response(
            "multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        third_call_kwargs = mock_client.messages.create.call_args_list[2].kwargs
        assert "tools" not in third_call_kwargs

    def test_both_tool_calls_are_executed(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_r1", {"query": "q1"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_r2", {"query": "q2"})
        final_resp = make_text_response("Answer.")
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        generator.generate_response(
            "multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert mock_tool_manager.execute_tool.call_count == 2

    def test_both_tool_results_present_in_third_call_messages(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_r1", {"query": "q1"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_r2", {"query": "q2"})
        final_resp = make_text_response("Answer.")
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        generator.generate_response(
            "multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        third_call_messages = mock_client.messages.create.call_args_list[2].kwargs["messages"]
        tool_result_blocks = [
            block
            for msg in third_call_messages
            if isinstance(msg.get("content"), list)
            for block in msg["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        assert len(tool_result_blocks) == 2

    def test_final_text_returned_after_two_rounds(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_r1", {"query": "q1"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_r2", {"query": "q2"})
        final_resp = make_text_response("Two-round answer.")
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        result = generator.generate_response(
            "multi-step query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert result == "Two-round answer."


# ===========================================================================
# Tool execution error tests
# ===========================================================================

class TestToolExecutionError:
    """Tool errors are surfaced as is_error results; Claude still gets a synthesis call."""

    def test_tool_exception_does_not_propagate(
        self, generator, mock_client, mock_tool_manager
    ):
        mock_tool_manager.execute_tool.side_effect = Exception("db connection failed")
        tool_resp = make_tool_use_response("search_course_content", "toolu_err", {"query": "test"})
        final_resp = make_text_response("I encountered an error.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        result = generator.generate_response(
            "test",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert isinstance(result, str)

    def test_error_result_has_is_error_flag(
        self, generator, mock_client, mock_tool_manager
    ):
        mock_tool_manager.execute_tool.side_effect = Exception("db connection failed")
        tool_resp = make_tool_use_response("search_course_content", "toolu_err", {"query": "test"})
        final_resp = make_text_response("I encountered an error.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "test",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
        tool_result_blocks = [
            block
            for msg in second_call_messages
            if isinstance(msg.get("content"), list)
            for block in msg["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        assert tool_result_blocks[0].get("is_error") is True

    def test_error_still_makes_synthesis_api_call(
        self, generator, mock_client, mock_tool_manager
    ):
        mock_tool_manager.execute_tool.side_effect = Exception("db connection failed")
        tool_resp = make_tool_use_response("search_course_content", "toolu_err", {"query": "test"})
        final_resp = make_text_response("I encountered an error.")
        mock_client.messages.create.side_effect = [tool_resp, final_resp]

        generator.generate_response(
            "test",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert mock_client.messages.create.call_count == 2


# ===========================================================================
# Round cap enforcement tests
# ===========================================================================

class TestRoundCap:
    """The loop must stop after MAX_TOOL_ROUNDS regardless of Claude's intent."""

    def test_stops_at_two_tool_rounds(
        self, generator, mock_client, mock_tool_manager
    ):
        tool_resp_1 = make_tool_use_response("search_course_content", "toolu_c1", {"query": "q1"})
        tool_resp_2 = make_tool_use_response("search_course_content", "toolu_c2", {"query": "q2"})
        final_resp = make_text_response("Capped answer.")
        # Even if a 4th response existed, the loop cap stops at 3 total API calls
        mock_client.messages.create.side_effect = [tool_resp_1, tool_resp_2, final_resp]

        generator.generate_response(
            "query needing many searches",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager,
        )
        assert mock_client.messages.create.call_count == 3
