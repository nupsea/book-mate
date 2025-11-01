"""
MCP Client using OpenAI for function calling.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from src.monitoring.metrics import QueryTimer, metrics_collector
from src.monitoring.judge import ResponseJudge
from src.monitoring.tracer import init_phoenix_tracing
from src.mcp_client.prompts import (
    get_system_prompt,
    get_citation_reminder,
    get_rephrase_prompt,
)

# Initialize Phoenix tracing once at module load
init_phoenix_tracing()


class BookMateAgent:
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        self.session: ClientSession | None = None
        self.tools_cache = []
        self.read_stream = None
        self.write_stream = None
        self.judge = ResponseJudge(self.client)

    async def connect_to_mcp_server(self):
        """Connect to the MCP server."""
        import os

        # Pass environment variables to MCP server subprocess
        env = dict(os.environ)

        server_params = StdioServerParameters(
            command="python", args=["-m", "src.mcp_server"], env=env
        )

        # Use async context manager correctly
        self.stdio_context = stdio_client(server_params)
        self.read_stream, self.write_stream = await self.stdio_context.__aenter__()

        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()

        # Fetch available tools from MCP server
        response = await self.session.list_tools()
        self.tools_cache = self._convert_mcp_tools_to_openai(response.tools)

        print(
            f"Connected to MCP server. Available tools: {[t['function']['name'] for t in self.tools_cache]}"
        )

    def _convert_mcp_tools_to_openai(self, mcp_tools) -> list[dict]:
        """Convert MCP tool format to OpenAI function calling format."""
        openai_tools = []
        for tool in mcp_tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema,
                    },
                }
            )
        return openai_tools

    async def call_mcp_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call via MCP server with error handling."""
        try:
            if not self.session:
                raise RuntimeError(
                    "MCP session not initialized. Call connect_to_mcp_server() first."
                )

            result = await self.session.call_tool(tool_name, arguments)
            # Combine all text content from the response
            text_content = "\n".join(
                [item.text for item in result.content if hasattr(item, "text")]
            )

            if not text_content:
                return f"Tool {tool_name} returned no content."

            return text_content
        except Exception as e:
            error_msg = f"Error calling tool '{tool_name}': {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg

    def _get_available_books(self) -> tuple[str, dict]:
        """
        Get available books from database.

        Returns:
            (formatted_list, title_to_slug_map)
        """
        try:
            from src.content.store import PgresStore

            store = PgresStore()
            with store.conn.cursor() as cur:
                cur.execute("SELECT slug, title, author FROM books ORDER BY title")
                books = cur.fetchall()

            if not books:
                return "No books currently available in the library.", {}

            # Create user-friendly list (no slugs exposed)
            book_list = "\n".join(
                [
                    f"- {title}" + (f" by {author}" if author else "")
                    for slug, title, author in books
                ]
            )

            # Create mapping for internal use
            title_to_slug = {title.lower(): slug for slug, title, _ in books}

            return f"Available books:\n{book_list}", title_to_slug
        except Exception as e:
            print(f"[WARN] Could not load book list: {e}")
            return "Book list unavailable.", {}

    async def _rephrase_query(self, original_query: str, book_title: str = None) -> str:
        """
        Use LLM to rephrase a search query that returned no results.

        Args:
            original_query: The original search query
            book_title: Optional book title for context

        Returns:
            Rephrased query string
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a search query optimization assistant.",
                    },
                    {
                        "role": "user",
                        "content": get_rephrase_prompt(original_query, book_title),
                    },
                ],
                temperature=0.3,
            )

            rephrased = response.choices[0].message.content.strip()
            print(f"[RETRY] Original query: '{original_query}'")
            print(f"[RETRY] Rephrased query: '{rephrased}'")
            return rephrased

        except Exception as e:
            print(f"[RETRY] Error rephrasing query: {e}")
            return original_query

    def _extract_search_results_count(self, tool_result: str) -> int:
        """
        Parse the number of results from a search_book tool response.

        Returns:
            Number of results, or -1 if unable to parse
        """
        try:
            # Look for "Found X results" pattern
            import re

            match = re.search(r"Found (\d+) results?", tool_result)
            if match:
                return int(match.group(1))

            # Alternative: Look for "No results found"
            if "No results found" in tool_result or "0 results" in tool_result:
                return 0

            return -1  # Unknown
        except Exception as e:
            print(f"[RETRY] Error parsing search results: {e}")
            return -1

    async def chat(
        self, user_message: str, conversation_history: list = None
    ) -> tuple[str, list, str]:
        """
        Send a message and handle tool calls automatically.

        Returns:
            (assistant_response, updated_conversation_history, query_id)
        """
        print(f"\n{'='*80}")
        print(f"[CHAT] NEW REQUEST")
        print(f"[CHAT] User message: {user_message}")
        print(
            f"[CHAT] Conversation history length: {len(conversation_history) if conversation_history else 0}"
        )
        print(f"{'='*80}\n")

        # Start monitoring
        with QueryTimer(user_message, None) as timer:
            try:
                if not self.session:
                    raise RuntimeError(
                        "MCP session not initialized. Call connect_to_mcp_server() first."
                    )

                if not user_message or not user_message.strip():
                    raise ValueError("User message cannot be empty.")

                # Get available books for system prompt
                available_books, self.title_to_slug = self._get_available_books()

                # Create system prompt
                system_prompt = {
                    "role": "system",
                    "content": get_system_prompt(available_books),
                }

                # Check if this is a new conversation or needs system prompt
                if not conversation_history:
                    print(f"[CHAT] Creating NEW conversation")
                    conversation_history = [system_prompt]
                else:
                    # Ensure system prompt exists in continuing conversations
                    if not conversation_history or conversation_history[0].get("role") != "system":
                        print(f"[CHAT] CONTINUING conversation - prepending system prompt")
                        conversation_history = [system_prompt] + conversation_history
                    else:
                        print(f"[CHAT] CONTINUING conversation with existing system prompt")

                print(f"[CHAT] Title-to-slug mapping: {self.title_to_slug}")

                # Add user message
                conversation_history.append({"role": "user", "content": user_message})

                print(f"[CHAT] Full conversation being sent to LLM:")
                for i, msg in enumerate(conversation_history):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    if role == "system":
                        print(f"  [{i}] SYSTEM: {content[:200]}...")
                    elif role == "user":
                        print(f"  [{i}] USER: {content}")
                    elif role == "assistant":
                        print(
                            f"  [{i}] ASSISTANT: {content[:100] if content else '<tool_calls>'}"
                        )
                    elif role == "tool":
                        print(f"  [{i}] TOOL: {content[:100]}...")
                print()

                # Call OpenAI with function calling
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=conversation_history,
                    tools=self.tools_cache,
                    tool_choice="auto",
                )

                assistant_message = response.choices[0].message

                # Check if the model wants to call tools
                if assistant_message.tool_calls:
                    # Add assistant's tool call request to history
                    conversation_history.append(
                        {
                            "role": "assistant",
                            "content": assistant_message.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in assistant_message.tool_calls
                            ],
                        }
                    )

                    # Execute each tool call via MCP
                    for tool_call in assistant_message.tool_calls:
                        function_name = tool_call.function.name

                        # Track tool call
                        timer.add_tool_call(function_name)

                        try:
                            function_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError as e:
                            print(f"[ERROR] Invalid JSON in tool arguments: {e}")
                            function_args = {}

                        # Store original query for potential retry
                        original_search_query = (
                            function_args.get("query")
                            if function_name == "search_book"
                            else None
                        )
                        book_title_for_retry = None

                        # Translate book title to slug if needed
                        if "book_identifier" in function_args:
                            book_id = function_args["book_identifier"]
                            print(f"[TOOL] LLM provided book_identifier: '{book_id}'")
                            print(
                                f"[TOOL] Available mappings: {self.title_to_slug if hasattr(self, 'title_to_slug') else 'NONE'}"
                            )

                            # Try to match as title first (case-insensitive)
                            if (
                                hasattr(self, "title_to_slug")
                                and book_id.lower() in self.title_to_slug
                            ):
                                original_id = book_id
                                function_args["book_identifier"] = self.title_to_slug[
                                    book_id.lower()
                                ]
                                book_title_for_retry = (
                                    original_id  # Store title for retry context
                                )
                                print(
                                    f"[TOOL] Translated '{original_id}' -> '{function_args['book_identifier']}'"
                                )
                            else:
                                print(
                                    f"[TOOL] NO TRANSLATION - passing '{book_id}' as-is"
                                )

                        print(f"[TOOL] Calling: {function_name}({function_args})")

                        # Call MCP server (already has error handling)
                        tool_result = await self.call_mcp_tool(
                            function_name, function_args
                        )

                        # Check if search returned 0 results and attempt retry
                        if function_name == "search_book" and original_search_query:
                            results_count = self._extract_search_results_count(
                                tool_result
                            )
                            timer.set_num_results(results_count)

                            if results_count == 0:
                                print(
                                    f"[SEARCH] No results found for: '{original_search_query}'"
                                )
                                print(f"[RETRY] Attempting query rephrase...")

                                # Rephrase the query
                                rephrased_query = await self._rephrase_query(
                                    original_search_query, book_title_for_retry
                                )

                                # Retry with rephrased query
                                retry_args = function_args.copy()
                                retry_args["query"] = rephrased_query

                                print(f"[RETRY] Searching with rephrased query...")
                                retry_result = await self.call_mcp_tool(
                                    function_name, retry_args
                                )

                                retry_count = self._extract_search_results_count(
                                    retry_result
                                )

                                # Track retry in metrics
                                timer.set_retry_info(
                                    original_query=original_search_query,
                                    rephrased_query=rephrased_query,
                                    retry_results=retry_count,
                                )

                                if retry_count > 0:
                                    # Use retry result since it found something
                                    tool_result = retry_result
                                    print(
                                        f"[RETRY] Found {retry_count} results with rephrased query"
                                    )
                                else:
                                    # Both failed - mark as fallback to context
                                    timer.set_fallback_to_context(True)
                                    print(
                                        f"[RETRY] No results from retry. LLM will respond from available context."
                                    )
                                    # Keep original tool result showing 0 results
                                    # LLM will see this and respond from context
                            elif results_count > 0:
                                print(f"[SEARCH] Found {results_count} results")
                        else:
                            # Non-search tools - just show completion
                            print(f"[TOOL] Completed: {function_name}")

                        print()

                        # Add tool result to conversation with citation reminder
                        tool_content = tool_result
                        if function_name == "search_book" and results_count > 0:
                            tool_content += get_citation_reminder()

                        conversation_history.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_content,
                            }
                        )

                    # Get final response from OpenAI after tool execution
                    final_response = self.client.chat.completions.create(
                        model="gpt-4o-mini", messages=conversation_history
                    )

                    final_message = final_response.choices[0].message.content
                    conversation_history.append(
                        {"role": "assistant", "content": final_message}
                    )

                    # Store response and assess quality
                    timer.set_response(final_message)
                    score, reasoning = self.judge.assess_response(
                        user_message, final_message
                    )
                    timer.set_llm_assessment(score, reasoning)

                    return final_message, conversation_history, timer.query_id

                else:
                    # No tool calls, just return the response
                    response_text = assistant_message.content
                    conversation_history.append(
                        {"role": "assistant", "content": response_text}
                    )

                    # Store response and assess quality
                    timer.set_response(response_text)
                    score, reasoning = self.judge.assess_response(
                        user_message, response_text
                    )
                    timer.set_llm_assessment(score, reasoning)

                    return response_text, conversation_history, timer.query_id

            except Exception as e:
                error_msg = f"Error during chat: {str(e)}"
                print(f"[ERROR] {error_msg}")
                timer.set_response(error_msg)
                return (
                    error_msg,
                    conversation_history if conversation_history else [],
                    timer.query_id,
                )

    async def close(self):
        """Close the MCP session."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, "stdio_context"):
            await self.stdio_context.__aexit__(None, None, None)


async def main():
    """Test the agent."""
    import os

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        return

    agent = BookMateAgent(api_key)

    try:
        await agent.connect_to_mcp_server()

        # Test conversation
        print("\n=== Book Mate Agent ===\n")

        response, history = await agent.chat(
            "What is the book 'Meditations' about? Use the book identifier 'mma'."
        )
        print(f"Agent: {response}\n")

        response, history = await agent.chat(
            "Search for passages about 'death' in the same book.",
            conversation_history=history,
        )
        print(f"Agent: {response}\n")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
