"""
Tests for CourseSearchTool and ToolManager.

Uses real in-memory ChromaDB to catch genuine ChromaDB validation errors.
The SentenceTransformer model is replaced with DummyEmbeddingFunction.
"""
import pytest
from search_tools import CourseSearchTool, ToolManager


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def loaded_store(vector_store, sample_course, sample_chunks):
    """VectorStore pre-loaded with one course and two chunks."""
    vector_store.add_course_metadata(sample_course)
    vector_store.add_course_content(sample_chunks)
    return vector_store


@pytest.fixture
def search_tool(loaded_store):
    return CourseSearchTool(loaded_store)


@pytest.fixture
def tool_manager(search_tool):
    tm = ToolManager()
    tm.register_tool(search_tool)
    return tm


# ===========================================================================
# Happy-path tests
# ===========================================================================

class TestCourseSearchToolHappyPath:

    def test_basic_search_returns_non_empty_string(self, search_tool):
        result = search_tool.execute(query="what is RAG")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_basic_search_contains_course_header(self, search_tool):
        result = search_tool.execute(query="what is RAG retrieval")
        assert "[Introduction to RAG" in result

    def test_basic_search_contains_lesson_header(self, search_tool):
        result = search_tool.execute(query="vector stores semantic search")
        assert "Lesson" in result

    def test_search_with_valid_course_name_filter(self, search_tool):
        result = search_tool.execute(
            query="RAG retrieval",
            course_name="Introduction to RAG",
        )
        assert isinstance(result, str)
        assert "No course found" not in result

    def test_search_with_invalid_course_name_on_empty_catalog(self, vector_store):
        """Empty catalog → _resolve_course_name returns None → 'No course found' string."""
        tool = CourseSearchTool(vector_store)
        result = tool.execute(query="anything", course_name="Nonexistent Course XYZ")
        assert isinstance(result, str)
        assert "No course found" in result

    def test_search_with_lesson_number_filter(self, search_tool):
        result = search_tool.execute(
            query="retrieval augmented generation",
            course_name="Introduction to RAG",
            lesson_number=1,
        )
        assert isinstance(result, str)

    def test_last_sources_populated_after_successful_search(self, search_tool):
        search_tool.execute(query="RAG retrieval generation")
        assert len(search_tool.last_sources) > 0
        source = search_tool.last_sources[0]
        assert "label" in source
        assert "url" in source

    def test_last_sources_contain_course_label(self, search_tool):
        search_tool.execute(query="RAG retrieval")
        labels = [s["label"] for s in search_tool.last_sources]
        assert any("Introduction to RAG" in label for label in labels)


# ===========================================================================
# Empty collection
# ===========================================================================

class TestEmptyCollection:

    def test_empty_collection_search_does_not_crash(self, vector_store):
        """Searching an empty content collection must not raise — returns graceful string."""
        tool = CourseSearchTool(vector_store)
        result = tool.execute(query="anything")
        assert isinstance(result, str)
        assert "No relevant content found" in result

    def test_empty_collection_with_course_filter_returns_error_string(self, vector_store):
        """Filtering by course when catalog is empty returns 'No course found' string."""
        tool = CourseSearchTool(vector_store)
        result = tool.execute(query="anything", course_name="Fake Course")
        assert isinstance(result, str)
        assert "No course found" in result


# ===========================================================================
# Bug B: None lesson_number causes ChromaDB ValueError
# ===========================================================================

class TestBugB_NoneMetadataValue:
    """
    Bug B (fixed): ChromaDB 1.0.15 rejects None metadata values.
    Fix: lesson_number=None is stored as -1 (sentinel int) in ChromaDB.

    These tests verify the fix works correctly — add succeeds and -1 is stored.
    """

    def test_add_chunk_with_none_lesson_number_succeeds(self, vector_store, chunk_with_none_lesson):
        """After Fix B, adding a chunk with lesson_number=None must not raise."""
        vector_store.add_course_content([chunk_with_none_lesson])

    def test_none_lesson_number_stored_as_minus_one(self, vector_store, chunk_with_none_lesson):
        """The -1 sentinel is retrievable from ChromaDB metadata."""
        vector_store.add_course_content([chunk_with_none_lesson])
        result = vector_store.course_content.get(
            ids=[f"Introduction_to_RAG_99"]
        )
        assert result["metadatas"][0]["lesson_number"] == -1

    def test_none_lesson_chunk_mixed_with_valid_chunks_succeeds(
        self, vector_store, sample_course, sample_chunks, chunk_with_none_lesson
    ):
        """Batch of valid + None-lesson chunks all succeed after Fix B."""
        vector_store.add_course_metadata(sample_course)
        vector_store.add_course_content(sample_chunks + [chunk_with_none_lesson])


# ===========================================================================
# Bug C: n_results > filtered collection size
# ===========================================================================

class TestBugC_NResultsExceedsCollectionSize:
    """
    Bug C (fixed): n_results is now clamped to the filtered collection size
    before querying ChromaDB, so InvalidArgumentError no longer occurs.
    """

    def test_filtered_query_returns_results_when_fewer_than_limit(
        self, vector_store, sample_course, sample_chunks
    ):
        """After Fix C, a filtered query with 2 chunks and n_results=5 returns results."""
        vector_store.add_course_metadata(sample_course)
        vector_store.add_course_content(sample_chunks)

        results = vector_store.search(
            query="RAG retrieval augmented generation",
            course_name="Introduction to RAG",
        )

        assert results.error is None
        assert len(results.documents) > 0

    def test_unfiltered_query_with_fewer_chunks_than_limit_returns_results(
        self, vector_store, sample_course, sample_chunks
    ):
        """Unfiltered search also works when collection has fewer docs than n_results."""
        vector_store.add_course_metadata(sample_course)
        vector_store.add_course_content(sample_chunks)

        results = vector_store.search(query="RAG vector stores")
        assert results is not None
        assert isinstance(results.documents, list)
        assert len(results.documents) > 0

    def test_lesson_filter_with_single_chunk_returns_that_chunk(
        self, vector_store, sample_course, sample_chunks
    ):
        """Filtering by lesson 1 returns the one chunk in lesson 1."""
        vector_store.add_course_metadata(sample_course)
        vector_store.add_course_content(sample_chunks)

        results = vector_store.search(
            query="retrieval augmented",
            course_name="Introduction to RAG",
            lesson_number=1,
        )
        assert results.error is None
        assert len(results.documents) == 1
        assert all(m["lesson_number"] == 1 for m in results.metadata)


# ===========================================================================
# ToolManager tests
# ===========================================================================

class TestToolManager:

    def test_register_and_execute_tool(self, search_tool):
        tm = ToolManager()
        tm.register_tool(search_tool)
        result = tm.execute_tool("search_course_content", query="RAG retrieval")
        assert isinstance(result, str)

    def test_execute_unknown_tool_returns_error_string(self):
        tm = ToolManager()
        result = tm.execute_tool("nonexistent_tool", query="test")
        assert "not found" in result.lower()

    def test_get_tool_definitions_returns_correct_schema(self, tool_manager):
        defs = tool_manager.get_tool_definitions()
        assert isinstance(defs, list)
        assert len(defs) == 1
        defn = defs[0]
        assert defn["name"] == "search_course_content"
        assert "input_schema" in defn
        assert "query" in defn["input_schema"]["properties"]

    def test_get_last_sources_empty_before_any_search(self, tool_manager):
        assert tool_manager.get_last_sources() == []

    def test_reset_sources_clears_last_sources(self, tool_manager):
        tool_manager.execute_tool("search_course_content", query="RAG retrieval augmented")
        tool_manager.reset_sources()
        assert tool_manager.get_last_sources() == []

    def test_tool_definition_has_required_query_field(self, tool_manager):
        defs = tool_manager.get_tool_definitions()
        assert "query" in defs[0]["input_schema"]["required"]
