"""
Tests for the FastAPI endpoints: /api/query, /api/courses, /api/sessions/{id}/reset.

Uses a test app defined in conftest.py that mirrors app.py's routes without mounting
the static frontend files (which don't exist in the test environment).
"""
import pytest


# ===========================================================================
# POST /api/query
# ===========================================================================

class TestQueryEndpoint:

    def test_happy_path_returns_answer_sources_and_session_id(self, api_client):
        response = api_client.post("/api/query", json={"query": "What is RAG?"})
        assert response.status_code == 200
        body = response.json()
        assert body["answer"] == "RAG stands for Retrieval Augmented Generation."
        assert isinstance(body["sources"], list)
        assert "session_id" in body

    def test_auto_creates_session_when_not_provided(self, api_client, mock_rag_system):
        api_client.post("/api/query", json={"query": "Hello"})
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_does_not_create_session_when_id_provided(self, api_client, mock_rag_system):
        api_client.post(
            "/api/query", json={"query": "Hello", "session_id": "session_abc"}
        )
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_returned_session_id_matches_provided_one(self, api_client):
        response = api_client.post(
            "/api/query", json={"query": "Hello", "session_id": "session_abc"}
        )
        assert response.json()["session_id"] == "session_abc"

    def test_auto_generated_session_id_comes_from_session_manager(
        self, api_client, mock_rag_system
    ):
        mock_rag_system.session_manager.create_session.return_value = "session_99"
        response = api_client.post("/api/query", json={"query": "Hello"})
        assert response.json()["session_id"] == "session_99"

    def test_query_forwarded_to_rag_system(self, api_client, mock_rag_system):
        api_client.post("/api/query", json={"query": "What is attention?"})
        call_args = mock_rag_system.query.call_args
        assert "What is attention?" in call_args[0] or "What is attention?" in str(
            call_args
        )

    def test_missing_query_field_returns_422(self, api_client):
        response = api_client.post("/api/query", json={"session_id": "s1"})
        assert response.status_code == 422

    def test_empty_body_returns_422(self, api_client):
        response = api_client.post("/api/query", json={})
        assert response.status_code == 422

    def test_rag_system_exception_returns_500(self, api_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("vector store unavailable")
        response = api_client.post("/api/query", json={"query": "test"})
        assert response.status_code == 500

    def test_500_detail_contains_exception_message(self, api_client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("vector store unavailable")
        response = api_client.post("/api/query", json={"query": "test"})
        assert "vector store unavailable" in response.json()["detail"]

    def test_sources_is_list_in_response(self, api_client, mock_rag_system):
        mock_rag_system.query.return_value = ("Answer", [])
        response = api_client.post("/api/query", json={"query": "test"})
        assert response.json()["sources"] == []

    def test_sources_contain_returned_dicts(self, api_client, mock_rag_system):
        mock_rag_system.query.return_value = (
            "Answer",
            [{"course": "Course A", "lesson": 2}],
        )
        response = api_client.post("/api/query", json={"query": "test"})
        assert response.json()["sources"] == [{"course": "Course A", "lesson": 2}]


# ===========================================================================
# GET /api/courses
# ===========================================================================

class TestCoursesEndpoint:

    def test_returns_200(self, api_client):
        response = api_client.get("/api/courses")
        assert response.status_code == 200

    def test_returns_total_courses_count(self, api_client):
        response = api_client.get("/api/courses")
        assert response.json()["total_courses"] == 2

    def test_returns_course_titles_list(self, api_client):
        response = api_client.get("/api/courses")
        assert response.json()["course_titles"] == [
            "Introduction to RAG",
            "Advanced NLP",
        ]

    def test_zero_courses_is_valid_response(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        response = api_client.get("/api/courses")
        assert response.status_code == 200
        assert response.json()["total_courses"] == 0
        assert response.json()["course_titles"] == []

    def test_analytics_exception_returns_500(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("db error")
        response = api_client.get("/api/courses")
        assert response.status_code == 500

    def test_500_detail_contains_exception_message(self, api_client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = Exception("db error")
        response = api_client.get("/api/courses")
        assert "db error" in response.json()["detail"]


# ===========================================================================
# POST /api/sessions/{session_id}/reset
# ===========================================================================

class TestSessionResetEndpoint:

    def test_returns_200(self, api_client):
        response = api_client.post("/api/sessions/session_1/reset")
        assert response.status_code == 200

    def test_returns_ok_status(self, api_client):
        response = api_client.post("/api/sessions/session_1/reset")
        assert response.json() == {"status": "ok"}

    def test_calls_clear_session_with_correct_id(self, api_client, mock_rag_system):
        api_client.post("/api/sessions/session_42/reset")
        mock_rag_system.session_manager.clear_session.assert_called_once_with(
            "session_42"
        )

    def test_accepts_arbitrary_session_id_strings(self, api_client):
        response = api_client.post("/api/sessions/some-random-id-123/reset")
        assert response.status_code == 200
