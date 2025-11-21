import logging
import sys
import os

# CRITICAL: Configure logging BEFORE any other imports to prevent stdout pollution
# MCP protocol requires stdout to be reserved exclusively for JSON-RPC messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)

# Suppress third-party library logging that might output to stdout
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)

# Disable transformers progress bars and verbosity
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Now safe to import other modules
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

from src.mcp_server.tool_handlers import BookToolHandlers

logger = logging.getLogger(__name__)
app = Server("book-mate-server")

# Initialize tool handlers
tool_handlers = BookToolHandlers()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_book",
            description="Search for content within a book using hybrid (BM25 + Vector) retrieval. Returns relevant text chunks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "book_identifier": {
                        "type": "string",
                        "description": "The book SLUG from the available books list (e.g., 'abc', 'xyz'). MUST use the slug shown in [square brackets], NOT the full title.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5,
                    },
                },
                "required": ["query", "book_identifier"],
            },
        ),
        Tool(
            name="get_book_summary",
            description="Get the overall summary of a book.",
            inputSchema={
                "type": "object",
                "properties": {
                    "book_identifier": {
                        "type": "string",
                        "description": "The book SLUG from the available books list (e.g., 'abc', 'xyz'). MUST use the slug shown in [square brackets], NOT the full title.",
                    }
                },
                "required": ["book_identifier"],
            },
        ),
        Tool(
            name="get_chapter_summaries",
            description="Get summaries of all chapters in a book.",
            inputSchema={
                "type": "object",
                "properties": {
                    "book_identifier": {
                        "type": "string",
                        "description": "The book SLUG from the available books list (e.g., 'abc', 'xyz'). MUST use the slug shown in [square brackets], NOT the full title.",
                    }
                },
                "required": ["book_identifier"],
            },
        ),
        Tool(
            name="search_multiple_books",
            description="Search across multiple books simultaneously for comparative analysis. Use this when you need to compare themes, concepts, perspectives, or topics across different authors or works. Returns relevant passages from each book with clear source attribution. TIP: Use concrete, specific search terms for best results. If no results found, consider getting book summaries instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to use across all books. Use specific, concrete terms rather than abstract concepts. For better results with comparative questions, include multiple related terms separated by spaces (e.g., 'concept1 concept2 term1 term2' instead of just 'concept1')"
                    },
                    "book_identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 2-5 book SLUGS to search and compare (e.g., ['abc', 'xyz']). MUST use slugs from [square brackets], NOT titles.",
                        "minItems": 2,
                        "maxItems": 5
                    },
                    "limit_per_book": {
                        "type": "integer",
                        "description": "Number of results to return from each book",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 5
                    }
                },
                "required": ["query", "book_identifiers"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    MCP tool call handler - dispatches to appropriate handler method.

    This is a thin wrapper that delegates all business logic to the
    BookToolHandlers class for better modularity and testability.
    """
    return tool_handlers.dispatch(name, arguments)


async def main():
    """Run the MCP server using stdio transport."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
