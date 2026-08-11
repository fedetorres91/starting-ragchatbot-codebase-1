"""Shared fixtures for the RAG chatbot test suite."""
import numpy as np
import pytest
from unittest.mock import MagicMock

from models import Course, Lesson, CourseChunk
from vector_store import VectorStore
from tests.helpers import make_text_response, make_tool_use_response  # re-export for convenience


# ---------------------------------------------------------------------------
# Dummy embedding function — replaces the 90 MB SentenceTransformer model.
# Same text always produces the same vector (hash-seeded), so similarity
# comparisons are deterministic. Tests run in < 1 second each.
# ---------------------------------------------------------------------------

class DummyEmbeddingFunction:
    DIM = 384

    def name(self) -> str:
        return "dummy-embedding-function"

    def __call__(self, input):  # chromadb protocol: input is List[str]
        embeddings = []
        for text in input:
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            vec = rng.random(self.DIM, dtype=np.float32)
            vec /= np.linalg.norm(vec) + 1e-9
            embeddings.append(vec.tolist())
        return embeddings


@pytest.fixture(scope="function")
def dummy_ef():
    return DummyEmbeddingFunction()


# ---------------------------------------------------------------------------
# VectorStore using a real PersistentClient in a unique tmp_path directory.
# Each test gets its own isolated ChromaDB storage — no shared state.
# The embedding function is still mocked to avoid the 90 MB model download.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def vector_store(tmp_path, dummy_ef, monkeypatch):
    """
    VectorStore backed by a real PersistentClient in tmp_path.
    tmp_path is unique per test, so ChromaDB state is fully isolated.
    The SentenceTransformerEmbeddingFunction is replaced with DummyEmbeddingFunction.
    """
    monkeypatch.setattr(
        "chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction",
        lambda model_name: dummy_ef,
    )
    return VectorStore(
        chroma_path=str(tmp_path / "chroma"),
        embedding_model="all-MiniLM-L6-v2",
        max_results=5,
    )


# ---------------------------------------------------------------------------
# Sample domain objects
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_course():
    return Course(
        title="Introduction to RAG",
        course_link="https://example.com/rag",
        instructor="Ada Lovelace",
        lessons=[
            Lesson(lesson_number=1, title="What is RAG?",
                   lesson_link="https://example.com/rag/1"),
            Lesson(lesson_number=2, title="Vector Stores",
                   lesson_link="https://example.com/rag/2"),
        ],
    )


@pytest.fixture
def sample_chunks():
    """Two chunks with explicit integer lesson numbers."""
    return [
        CourseChunk(
            content="RAG stands for Retrieval Augmented Generation.",
            course_title="Introduction to RAG",
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Vector stores enable fast semantic search over embeddings.",
            course_title="Introduction to RAG",
            lesson_number=2,
            chunk_index=1,
        ),
    ]


@pytest.fixture
def chunk_with_none_lesson():
    """A chunk where lesson_number is None — exercises Bug B."""
    return CourseChunk(
        content="General course overview without a lesson assignment.",
        course_title="Introduction to RAG",
        lesson_number=None,
        chunk_index=99,
    )


# ---------------------------------------------------------------------------
# Anthropic response helpers
# ---------------------------------------------------------------------------

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
