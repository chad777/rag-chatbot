"""
Tests for RAGSystem.query() in rag_system.py

Coverage:
- Prompt wrapping: original query prefixed with instruction
- Return type: (str, list) tuple
- Tool definitions passed to AIGenerator
- tool_manager reference passed to AIGenerator
- Sources retrieved from tool_manager and returned
- Sources reset after retrieval
- Session history passed when session_id provided
- No history when no session_id
- Session updated with original (un-wrapped) query
- Session NOT updated when no session_id
- Content question triggers search tool (integration)
- General question skips search (integration)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from rag_system import RAGSystem
from tests.conftest import make_end_turn_response, make_tool_use_response


# ---------------------------------------------------------------------------
# Fixture: RAGSystem with all heavy dependencies mocked
# ---------------------------------------------------------------------------

@pytest.fixture
def rag(mocker):
    """
    RAGSystem with VectorStore, AIGenerator, DocumentProcessor, and
    SessionManager replaced by MagicMocks so no ChromaDB or API is touched.
    """
    mocker.patch("rag_system.VectorStore")
    mocker.patch("rag_system.AIGenerator")
    mocker.patch("rag_system.DocumentProcessor")
    mocker.patch("rag_system.SessionManager")

    config = MagicMock()
    config.ANTHROPIC_API_KEY = "test-key"
    config.ANTHROPIC_MODEL = "claude-test"
    config.CHROMA_PATH = ":memory:"
    config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    config.MAX_RESULTS = 5
    config.MAX_HISTORY = 2
    config.CHUNK_SIZE = 800
    config.CHUNK_OVERLAP = 100

    system = RAGSystem(config)
    # Make generate_response return a plain string by default
    system.ai_generator.generate_response.return_value = "AI response text"
    # tool_manager is a real ToolManager (it only manages search_tool)
    # Override get_last_sources / reset_sources so we can inspect them easily
    return system


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

class TestPromptConstruction:
    def test_query_wraps_prompt_with_instruction_prefix(self, rag):
        rag.query("What is RAG?")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs["query"].startswith("Answer this question about course materials:")

    def test_wrapped_prompt_contains_original_question(self, rag):
        rag.query("What is retrieval-augmented generation?")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert "retrieval-augmented generation" in call_kwargs["query"]


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------

class TestReturnValue:
    def test_returns_tuple(self, rag):
        result = rag.query("What is RAG?")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_string(self, rag):
        response, _ = rag.query("What is RAG?")
        assert isinstance(response, str)

    def test_second_element_is_list(self, rag):
        _, sources = rag.query("What is RAG?")
        assert isinstance(sources, list)

    def test_response_matches_ai_generator_output(self, rag):
        rag.ai_generator.generate_response.return_value = "Specific answer"
        response, _ = rag.query("What is RAG?")
        assert response == "Specific answer"


# ---------------------------------------------------------------------------
# Tool wiring
# ---------------------------------------------------------------------------

class TestToolWiring:
    def test_tool_definitions_passed_to_generate_response(self, rag):
        rag.query("What is RAG?")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        tools = call_kwargs.get("tools")
        assert tools is not None
        assert len(tools) > 0

    def test_tool_manager_passed_to_generate_response(self, rag):
        rag.query("What is RAG?")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("tool_manager") is rag.tool_manager


# ---------------------------------------------------------------------------
# Source flow
# ---------------------------------------------------------------------------

class TestSourceFlow:
    def test_sources_returned_match_tool_manager_output(self, rag):
        expected_sources = [{"text": "Test Course - Lesson 1", "url": "https://example.com"}]
        # Inject sources into the real search_tool
        rag.search_tool.last_sources = expected_sources
        _, sources = rag.query("What is RAG?")
        assert sources == expected_sources

    def test_sources_reset_after_query(self, rag):
        rag.search_tool.last_sources = [{"text": "Some Course"}]
        rag.query("What is RAG?")
        # After query, sources should have been reset
        assert rag.search_tool.last_sources == []

    def test_empty_sources_when_no_tool_used(self, rag):
        rag.search_tool.last_sources = []  # no tool was triggered
        _, sources = rag.query("What is 2 + 2?")
        assert sources == []


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSessionManagement:
    def test_no_history_when_no_session_id(self, rag):
        rag.query("What is RAG?")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") is None

    def test_history_passed_when_session_id_provided(self, rag):
        # SessionManager.get_conversation_history returns a non-None string
        rag.session_manager.get_conversation_history.return_value = "User: hi\nAssistant: hello"
        rag.query("follow-up question", session_id="session_1")
        call_kwargs = rag.ai_generator.generate_response.call_args[1]
        assert call_kwargs.get("conversation_history") == "User: hi\nAssistant: hello"

    def test_session_add_exchange_called_with_original_query(self, rag):
        rag.session_manager.get_conversation_history.return_value = None
        rag.query("What is embeddings?", session_id="session_1")
        rag.session_manager.add_exchange.assert_called_once_with(
            "session_1",
            "What is embeddings?",   # original query, NOT the wrapped prompt
            "AI response text",
        )

    def test_session_not_updated_when_no_session_id(self, rag):
        rag.query("What is RAG?")
        rag.session_manager.add_exchange.assert_not_called()


# ---------------------------------------------------------------------------
# Integration: content vs. general question routing
# ---------------------------------------------------------------------------

class TestQueryRouting:
    def test_content_question_triggers_tool_and_returns_search_response(
            self, rag, mock_store, sample_results):
        """
        When the AI decides to use the search tool, the tool result flows back
        to the AI and the final synthesized answer is returned.
        We verify this by wiring a real CourseSearchTool to a mock store
        and simulating the full two-call sequence in AIGenerator.
        """
        # Replace the mocked ai_generator with a real one backed by a mock client
        from ai_generator import AIGenerator
        mock_client = MagicMock()

        # First call: Claude uses search tool
        tool_response = make_tool_use_response(tool_input={"query": "What is RAG?"})
        # Second call: Claude synthesizes answer
        final_response = make_end_turn_response("RAG stands for Retrieval-Augmented Generation.")
        mock_client.messages.create.side_effect = [tool_response, final_response]

        real_gen = AIGenerator(api_key="test-key", model="claude-test")
        real_gen.client = mock_client
        rag.ai_generator = real_gen

        # Wire a real CourseSearchTool to a mock store with actual results
        mock_store.search.return_value = sample_results
        mock_store.get_lesson_link.return_value = None
        from search_tools import CourseSearchTool
        rag.search_tool = CourseSearchTool(mock_store)
        rag.tool_manager.tools["search_course_content"] = rag.search_tool

        response, sources = rag.query("What is RAG?")
        assert response == "RAG stands for Retrieval-Augmented Generation."
        # Tool was called, so search was triggered
        mock_store.search.assert_called_once()

    def test_general_question_skips_search_and_returns_direct_response(
            self, rag, mock_store):
        """
        When the AI answers directly (no tool_use), search is never triggered
        and sources list is empty.
        """
        from ai_generator import AIGenerator
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_end_turn_response("42.")

        real_gen = AIGenerator(api_key="test-key", model="claude-test")
        real_gen.client = mock_client
        rag.ai_generator = real_gen

        response, sources = rag.query("What is 6 times 7?")
        assert response == "42."
        assert sources == []
        mock_store.search.assert_not_called()
