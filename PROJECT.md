# RAG Chatbot — Project Reference

## Overview

A **Retrieval-Augmented Generation (RAG)** system that answers questions about course materials using semantic search and Claude AI. Users interact through a web chat interface; Claude decides when to search the vector store versus answering from general knowledge.

**Stack:** Python 3.13+ · FastAPI · ChromaDB · SentenceTransformers · Anthropic Claude API · Vanilla JS frontend

---

## Project Structure

```
starting-ragchatbot-codebase-main/
├── backend/
│   ├── app.py               # FastAPI entry point, API routes, startup loader
│   ├── config.py            # All configuration (model, paths, chunking)
│   ├── rag_system.py        # Main orchestrator — wires all components together
│   ├── ai_generator.py      # Claude API client, agentic tool-use loop
│   ├── search_tools.py      # Tool definitions: CourseSearchTool, CourseOutlineTool, ToolManager
│   ├── vector_store.py      # ChromaDB wrapper — two collections: catalog + content
│   ├── document_processor.py# Parses course .txt files, chunks content
│   ├── session_manager.py   # Per-session conversation history
│   └── models.py            # Dataclasses: Course, Lesson, CourseChunk
├── frontend/
│   ├── index.html           # Single-page chat UI
│   ├── style.css            # Dark-theme styles
│   ├── script.js            # Chat logic, API calls, source rendering
│   └── marked.min.js        # Markdown renderer
└── docs/                    # Course .txt files (loaded at startup)
```

---

## Setup

### Prerequisites

- Python 3.13+
- `uv` package manager
- Anthropic API key

### Install & configure

```bash
# Navigate to project
cd private-projects/DeepLearningAI/starting-ragchatbot-codebase-main

# Install dependencies
uv sync

# Create .env file in project root (NOT inside backend/)
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

### Configuration (`backend/config.py`)

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model used |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer for vector embeddings |
| `CHUNK_SIZE` | `800` | Characters per content chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `MAX_RESULTS` | `5` | Max semantic search results |
| `MAX_HISTORY` | `2` | Conversation turns remembered |
| `CHROMA_PATH` | `./chroma_db` | ChromaDB persistence location (relative to `backend/`) |

---

## Running the Server

```bash
# Add uv to PATH (required in MINGW64/Windows)
export PATH="$PATH:/c/Users/edgen/.local/bin"

# Start server (run from backend/ directory)
cd backend
uv run python -m uvicorn app:app --reload --port 8000
```

**Access points:**

| URL | Description |
|---|---|
| `http://localhost:8000` | Web chat interface |
| `http://localhost:8000/docs` | FastAPI auto-generated API docs |
| `http://localhost:8000/api/courses` | Course catalog stats (GET) |
| `http://localhost:8000/api/query` | Send a query (POST) |

**Stop the server (Windows):**

```bash
taskkill //F //IM python.exe
```

---

## API

### POST `/api/query`

Send a user question to the RAG system.

**Request:**
```json
{
  "query": "What is RAG?",
  "session_id": "session_1"
}
```

**Response:**
```json
{
  "answer": "RAG stands for Retrieval-Augmented Generation...",
  "sources": [
    { "text": "Introduction to RAG - Lesson 2", "url": "https://..." }
  ],
  "session_id": "session_1"
}
```

### GET `/api/courses`

Returns the course catalog.

```json
{
  "total_courses": 3,
  "course_titles": ["Introduction to RAG", "MCP Course", "...]
}
```

### DELETE `/api/session/{session_id}`

Clears conversation history for a session.

---

## Tools (Claude Tool Use)

Claude autonomously selects tools based on the query. Both tools are registered at startup in `rag_system.py`.

### `search_course_content` — `CourseSearchTool`

Semantic search over chunked course content.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | What to search for |
| `course_name` | string | no | Filter by course (partial match OK) |
| `lesson_number` | integer | no | Filter by lesson number |

**Use case:** Questions about specific content, concepts, or details within a course.

**Data source:** `course_content` ChromaDB collection (chunked lesson text).

### `get_course_outline` — `CourseOutlineTool`

Returns a course's complete outline: title, course link, and every lesson's number and title.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `course_title` | string | yes | Course to look up (partial match OK, e.g. `"MCP"`, `"RAG"`) |

**Output includes:**
- Course title
- Course link (URL)
- Full ordered lesson list (lesson number + lesson title)

**Use case:** "What lessons are in the X course?", "Give me an overview of course Y", "What topics does Z cover?"

**Data source:** `course_catalog` ChromaDB collection (course metadata with serialised `lessons_json`).

---

## How It Works — Request Flow

```
User query
    │
    ▼
POST /api/query  (app.py)
    │
    ▼
RAGSystem.query()  (rag_system.py)
    │  ├── fetch conversation history (SessionManager)
    │  └── call AIGenerator.generate_response()
    │
    ▼
AIGenerator._run_agentic_loop()  (ai_generator.py)
    │  Claude receives: query + history + tool definitions
    │
    ├── Claude calls get_course_outline  ──▶  CourseOutlineTool.execute()
    │       └── VectorStore.get_course_outline()
    │               └── course_catalog.get()  (ChromaDB)
    │
    ├── Claude calls search_course_content  ──▶  CourseSearchTool.execute()
    │       └── VectorStore.search()
    │               └── course_content.query()  (ChromaDB, semantic)
    │
    └── Claude generates final response (up to 2 tool rounds)
    │
    ▼
Return (answer, sources)  →  JSON response to frontend
```

---

## Adding Course Documents

Course documents go in the `docs/` folder and are loaded automatically at server startup. Existing courses (matched by title) are skipped.

**Required `.txt` format:**

```
Course Title: Introduction to RAG
Course Link: https://example.com/course
Course Instructor: Jane Smith

Lesson 0: What is RAG?
Lesson Link: https://example.com/course/lesson-0
[lesson content here...]

Lesson 1: Vector Databases
Lesson Link: https://example.com/course/lesson-1
[lesson content here...]
```

**To force a full reload** (re-process all documents), set `clear_existing=True` in `rag_system.add_course_folder()` in `app.py`'s `startup_event`.

---

## Frontend

Single-page application served as static files by FastAPI.

| File | Role |
|---|---|
| `index.html` | Layout: sidebar (New Chat, Courses, Try Asking) + chat area |
| `style.css` | Dark theme, CSS variables, responsive layout |
| `script.js` | Sends queries to `/api/query`, renders markdown responses, displays source links |
| `marked.min.js` | Client-side markdown-to-HTML rendering |

**Sidebar items** (all share `.stats-header` / `.suggested-header` style):
- **+ NEW CHAT** — clears chat and starts a fresh session
- **COURSES** — collapsible, shows loaded course titles from `/api/courses`
- **TRY ASKING** — collapsible, shows example prompt suggestions

---

## Session 2026-04-06 — Changes Made

### 1. Frontend: New Chat button styling (`frontend/style.css`)

Added `appearance: none` and `outline: none` to `.new-chat-btn` so the `<button>` element renders identically to the `<summary>`-based sidebar headers (Courses, Try Asking) — removing the browser-default button border.

```css
.new-chat-btn {
    /* ... existing properties ... */
    appearance: none;
    -webkit-appearance: none;
    outline: none;
}
```

### 2. Backend: `get_course_outline` method (`backend/vector_store.py`)

New public method on `VectorStore`. Accepts a fuzzy course name, resolves it via semantic search, then retrieves full course metadata from the `course_catalog` collection.

```python
def get_course_outline(self, course_name: str) -> Optional[Dict[str, Any]]:
    # Returns: { "title": ..., "course_link": ..., "lessons": [...] }
```

### 3. Backend: `CourseOutlineTool` class (`backend/search_tools.py`)

New tool alongside `CourseSearchTool`. Takes a `course_title` input, calls `VectorStore.get_course_outline()`, and returns a formatted string with the course title, link, and numbered lesson list. Also sets `last_sources` so the course link appears in the frontend as a clickable source.

```python
class CourseOutlineTool(Tool):
    def get_tool_definition(self) -> Dict[str, Any]: ...
    def execute(self, course_title: str) -> str: ...
```

### 4. Backend: System prompt update (`backend/ai_generator.py`)

Updated `AIGenerator.SYSTEM_PROMPT` to instruct Claude to:
- Use `get_course_outline` for outline/overview queries — returning title, course link, and full numbered lesson list
- Use `search_course_content` for content-specific queries
- Not use tools for general knowledge questions

### 5. Backend: Tool registration (`backend/rag_system.py`)

Imported `CourseOutlineTool` and registered it with the `ToolManager` at startup:

```python
from search_tools import ToolManager, CourseSearchTool, CourseOutlineTool

self.outline_tool = CourseOutlineTool(self.vector_store)
self.tool_manager.register_tool(self.outline_tool)
```
