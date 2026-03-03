# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Always use `uv` — never `pip` directly.

```bash
# Install / sync dependencies
uv sync

# Add a package
uv add <package>

# Run the server (from backend/)
cd backend
uv run uvicorn app:app --reload --port 8000
```

The app is then available at `http://localhost:8000` (UI) and `http://localhost:8000/docs` (auto-generated API docs).

Requires a `.env` file in the repo root:
```
ANTHROPIC_API_KEY=sk-ant-...
```

## Architecture

This is a RAG chatbot that lets users query course documents via a chat UI. The backend is a single FastAPI process that also serves the frontend as static files.

**Key data flow for a user query:**

1. `frontend/script.js` — `sendMessage()` POSTs `{ query, session_id }` to `/api/query`
2. `backend/app.py` — creates a session if needed, delegates to `RAGSystem.query()`
3. `backend/rag_system.py` — loads conversation history, calls `AIGenerator` with Claude + tool definitions
4. Claude decides whether to call `search_course_content` tool (tool-use) or answer directly
5. If tool-use: `search_tools.py → vector_store.py` performs a two-step ChromaDB lookup:
   - `course_catalog` collection: semantic fuzzy-match on course name
   - `course_content` collection: semantic search filtered by resolved course + optional lesson number
6. Tool results are fed back to Claude in a second API call; final answer is returned
7. Response `{ answer, sources, session_id }` flows back to the browser; answer is rendered as Markdown

**Component responsibilities:**

| File | Role |
|---|---|
| `backend/config.py` | Single `Config` dataclass — model name, chunk sizes, ChromaDB path, history limit |
| `backend/models.py` | Pydantic models: `Course`, `Lesson`, `CourseChunk` |
| `backend/document_processor.py` | Parses structured `.txt` course files, sentence-splits into overlapping chunks |
| `backend/vector_store.py` | ChromaDB wrapper; two collections: `course_catalog` and `course_content` |
| `backend/ai_generator.py` | Anthropic API client; handles the two-turn tool-use loop |
| `backend/search_tools.py` | `CourseSearchTool` + `ToolManager`; translates Claude tool calls into vector store searches |
| `backend/session_manager.py` | In-memory conversation history keyed by session ID |

**Course document format** (`docs/*.txt`):
```
Course Title: ...
Course Link: https://...
Course Instructor: ...

Lesson 0: Title
Lesson Link: https://...
[lesson content]
```

`DocumentProcessor` parses this structure, then chunks each lesson's text with sentence-aware splitting (`CHUNK_SIZE=800`, `CHUNK_OVERLAP=100`). On startup, `app.py` loads `docs/` into ChromaDB, skipping courses already indexed (deduplication by title).

## Dependencies note

`numpy<2` is pinned in `pyproject.toml` because `torch` (used by `sentence-transformers`) was compiled against NumPy 1.x and is incompatible with NumPy 2.x.
