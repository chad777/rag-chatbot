"""
Tests for CourseSearchTool.execute() in search_tools.py

Coverage:
- Result formatting (headers, content)
- Empty-result messages (with/without filter info)
- Error propagation
- Filter forwarding to VectorStore.search()
- last_sources population (with URL, without URL)
- Stale last_sources bug: sources must be cleared on empty/error returns
"""

import pytest
from unittest.mock import MagicMock
from vector_store import SearchResults
from search_tools import CourseSearchTool


# ---------------------------------------------------------------------------
# Happy-path: results found
# ---------------------------------------------------------------------------

class TestExecuteWithResults:
    def test_returns_string(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        result = search_tool.execute("What is RAG?")
        assert isinstance(result, str)

    def test_result_contains_course_lesson_header(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        result = search_tool.execute("What is RAG?")
        assert "[Test Course - Lesson 1]" in result

    def test_result_contains_document_text(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        result = search_tool.execute("What is RAG?")
        assert "Chunk about RAG systems." in result

    def test_multiple_results_separated_by_blank_line(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        result = search_tool.execute("embeddings")
        # Two chunks joined by "\n\n"
        assert "\n\n" in result

    def test_header_without_lesson_when_no_lesson_number(self, search_tool, mock_store):
        """When metadata has no lesson_number, header should not include 'Lesson'."""
        results = SearchResults(
            documents=["Some content."],
            metadata=[{"course_title": "Intro Course"}],  # no lesson_number key
            distances=[0.1],
        )
        mock_store.search.return_value = results
        result = search_tool.execute("intro")
        assert "[Intro Course]" in result
        assert "Lesson" not in result


# ---------------------------------------------------------------------------
# Filter forwarding
# ---------------------------------------------------------------------------

class TestFilterForwarding:
    def test_passes_query_to_store(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        search_tool.execute("What is RAG?")
        mock_store.search.assert_called_once_with(
            query="What is RAG?",
            course_name=None,
            lesson_number=None,
        )

    def test_passes_course_name_filter(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        search_tool.execute("embeddings", course_name="Test Course")
        mock_store.search.assert_called_once_with(
            query="embeddings",
            course_name="Test Course",
            lesson_number=None,
        )

    def test_passes_lesson_number_filter(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        search_tool.execute("embeddings", lesson_number=3)
        mock_store.search.assert_called_once_with(
            query="embeddings",
            course_name=None,
            lesson_number=3,
        )

    def test_passes_both_filters(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        search_tool.execute("embeddings", course_name="Test Course", lesson_number=2)
        mock_store.search.assert_called_once_with(
            query="embeddings",
            course_name="Test Course",
            lesson_number=2,
        )


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------

class TestEmptyResults:
    def test_returns_no_content_message(self, search_tool, mock_store, empty_results):
        mock_store.search.return_value = empty_results
        result = search_tool.execute("unknown topic")
        assert "No relevant content found" in result

    def test_empty_message_includes_course_name_when_filtered(self, search_tool, mock_store, empty_results):
        mock_store.search.return_value = empty_results
        result = search_tool.execute("unknown", course_name="Physics 101")
        assert "Physics 101" in result

    def test_empty_message_includes_lesson_number_when_filtered(self, search_tool, mock_store, empty_results):
        mock_store.search.return_value = empty_results
        result = search_tool.execute("unknown", lesson_number=5)
        assert "lesson 5" in result.lower()


# ---------------------------------------------------------------------------
# Error results
# ---------------------------------------------------------------------------

class TestErrorResults:
    def test_returns_error_string_from_results(self, search_tool, mock_store, error_results):
        mock_store.search.return_value = error_results
        result = search_tool.execute("query")
        assert result == error_results.error


# ---------------------------------------------------------------------------
# last_sources tracking
# ---------------------------------------------------------------------------

class TestLastSources:
    def test_last_sources_set_after_successful_search(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson/1"
        search_tool.execute("What is RAG?")
        assert len(search_tool.last_sources) == len(sample_results.documents)

    def test_last_sources_contains_text_field(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        search_tool.execute("What is RAG?")
        for source in search_tool.last_sources:
            assert "text" in source

    def test_last_sources_has_url_when_lesson_link_exists(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        mock_store.get_lesson_link.return_value = "https://example.com/lesson/1"
        search_tool.execute("What is RAG?")
        # At least one source should have a URL (both docs have lesson_number)
        assert any("url" in s for s in search_tool.last_sources)

    def test_last_sources_no_url_when_lesson_link_is_none(self, search_tool, mock_store, sample_results):
        mock_store.search.return_value = sample_results
        mock_store.get_lesson_link.return_value = None  # no URL available
        search_tool.execute("What is RAG?")
        for source in search_tool.last_sources:
            assert "url" not in source

    def test_last_sources_cleared_on_empty_result(self, search_tool, mock_store, sample_results, empty_results):
        """
        Bug 3: last_sources must be reset at the start of execute().
        If a successful search is followed by an empty search, the stale
        sources from the first call must NOT survive into the second result.
        """
        # First call populates last_sources
        mock_store.search.return_value = sample_results
        search_tool.execute("first query")
        assert len(search_tool.last_sources) > 0  # precondition

        # Second call returns empty — last_sources must be cleared
        mock_store.search.return_value = empty_results
        search_tool.execute("second query — no results")
        assert search_tool.last_sources == [], (
            "last_sources should be [] after an empty result, "
            "not carry over values from the previous call"
        )

    def test_last_sources_cleared_on_error_result(self, search_tool, mock_store, sample_results, error_results):
        """Same stale-source scenario but triggered by an error instead of empty results."""
        mock_store.search.return_value = sample_results
        search_tool.execute("first query")
        assert len(search_tool.last_sources) > 0  # precondition

        mock_store.search.return_value = error_results
        search_tool.execute("second query — error")
        assert search_tool.last_sources == [], (
            "last_sources should be [] after an error result"
        )
