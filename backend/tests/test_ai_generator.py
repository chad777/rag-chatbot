"""
Tests for AIGenerator in ai_generator.py

Coverage:
- Direct (non-tool) response path
- Single tool-call round: tool_use → end_turn
- Two tool-call rounds: tool_use → tool_use → synthesis
- Max-rounds enforcement: forced synthesis call without tools after 2 rounds
- Tool execution error handling (exception passed as string to Claude)
- Conversation history injected into system prompt
- tool_choice set when tools + tool_manager provided
- No tool_choice on the no-tools direct path

All tests verify EXTERNAL behaviour — API calls made, tools executed, return
values — rather than internal method names or private state.
"""

import pytest
from unittest.mock import MagicMock, call
from ai_generator import AIGenerator
from tests.conftest import make_end_turn_response, make_tool_use_response


# ---------------------------------------------------------------------------
# Direct response (no tool use)
# ---------------------------------------------------------------------------

class TestDirectResponse:
    def test_returns_text_on_end_turn(self, ai_generator, mock_anthropic_client):
        response = make_end_turn_response("Here is a direct answer.")
        mock_anthropic_client.messages.create.return_value = response
        result = ai_generator.generate_response("What is Python?")
        assert result == "Here is a direct answer."

    def test_single_api_call_on_end_turn(self, ai_generator, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_end_turn_response()
        ai_generator.generate_response("What is Python?")
        assert mock_anthropic_client.messages.create.call_count == 1

    def test_no_tool_choice_when_tools_not_provided(self, ai_generator, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_end_turn_response()
        ai_generator.generate_response("What is Python?")
        kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "tool_choice" not in kwargs

    def test_tool_choice_auto_when_tools_and_manager_provided(self, ai_generator, mock_anthropic_client):
        """tool_choice=auto must appear on the first API call when both tools and tool_manager are given."""
        # First call returns end_turn so the loop exits immediately after one call
        mock_anthropic_client.messages.create.return_value = make_end_turn_response("answer")
        tools = [{"name": "search_course_content", "description": "...", "input_schema": {}}]
        tool_manager = MagicMock()
        ai_generator.generate_response("What is RAG?", tools=tools, tool_manager=tool_manager)
        first_call_kwargs = mock_anthropic_client.messages.create.call_args_list[0][1]
        assert first_call_kwargs.get("tool_choice") == {"type": "auto"}


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

class TestConversationHistory:
    def test_history_appended_to_system_prompt(self, ai_generator, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_end_turn_response()
        ai_generator.generate_response("follow-up", conversation_history="User: hi\nAssistant: hello")
        kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "User: hi" in kwargs["system"]
        assert "Previous conversation:" in kwargs["system"]

    def test_no_history_yields_clean_system_prompt(self, ai_generator, mock_anthropic_client):
        mock_anthropic_client.messages.create.return_value = make_end_turn_response()
        ai_generator.generate_response("standalone question")
        kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "Previous conversation:" not in kwargs["system"]
        assert kwargs["system"] == AIGenerator.SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Single-round tool use (tool_use → end_turn, 2 API calls total)
# ---------------------------------------------------------------------------

class TestToolUseFlow:
    def _setup_tool_use(self, mock_anthropic_client,
                        tool_input=None,
                        final_text="Final synthesized answer."):
        """Configure client to return tool_use then end_turn."""
        if tool_input is None:
            tool_input = {"query": "What is RAG?"}
        first = make_tool_use_response(tool_input=tool_input)
        second = make_end_turn_response(final_text)
        mock_anthropic_client.messages.create.side_effect = [first, second]
        return first, second

    def test_triggers_tool_execution_on_tool_use_stop_reason(
            self, ai_generator, mock_anthropic_client):
        self._setup_tool_use(mock_anthropic_client)
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search result text"
        tools = [{"name": "search_course_content"}]
        result = ai_generator.generate_response(
            "What is RAG?", tools=tools, tool_manager=tool_manager
        )
        assert result == "Final synthesized answer."

    def test_two_api_calls_made(self, ai_generator, mock_anthropic_client):
        self._setup_tool_use(mock_anthropic_client)
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        ai_generator.generate_response(
            "What is RAG?",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )
        assert mock_anthropic_client.messages.create.call_count == 2

    def test_execute_tool_called_with_correct_args(self, ai_generator, mock_anthropic_client):
        self._setup_tool_use(mock_anthropic_client,
                             tool_input={"query": "RAG definition", "course_name": "AI Basics"})
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "some result"
        ai_generator.generate_response(
            "What is RAG?",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )
        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="RAG definition",
            course_name="AI Basics",
        )

    def test_tool_result_message_in_second_call_messages(self, ai_generator, mock_anthropic_client):
        """The second API call's messages must include a tool_result block."""
        self._setup_tool_use(mock_anthropic_client)
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "tool output text"
        ai_generator.generate_response(
            "query",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )
        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        tool_result_found = any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for msg in messages
            for block in (msg.get("content", []) if isinstance(msg.get("content"), list) else [])
        )
        assert tool_result_found, "Second API call must contain a tool_result message"

    def test_tool_result_contains_tool_output(self, ai_generator, mock_anthropic_client):
        """tool_result content must equal what execute_tool returned."""
        self._setup_tool_use(mock_anthropic_client)
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "specific tool output"
        ai_generator.generate_response(
            "query",
            tools=[{"name": "search_course_content"}],
            tool_manager=tool_manager,
        )
        second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1][1]
        messages = second_call_kwargs["messages"]
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        assert block["content"] == "specific tool output"
                        return
        pytest.fail("No tool_result block found in second API call messages")

    def test_no_tool_execution_when_tool_manager_is_none(self, ai_generator, mock_anthropic_client):
        """When tool_manager is None, the direct (no-tool) path is used — single API call."""
        first = make_tool_use_response()
        mock_anthropic_client.messages.create.return_value = first
        ai_generator.generate_response("query", tools=[{"name": "search_course_content"}])
        assert mock_anthropic_client.messages.create.call_count == 1

    def test_no_tool_choice_when_tools_provided_without_manager(self, ai_generator, mock_anthropic_client):
        """When tool_manager is None, tool_choice must NOT be sent — we take the direct path."""
        mock_anthropic_client.messages.create.return_value = make_end_turn_response("direct answer")
        ai_generator.generate_response("query", tools=[{"name": "search_course_content"}])
        kwargs = mock_anthropic_client.messages.create.call_args[1]
        assert "tool_choice" not in kwargs


# ---------------------------------------------------------------------------
# Multi-round agentic loop
# ---------------------------------------------------------------------------

class TestAgenticLoop:
    """
    Verify sequential tool-calling behaviour: up to 2 rounds, each a separate
    API call. All assertions are on observable externals — API call counts,
    execute_tool invocations, and the final returned string.
    """

    def _tools(self):
        return [{"name": "search_course_content"}]

    def test_single_round_two_api_calls_total(self, ai_generator, mock_anthropic_client):
        """tool_use → end_turn: 2 API calls, 1 tool execution."""
        mock_anthropic_client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "q1"}),
            make_end_turn_response("answer after one search"),
        ]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result 1"
        result = ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)
        assert mock_anthropic_client.messages.create.call_count == 2
        assert tool_manager.execute_tool.call_count == 1
        assert result == "answer after one search"

    def test_two_rounds_three_api_calls_total(self, ai_generator, mock_anthropic_client):
        """tool_use → tool_use → end_turn: 3 API calls, 2 tool executions."""
        mock_anthropic_client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "q1"}, tool_id="id1"),
            make_tool_use_response(tool_input={"query": "q2"}, tool_id="id2"),
            make_end_turn_response("answer after two searches"),
        ]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "some result"
        result = ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)
        assert mock_anthropic_client.messages.create.call_count == 3
        assert tool_manager.execute_tool.call_count == 2
        assert result == "answer after two searches"

    def test_max_rounds_enforced_forces_synthesis_call(self, ai_generator, mock_anthropic_client):
        """
        When both rounds are used up (tool_use × 2), the loop exits and a
        final synthesis call is made WITHOUT tools — enforcing the 2-round cap.
        """
        mock_anthropic_client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "q1"}, tool_id="id1"),
            make_tool_use_response(tool_input={"query": "q2"}, tool_id="id2"),
            make_end_turn_response("synthesised answer"),
        ]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)

        # The third (final) call must NOT include 'tools'
        final_call_kwargs = mock_anthropic_client.messages.create.call_args_list[2][1]
        assert "tools" not in final_call_kwargs, (
            "After 2 rounds the synthesis call must have no tools so Claude "
            "cannot loop further"
        )

    def test_two_rounds_correct_tool_args_each_round(self, ai_generator, mock_anthropic_client):
        """Each round's tool call must carry its own input args."""
        mock_anthropic_client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "first search"}, tool_id="id1"),
            make_tool_use_response(tool_input={"query": "second search"}, tool_id="id2"),
            make_end_turn_response("final"),
        ]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "ok"
        ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)
        calls = tool_manager.execute_tool.call_args_list
        assert calls[0] == call("search_course_content", query="first search")
        assert calls[1] == call("search_course_content", query="second search")

    def test_tool_exception_passed_as_string_to_claude(self, ai_generator, mock_anthropic_client):
        """When execute_tool raises, the error string is passed to Claude as a tool_result."""
        mock_anthropic_client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "q"}),
            make_end_turn_response("graceful answer"),
        ]
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("DB connection failed")
        result = ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)

        # Claude must have received the error as tool_result content
        second_call_msgs = mock_anthropic_client.messages.create.call_args_list[1][1]["messages"]
        error_delivered = any(
            isinstance(block, dict)
            and block.get("type") == "tool_result"
            and "DB connection failed" in block.get("content", "")
            for msg in second_call_msgs
            for block in (msg.get("content", []) if isinstance(msg.get("content"), list) else [])
        )
        assert error_delivered, "Error string must appear as tool_result content for Claude"
        assert result == "graceful answer"
        # 2 API calls: round 0 (tool_use) + round 1 (end_turn after error)
        assert mock_anthropic_client.messages.create.call_count == 2

    def test_early_exit_when_claude_returns_text_in_first_round(
            self, ai_generator, mock_anthropic_client):
        """
        If Claude answers directly on the first round (end_turn immediately),
        no tools are executed and only 1 API call is made.
        """
        mock_anthropic_client.messages.create.return_value = make_end_turn_response("direct")
        tool_manager = MagicMock()
        result = ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)
        assert mock_anthropic_client.messages.create.call_count == 1
        tool_manager.execute_tool.assert_not_called()
        assert result == "direct"

    def test_two_round_final_return_value_is_synthesis_text(self, ai_generator, mock_anthropic_client):
        """The string returned must be the text from the final synthesis call."""
        mock_anthropic_client.messages.create.side_effect = [
            make_tool_use_response(tool_input={"query": "q1"}, tool_id="id1"),
            make_tool_use_response(tool_input={"query": "q2"}, tool_id="id2"),
            make_end_turn_response("This is the definitive two-round answer."),
        ]
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"
        result = ai_generator.generate_response("query", tools=self._tools(), tool_manager=tool_manager)
        assert result == "This is the definitive two-round answer."
