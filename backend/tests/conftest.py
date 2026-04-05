"""
Shared fixtures for RAG chatbot backend tests.

Mocking strategy:
- VectorStore is mocked via MagicMock — avoids ChromaDB/embedding model startup
- anthropic.Anthropic client is mocked — avoids real API calls
- All real business logic (CourseSearchTool, AIGenerator, RAGSystem) runs as-is
"""

import pytest
from unittest.mock import MagicMock, patch
from vector_store import SearchResults
from search_tools import CourseSearchTool
from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# SearchResults helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_results():
    """Two-document SearchResults with course/lesson metadata."""
    return SearchResults(
        documents=["Chunk about RAG systems.", "Chunk about embeddings."],
        metadata=[
            {"course_title": "Test Course", "lesson_number": 1},
            {"course_title": "Test Course", "lesson_number": 2},
        ],
        distances=[0.1, 0.2],
    )


@pytest.fixture
def empty_results():
    """SearchResults with no documents (is_empty() == True)."""
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def error_results():
    """SearchResults carrying an error message."""
    return SearchResults.empty("Search error: connection refused")


# ---------------------------------------------------------------------------
# VectorStore mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_store():
    """MagicMock standing in for VectorStore."""
    store = MagicMock()
    store.get_lesson_link.return_value = "https://example.com/lesson/1"
    return store


# ---------------------------------------------------------------------------
# CourseSearchTool
# ---------------------------------------------------------------------------

@pytest.fixture
def search_tool(mock_store):
    """Real CourseSearchTool wired to the mock store."""
    return CourseSearchTool(mock_store)


# ---------------------------------------------------------------------------
# AIGenerator (Anthropic client mocked at instance level)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_anthropic_client():
    """MagicMock replacing the anthropic.Anthropic client instance."""
    return MagicMock()


@pytest.fixture
def ai_generator(mock_anthropic_client):
    """Real AIGenerator with its internal client replaced by a mock."""
    gen = AIGenerator(api_key="test-key", model="claude-test")
    gen.client = mock_anthropic_client
    return gen


# ---------------------------------------------------------------------------
# Anthropic response builders
# ---------------------------------------------------------------------------

def make_end_turn_response(text: str = "Direct answer."):
    """Build a mock Anthropic response with stop_reason='end_turn'."""
    response = MagicMock()
    response.stop_reason = "end_turn"
    content_block = MagicMock()
    content_block.text = text
    content_block.type = "text"
    response.content = [content_block]
    return response


def make_tool_use_response(tool_name: str = "search_course_content",
                           tool_id: str = "toolu_abc",
                           tool_input: dict = None):
    """Build a mock Anthropic response with stop_reason='tool_use'."""
    if tool_input is None:
        tool_input = {"query": "test query"}
    response = MagicMock()
    response.stop_reason = "tool_use"
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = tool_name
    tool_block.input = tool_input
    response.content = [tool_block]
    return response
