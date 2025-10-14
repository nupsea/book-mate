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
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", "-m", "src.mcp_server.book_tools"],
            env=None
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

        print(f"Connected to MCP server. Available tools: {[t['function']['name'] for t in self.tools_cache]}")

    def _convert_mcp_tools_to_openai(self, mcp_tools) -> list[dict]:
        """Convert MCP tool format to OpenAI function calling format."""
        openai_tools = []
        for tool in mcp_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            })
        return openai_tools

    async def call_mcp_tool(self, tool_name: str, arguments: dict) -> str:
        """Execute a tool call via MCP server with error handling."""
        try:
            if not self.session:
                raise RuntimeError("MCP session not initialized. Call connect_to_mcp_server() first.")

            result = await self.session.call_tool(tool_name, arguments)
            # Combine all text content from the response
            text_content = "\n".join([item.text for item in result.content if hasattr(item, 'text')])

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
            book_list = "\n".join([
                f"- {title}" + (f" by {author}" if author else "")
                for slug, title, author in books
            ])

            # Create mapping for internal use
            title_to_slug = {
                title.lower(): slug for slug, title, _ in books
            }

            return f"Available books:\n{book_list}", title_to_slug
        except Exception as e:
            print(f"[WARN] Could not load book list: {e}")
            return "Book list unavailable.", {}

    async def chat(self, user_message: str, conversation_history: list = None) -> tuple[str, list, str]:
        """
        Send a message and handle tool calls automatically.

        Returns:
            (assistant_response, updated_conversation_history, query_id)
        """
        print(f"\n{'='*80}")
        print(f"[CHAT] NEW REQUEST")
        print(f"[CHAT] User message: {user_message}")
        print(f"[CHAT] Conversation history length: {len(conversation_history) if conversation_history else 0}")
        print(f"{'='*80}\n")

        # Start monitoring
        with QueryTimer(user_message, None) as timer:
            try:
                if not self.session:
                    raise RuntimeError("MCP session not initialized. Call connect_to_mcp_server() first.")

                if not user_message or not user_message.strip():
                    raise ValueError("User message cannot be empty.")

                # Check if this is a new conversation (None or empty list)
                if not conversation_history:
                    # Dynamically get available books
                    available_books, self.title_to_slug = self._get_available_books()

                    print(f"[CHAT] Creating NEW conversation")
                    print(f"[CHAT] Title-to-slug mapping: {self.title_to_slug}")
                    print(f"[CHAT] Available books shown to LLM:\n{available_books}\n")

                    conversation_history = [
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful book assistant with access to book summaries and search tools. "
                                "When searching books, analyze and synthesize the passages to provide meaningful insights. "
                                "Don't just list results - explain what they reveal, identify themes, and connect ideas.\n\n"
                                f"CRITICAL RULES:\n"
                                f"1. ALWAYS use the provided tools to get information - NEVER make up or hallucinate book content\n"
                                f"2. If asked about a book's plot/summary, you MUST call get_book_summary tool\n"
                                f"3. If asked to search for specific content, you MUST call search_book tool\n"
                                f"4. For tool parameters, use the exact book title as the book_identifier\n"
                                f"5. If no data exists in tools, clearly state you don't have that information - DO NOT fabricate\n\n"
                                f"{available_books}\n\n"
                                f"Remember: Always call tools first, never answer from your training data."
                            )
                        }
                    ]
                else:
                    print(f"[CHAT] CONTINUING conversation with {len(conversation_history)} messages")
                    # For continuing conversations, use existing mapping
                    if not hasattr(self, 'title_to_slug'):
                        _, self.title_to_slug = self._get_available_books()
                    print(f"[CHAT] Title-to-slug mapping: {self.title_to_slug}")

                # Add user message
                conversation_history.append({"role": "user", "content": user_message})

                print(f"[CHAT] Full conversation being sent to LLM:")
                for i, msg in enumerate(conversation_history):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    if role == 'system':
                        print(f"  [{i}] SYSTEM: {content[:200]}...")
                    elif role == 'user':
                        print(f"  [{i}] USER: {content}")
                    elif role == 'assistant':
                        print(f"  [{i}] ASSISTANT: {content[:100] if content else '<tool_calls>'}")
                    elif role == 'tool':
                        print(f"  [{i}] TOOL: {content[:100]}...")
                print()

                # Call OpenAI with function calling
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=conversation_history,
                    tools=self.tools_cache,
                    tool_choice="auto"
                )

                assistant_message = response.choices[0].message

                # Check if the model wants to call tools
                if assistant_message.tool_calls:
                    # Add assistant's tool call request to history
                    conversation_history.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })

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

                        # Translate book title to slug if needed
                        if "book_identifier" in function_args:
                            book_id = function_args["book_identifier"]
                            print(f"[TOOL] LLM provided book_identifier: '{book_id}'")
                            print(f"[TOOL] Available mappings: {self.title_to_slug if hasattr(self, 'title_to_slug') else 'NONE'}")

                            # Try to match as title first (case-insensitive)
                            if hasattr(self, 'title_to_slug') and book_id.lower() in self.title_to_slug:
                                original_id = book_id
                                function_args["book_identifier"] = self.title_to_slug[book_id.lower()]
                                print(f"[TOOL] ✓ Translated '{original_id}' → '{function_args['book_identifier']}'")
                            else:
                                print(f"[TOOL] ✗ NO TRANSLATION - passing '{book_id}' as-is")

                        print(f"[TOOL] Calling: {function_name}({function_args})")

                        # Call MCP server (already has error handling)
                        tool_result = await self.call_mcp_tool(function_name, function_args)

                        print(f"[TOOL] Result length: {len(tool_result)} chars")
                        print(f"[TOOL] Result preview: {tool_result[:200]}...")
                        print()

                        # Add tool result to conversation
                        conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        })

                    # Get final response from OpenAI after tool execution
                    final_response = self.client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=conversation_history
                    )

                    final_message = final_response.choices[0].message.content
                    conversation_history.append({"role": "assistant", "content": final_message})

                    # Store response and assess quality
                    timer.set_response(final_message)
                    score, reasoning = self.judge.assess_response(user_message, final_message)
                    timer.set_llm_assessment(score, reasoning)

                    return final_message, conversation_history, timer.query_id

                else:
                    # No tool calls, just return the response
                    response_text = assistant_message.content
                    conversation_history.append({"role": "assistant", "content": response_text})

                    # Store response and assess quality
                    timer.set_response(response_text)
                    score, reasoning = self.judge.assess_response(user_message, response_text)
                    timer.set_llm_assessment(score, reasoning)

                    return response_text, conversation_history, timer.query_id

            except Exception as e:
                error_msg = f"Error during chat: {str(e)}"
                print(f"[ERROR] {error_msg}")
                timer.set_response(error_msg)
                return error_msg, conversation_history if conversation_history else [], timer.query_id

    async def close(self):
        """Close the MCP session."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'stdio_context'):
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
            conversation_history=history
        )
        print(f"Agent: {response}\n")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
