"""
Tool handlers for book-related MCP operations.

Separates business logic from MCP protocol definitions.
"""

import logging
from mcp.types import TextContent

from src.flows.book_query import (
    search_book_content,
    get_book_summary,
    get_chapter_summaries,
)

logger = logging.getLogger(__name__)


class BookToolHandlers:
    """Handles all book-related tool requests."""

    def handle_search_book(self, arguments: dict) -> list[TextContent]:
        """
        Handle single-book search requests.

        Args:
            arguments: Dict with 'query', 'book_identifier', 'limit' (optional)

        Returns:
            List of TextContent with formatted search results
        """
        result = search_book_content(
            query=arguments["query"],
            book_identifier=arguments["book_identifier"],
            limit=arguments.get("limit", 5),
        )

        # Debug logging
        logger.debug(
            f"Search result for '{arguments['query']}' in '{arguments['book_identifier']}':"
        )
        logger.debug(f"  - num_results: {result['num_results']}")
        logger.debug(f"  - chunk_ids: {result.get('chunk_ids', [])}")
        logger.debug(f"  - error: {result.get('error', 'None')}")

        # Format results as readable text
        if result.get("error"):
            return [TextContent(type="text", text=f"Error: {result['error']}")]

        if result["num_results"] == 0:
            output = (
                f"No results found for '{result['query']}' in book '{result['book']}'."
            )
        else:
            output = (
                f"Found {result['num_results']} results for '{result['query']}' in {result['book']}:\n\n"
            )
            for i, chunk in enumerate(result["chunks"], 1):
                chunk_id = chunk.get("id", "unknown")

                # Extract chapter number from chunk_id (format: slug_chapter_chunk_hash)
                chapter_num = "?"
                if "_" in chunk_id:
                    parts = chunk_id.split("_")
                    if len(parts) >= 2:
                        chapter_num = (
                            parts[1].lstrip("0") or "0"
                        )  # Remove leading zeros

                # Format citation
                citation = f"[Chapter {chapter_num}, Source: {chunk_id}]"

                output += f"Passage {i} {citation}:\n{chunk['text']}\n\n---\n\n"

        return [TextContent(type="text", text=output)]

    def handle_get_book_summary(self, arguments: dict) -> list[TextContent]:
        """
        Handle book summary requests.

        Args:
            arguments: Dict with 'book_identifier'

        Returns:
            List of TextContent with book summary
        """
        result = get_book_summary(arguments["book_identifier"])
        return [
            TextContent(type="text", text=result["summary"] or "No summary available")
        ]

    def handle_get_chapter_summaries(self, arguments: dict) -> list[TextContent]:
        """
        Handle chapter summaries requests.

        Args:
            arguments: Dict with 'book_identifier'

        Returns:
            List of TextContent with all chapter summaries
        """
        result = get_chapter_summaries(arguments["book_identifier"])

        output = f"Found {result['num_chapters']} chapters:\n\n"
        for ch in result["chapters"]:
            output += f"Chapter {ch['chapter_id']}:\n{ch['summary']}\n\n"

        return [TextContent(type="text", text=output)]

    def handle_search_multiple_books(self, arguments: dict) -> list[TextContent]:
        """
        Handle multi-book comparative search requests.

        Args:
            arguments: Dict with:
                - 'query': Search query to use across all books
                - 'book_identifiers': List of book titles to search
                - 'limit_per_book': Optional, number of results per book (default: 3)

        Returns:
            List of TextContent with formatted comparative results
        """
        query = arguments["query"]
        book_identifiers = arguments["book_identifiers"]
        limit_per_book = arguments.get("limit_per_book", 3)

        logger.info(
            f"Multi-book search: '{query}' across {len(book_identifiers)} books"
        )

        # Collect results from each book sequentially (thread-safe)
        all_results = []
        total_found = 0

        for book_id in book_identifiers:
            # Reuse existing search function
            result = search_book_content(
                query=query, book_identifier=book_id, limit=limit_per_book
            )

            # Track how many results we found
            num_results = result.get("num_results", 0)
            total_found += num_results

            logger.debug(f"  - {book_id}: {num_results} results")

            # Store result with book info for formatting
            all_results.append({"book": book_id, "result": result})

        # Format combined output with clear book separation
        if total_found == 0:
            output = f"Found 0 results for '{query}' in any of the {len(book_identifiers)} books searched."
        else:
            output = f"Found {total_found} results - Comparative search for '{query}' across {len(book_identifiers)} books:\n\n"
            output += "=" * 80 + "\n\n"

            for book_data in all_results:
                book_id = book_data["book"]
                result = book_data["result"]

                # Book header
                output += f"### {book_id.upper()} ###\n\n"

                if result.get("error"):
                    output += f"Error: {result['error']}\n\n"
                elif result["num_results"] == 0:
                    output += "No results found in this book.\n\n"
                else:
                    # Format passages for this book
                    for i, chunk in enumerate(result["chunks"], 1):
                        chunk_id = chunk.get("id", "unknown")

                        # Extract chapter number
                        chapter_num = "?"
                        if "_" in chunk_id:
                            parts = chunk_id.split("_")
                            if len(parts) >= 2:
                                chapter_num = parts[1].lstrip("0") or "0"

                        citation = f"[Chapter {chapter_num}, Source: {chunk_id}]"
                        output += f"Passage {i} {citation}:\n{chunk['text']}\n\n"

                output += "-" * 80 + "\n\n"

        return [TextContent(type="text", text=output)]

    def dispatch(self, tool_name: str, arguments: dict) -> list[TextContent]:
        """
        Dispatch tool call to the appropriate handler method.

        Uses reflection to find handler method by name convention:
        Tool 'search_book' -> method 'handle_search_book'

        Args:
            tool_name: Name of the tool to invoke
            arguments: Arguments passed to the tool

        Returns:
            List of TextContent with tool results or error message
        """
        handler_method_name = f"handle_{tool_name}"
        handler = getattr(self, handler_method_name, None)

        if handler and callable(handler):
            logger.debug(f"Dispatching to {handler_method_name}")
            return handler(arguments)
        else:
            logger.error(f"Unknown tool: {tool_name}")
            return [TextContent(type="text", text=f"Unknown tool: {tool_name}")]
