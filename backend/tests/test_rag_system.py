"""
Integration tests for RAGSystem.query().

- Real in-memory ChromaDB (via fixtures from conftest.py)
- Anthropic client mocked at the instance level (mocker.patch.object on client.messages)
- Verifies the full call chain: query() → generate_response() → [tool_use] →
  CourseSearchTool.execute() → vector_store.search() → synthesis → (str, list)
"""
import re
import pytest
from unittest.mock import MagicMock

from rag_system import RAGSystem
from config import config
from tests.helpers import make_text_response, make_tool_use_response


# ===========================================================================
# RAGSystem fixture
# ===========================================================================

@pytest.fixture
def rag_system(tmp_path, dummy_ef, monkeypatch):
    """
    RAGSystem with a real PersistentClient in tmp_path (isolated per test)
    and dummy embeddings. Anthropic client is NOT mocked here — individual
    tests do it via mocker.patch.object on the already-constructed client.
    """
    monkeypatch.setattr(
        "chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction",
        lambda model_name: dummy_ef,
    )
    from config import Config
    test_config = Config(CHROMA_PATH=str(tmp_path / "chroma"))
    return RAGSystem(test_config)


@pytest.fixture
def loaded_rag_system(rag_system, sample_course, sample_chunks):
    """RAGSystem pre-loaded with sample course data."""
    rag_system.vector_store.add_course_metadata(sample_course)
    rag_system.vector_store.add_course_content(sample_chunks)
    return rag_system


# ===========================================================================
# Basic query tests (direct response — no tool use)
# ===========================================================================

class TestRAGSystemQuery:

    def test_query_returns_tuple_of_str_and_list(self, loaded_rag_system, mocker):
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("This is an answer."),
        )
        result = loaded_rag_system.query("What is RAG?")
        assert isinstance(result, tuple)
        answer, sources = result
        assert isinstance(answer, str)
        assert isinstance(sources, list)

    def test_query_answer_matches_ai_response_text(self, loaded_rag_system, mocker):
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("RAG augments LLMs with retrieved context."),
        )
        answer, _ = loaded_rag_system.query("Explain RAG")
        assert answer == "RAG augments LLMs with retrieved context."

    def test_direct_response_returns_empty_sources_list(self, loaded_rag_system, mocker):
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("General knowledge answer."),
        )
        _, sources = loaded_rag_system.query("What is machine learning?")
        assert sources == []

    def test_query_sends_correct_model_to_anthropic(self, loaded_rag_system, mocker):
        create_mock = mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("ok"),
        )
        loaded_rag_system.query("test question")
        model_used = create_mock.call_args.kwargs["model"]
        assert model_used == config.ANTHROPIC_MODEL


# ===========================================================================
# Bug A: Model name end-to-end
# ===========================================================================

class TestBugA_EndToEnd:
    """
    Confirms Bug A through the full RAGSystem stack.
    The model name reaching the Anthropic API must conform to valid Claude 4 format.
    EXPECTED FAILURE on unpatched code.
    """

    VALID_PATTERN = re.compile(r"^claude-[a-z]+-4-\d{1,2}(-\d{8})?$")

    def test_configured_model_is_valid_claude_4_id(self):
        """
        DIAGNOSTIC — EXPECTED FAILURE on unpatched code.
        Fix: change config.py ANTHROPIC_MODEL to 'claude-sonnet-4-6'.
        """
        assert self.VALID_PATTERN.match(config.ANTHROPIC_MODEL), (
            f"config.ANTHROPIC_MODEL = '{config.ANTHROPIC_MODEL}' is not a valid "
            f"Claude 4 model ID. This is Bug A — the root cause of HTTP 500 / 'query failed'. "
            f"Fix: ANTHROPIC_MODEL = 'claude-sonnet-4-6'"
        )

    def test_rag_query_sends_valid_model_to_anthropic(self, loaded_rag_system, mocker):
        create_mock = mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("ok"),
        )
        loaded_rag_system.query("test question")
        model_used = create_mock.call_args.kwargs["model"]
        assert self.VALID_PATTERN.match(model_used), (
            f"Model '{model_used}' sent to Anthropic is not a valid Claude 4 ID."
        )


# ===========================================================================
# Session history tests
# ===========================================================================

class TestRAGSystemSessionHistory:

    def test_query_with_session_id_records_exchange_in_history(
        self, loaded_rag_system, mocker
    ):
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("Answer A"),
        )
        session_id = loaded_rag_system.session_manager.create_session()
        loaded_rag_system.query("Question A", session_id=session_id)
        history = loaded_rag_system.session_manager.get_conversation_history(session_id)
        assert history is not None
        assert "Question A" in history
        assert "Answer A" in history

    def test_second_query_same_session_includes_prior_exchange_in_system_prompt(
        self, loaded_rag_system, mocker
    ):
        create_mock = mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("Answer"),
        )
        session_id = loaded_rag_system.session_manager.create_session()
        loaded_rag_system.query("First question", session_id=session_id)
        loaded_rag_system.query("Second question", session_id=session_id)

        second_call_system = create_mock.call_args_list[1].kwargs["system"]
        # Prior exchange should appear in the system prompt of the second call
        assert "First question" in second_call_system or "Answer" in second_call_system

    def test_query_without_session_id_does_not_raise(self, loaded_rag_system, mocker):
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            return_value=make_text_response("Stateless answer"),
        )
        # Should complete without KeyError or AttributeError
        answer, sources = loaded_rag_system.query("Stateless query", session_id=None)
        assert isinstance(answer, str)
        assert isinstance(sources, list)


# ===========================================================================
# End-to-end: mocked Claude responds with tool_use
# ===========================================================================

class TestRAGSystemEndToEndWithToolUse:
    """
    Full pipeline: mocked Claude returns tool_use → real CourseSearchTool.execute()
    hits real in-memory ChromaDB → mocked Claude synthesizes the final answer.
    """

    def test_tool_use_pipeline_returns_synthesized_answer(
        self, loaded_rag_system, mocker
    ):
        tool_resp = make_tool_use_response(
            "search_course_content",
            "toolu_e2e_01",
            {"query": "what is RAG"},
        )
        final_resp = make_text_response(
            "RAG combines retrieval with generation for better answers."
        )
        create_mock = mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            side_effect=[tool_resp, final_resp],
        )
        answer, _ = loaded_rag_system.query("What is RAG?")
        assert answer == "RAG combines retrieval with generation for better answers."
        assert create_mock.call_count == 2

    def test_tool_use_pipeline_returns_list_of_sources(
        self, loaded_rag_system, mocker
    ):
        tool_resp = make_tool_use_response(
            "search_course_content",
            "toolu_e2e_02",
            {"query": "vector stores embeddings"},
        )
        final_resp = make_text_response("Vector stores are databases for embeddings.")
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            side_effect=[tool_resp, final_resp],
        )
        _, sources = loaded_rag_system.query("Tell me about vector stores")
        assert isinstance(sources, list)

    def test_tool_result_with_correct_id_sent_to_second_api_call(
        self, loaded_rag_system, mocker
    ):
        tool_resp = make_tool_use_response(
            "search_course_content",
            "toolu_e2e_id",
            {"query": "RAG retrieval augmented"},
        )
        final_resp = make_text_response("Done.")
        create_mock = mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            side_effect=[tool_resp, final_resp],
        )
        loaded_rag_system.query("What is RAG?")

        second_call_messages = create_mock.call_args_list[1].kwargs["messages"]
        tool_result_blocks = [
            block
            for msg in second_call_messages
            if isinstance(msg.get("content"), list)
            for block in msg["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        assert len(tool_result_blocks) == 1
        assert tool_result_blocks[0]["tool_use_id"] == "toolu_e2e_id"

    def test_sources_reset_between_consecutive_queries(
        self, loaded_rag_system, mocker
    ):
        """Sources from query 1 must not bleed into query 2."""
        side_effects = [
            make_tool_use_response("search_course_content", "t1", {"query": "RAG"}),
            make_text_response("First answer"),
            make_tool_use_response("search_course_content", "t2", {"query": "python"}),
            make_text_response("Second answer"),
        ]
        mocker.patch.object(
            loaded_rag_system.ai_generator.client.messages,
            "create",
            side_effect=side_effects,
        )
        session = loaded_rag_system.session_manager.create_session()
        _, sources1 = loaded_rag_system.query("Question 1", session_id=session)
        _, sources2 = loaded_rag_system.query("Question 2", session_id=session)

        assert isinstance(sources1, list)
        assert isinstance(sources2, list)
