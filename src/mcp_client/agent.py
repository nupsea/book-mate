"""
MCP Client using OpenAI for function calling.
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI


class BookMateAgent:
    def __init__(self, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        self.session: ClientSession | None = None
        self.tools_cache = []
        self.read_stream = None
        self.write_stream = None

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
        """Execute a tool call via MCP server."""
        result = await self.session.call_tool(tool_name, arguments)
        # Combine all text content from the response
        return "\n".join([item.text for item in result.content if hasattr(item, 'text')])

    async def chat(self, user_message: str, conversation_history: list = None) -> tuple[str, list]:
        """
        Send a message and handle tool calls automatically.

        Returns:
            (assistant_response, updated_conversation_history)
        """
        if conversation_history is None:
            conversation_history = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful book assistant. When searching books, analyze and synthesize "
                        "the passages to provide meaningful insights. Don't just list the results - explain "
                        "what they reveal about the topic, identify key themes, and connect ideas across passages. "
                        "Be thoughtful and analytical in your responses."
                    )
                }
            ]

        # Add user message
        conversation_history.append({"role": "user", "content": user_message})

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
                function_args = json.loads(tool_call.function.arguments)

                print(f"[TOOL] Calling: {function_name}({function_args})")

                # Call MCP server
                tool_result = await self.call_mcp_tool(function_name, function_args)

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

            return final_message, conversation_history

        else:
            # No tool calls, just return the response
            conversation_history.append({"role": "assistant", "content":
assistant_message.content})
            return assistant_message.content, conversation_history

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
