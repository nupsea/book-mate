from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

from src.flows.book_query import (
    search_book_content,
    get_book_summary,
    get_chapter_summaries
    # validate_book_exists
)

app = Server("book-mate-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_book",
            description="Search for content within a book using hybrid (BM25 + Vector) retrieval. Returns relevant text chunks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "book_identifier": {
                        "type": "string",
                        "description": "The full book title exactly as provided in the available books list (e.g., 'The Meditations', 'The Odyssey', 'Alice\\'s Adventures in Wonderland')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5
                    }
                },
                "required": ["query", "book_identifier"]
            }
        ),
        Tool(
            name="get_book_summary",
            description="Get the overall summary of a book.",
            inputSchema={
                "type": "object",
                "properties": {
                    "book_identifier": {
                        "type": "string",
                        "description": "The full book title exactly as provided in the available books list (e.g., 'The Meditations', 'The Odyssey', 'Alice\\'s Adventures in Wonderland')"
                    }
                },
                "required": ["book_identifier"]
            }
        ),
        Tool(
            name="get_chapter_summaries",
            description="Get summaries of all chapters in a book.",
            inputSchema={
                "type": "object",
                "properties": {
                    "book_identifier": {
                        "type": "string",
                        "description": "The full book title exactly as provided in the available books list (e.g., 'The Meditations', 'The Odyssey', 'Alice\\'s Adventures in Wonderland')"
                    }
                },
                "required": ["book_identifier"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "search_book":
        result = search_book_content(
            query=arguments["query"],
            book_identifier=arguments["book_identifier"],
            limit=arguments.get("limit", 5)
        )

        # Debug print
        print(f"\n[DEBUG] Search result for '{arguments['query']}' in '{arguments['book_identifier']}':")
        print(f"  - num_results: {result['num_results']}")
        print(f"  - chunk_ids: {result.get('chunk_ids', [])}")
        print(f"  - error: {result.get('error', 'None')}\n")

        # Format results as readable text
        if result.get("error"):
            return [TextContent(type="text", text=f"Error: {result['error']}")]

        if result['num_results'] == 0:
            output = f"No results found for '{result['query']}' in book '{result['book']}'."
        else:
            output = f"Search results for '{result['query']}' in {result['book']}:\n\n"
            for i, chunk in enumerate(result['chunks'], 1):
                output += f"Passage {i}:\n{chunk['text']}\n\n---\n\n"

        return [TextContent(type="text", text=output)]

    elif name == "get_book_summary":
        result = get_book_summary(arguments["book_identifier"])
        return [TextContent(type="text", text=result["summary"] or "No summary available")]

    elif name == "get_chapter_summaries":
        result = get_chapter_summaries(arguments["book_identifier"])

        output = f"Found {result['num_chapters']} chapters:\n\n"
        for ch in result['chapters']:
            output += f"Chapter {ch['chapter_id']}:\n{ch['summary']}\n\n"

        return [TextContent(type="text", text=output)]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server using stdio transport."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())