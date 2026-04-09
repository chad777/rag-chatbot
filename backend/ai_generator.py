import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for searching course information.

Tool Usage:
- **get_course_outline**: Use for any question asking for a course outline, what lessons a course has, what topics are covered, or a course overview. Always return the course title, course link, and the number and title of every lesson.
- **search_course_content**: Use for questions about specific course content or detailed educational materials. Up to 2 searches per query — use a second search only if the first results are insufficient.
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Outline/overview questions**: Use get_course_outline, then present the course title, course link, and numbered lesson list
- **Course-specific content questions**: Use search_course_content, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool-use explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None,
                         image_data: Optional[str] = None,
                         image_media_type: Optional[str] = None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        if image_data and image_media_type:
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_data,
                    },
                },
                {"type": "text", "text": query},
            ]
        else:
            content = query

        messages = [{"role": "user", "content": content}]

        if tools and tool_manager:
            return self._run_agentic_loop(messages, system_content, tools, tool_manager, max_rounds=2)

        # No-tools path: single direct call
        response = self.client.messages.create(
            **self.base_params,
            messages=messages,
            system=system_content,
        )
        return response.content[0].text

    def _run_agentic_loop(self, messages: List[Dict], system: str,
                          tools: List, tool_manager, max_rounds: int = 2) -> str:
        """
        Run an agentic loop allowing Claude up to max_rounds tool-call rounds.

        Terminates when:
          (a) max_rounds completed
          (b) Claude's response has no tool_use blocks (stop_reason != "tool_use")
          (c) tool execution returns an error (error string passed to Claude, loop continues)

        On termination (a): makes one final synthesis call without tools.
        On termination (b): returns Claude's text directly (no extra API call needed).

        Args:
            messages: Initial messages list (mutated in-place across rounds)
            system: System prompt string
            tools: Tool definitions to include in each loop call
            tool_manager: Executes tool calls
            max_rounds: Maximum tool-call rounds before forcing synthesis

        Returns:
            Final response text
        """
        rounds_completed = 0

        while rounds_completed < max_rounds:
            response = self.client.messages.create(
                **self.base_params,
                messages=messages,
                system=system,
                tools=tools,
                tool_choice={"type": "auto"},
            )

            # Termination (b): Claude returned text — no more tools needed
            if response.stop_reason != "tool_use":
                return response.content[0].text

            # Execute every tool call Claude requested this round
            tool_results = self._execute_tools_for_round(response, tool_manager)

            # Append this round to the conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user",      "content": tool_results})

            rounds_completed += 1

        # Termination (a): max_rounds exhausted — synthesise without tools
        final_response = self.client.messages.create(
            **self.base_params,
            messages=messages,
            system=system,
            # tools intentionally omitted so Claude cannot loop further
        )
        return final_response.content[0].text

    def _execute_tools_for_round(self, response, tool_manager) -> List[Dict]:
        """
        Execute all tool_use blocks in a single response and return tool_result dicts.

        Never raises — errors are converted to descriptive strings so the API
        contract (every tool_use must have a tool_result) is always satisfied.

        Args:
            response: Anthropic API response containing tool_use content blocks
            tool_manager: Executes tool calls by name

        Returns:
            List of tool_result dicts ready to be appended as a user message
        """
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                content = tool_manager.execute_tool(block.name, **block.input)
            except Exception as exc:
                content = f"Tool execution error: {exc}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": content,
            })
        return tool_results
