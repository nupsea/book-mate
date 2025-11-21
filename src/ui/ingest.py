"""
Book ingestion interface component.
"""

import gradio as gr
from pathlib import Path
from src.flows.book_ingest import ingest_book
from src.ui.utils import (
    validate_slug,
    extract_chapter_info_from_chunks,
    format_book_list,
    get_available_books,
    delete_book,
)
from src.ui.pattern_builder import build_pattern_from_example, validate_pattern_on_file


def test_chapter_pattern(file, chapter_example: str):
    """Test pattern on uploaded file before ingestion."""
    if not file:
        return "Please upload a file first"

    if not chapter_example.strip():
        return "Please provide a chapter example (e.g., 'CHAPTER 2' or 'BOOK II')"

    try:
        file_path = Path(file.name)

        # Build pattern from example
        pattern, desc = build_pattern_from_example(chapter_example)

        if not pattern:
            return f"Could not build pattern: {desc}"

        # Validate against file
        success, message, matches = validate_pattern_on_file(pattern, str(file_path))

        output = f"Example: '{chapter_example}'\n"
        output += f"Generated pattern: {pattern}\n"
        output += f"Description: {desc}\n\n"

        if success:
            output += f"[SUCCESS] {message}\n\n"
            output += "Sample matches:\n"
            for i, (line_num, text) in enumerate(matches[:5], 1):
                output += f"  {i}. Line {line_num}: {text[:60]}\n"
            output += "\nPattern looks good! You can proceed with ingestion."
        else:
            output += f"[FAILED] {message}\n\n"
            output += "Please try a different example or check your file format."

        return output

    except Exception as e:
        return f"Error testing pattern: {str(e)}"


async def ingest_new_book(
    file,
    title: str,
    author: str,
    slug: str,
    skip_chapters: bool,
    chapter_example: str,
    force_update: bool,
):
    """Handle book ingestion from UI."""
    if not file:
        return {
            "output": "Error: Please upload a file",
            "status": "[ERROR] Error",
            "clear_inputs": False,
        }

    if not title.strip():
        return {
            "output": "Error: Please provide a book title",
            "status": "[ERROR] Error",
            "clear_inputs": False,
        }

    slug = slug.strip().lower()

    if not slug:
        return {
            "output": "Error: Please provide a slug",
            "status": "[ERROR] Error",
            "clear_inputs": False,
        }

    if not skip_chapters and not chapter_example.strip():
        return {
            "output": "Error: Please provide a chapter example or enable 'Skip chapter detection'",
            "status": "[ERROR] Error",
            "clear_inputs": False,
        }

    # Validate slug (skip duplicate check if force_update is enabled)
    if not force_update:
        is_valid, error_msg = validate_slug(slug)
        if not is_valid:
            return {
                "output": f"Error: {error_msg}",
                "status": "[ERROR] Error",
                "clear_inputs": False,
            }

    try:
        file_path = Path(file.name)

        # Handle pattern building or skip
        if skip_chapters:
            pattern = None
            output = "[SKIP] Chapter detection disabled - using automatic chunking\n\n"
        else:
            # Build pattern from example
            pattern, desc = build_pattern_from_example(chapter_example)
            output = f"Building pattern from example: '{chapter_example}'\n"
            output += f"Generated pattern: {pattern}\n"
            output += f"Description: {desc}\n\n"

            if not pattern:
                return {
                    "output": output + f"Error: {desc}",
                    "status": "[ERROR] Pattern Error",
                    "clear_inputs": False,
                }

            # Validate pattern
            success, message, matches = validate_pattern_on_file(
                pattern, str(file_path)
            )
            output += f"Pattern validation: {message}\n\n"

            if not success:
                return {
                    "output": output
                    + "Pattern validation failed. Please try a different example.",
                    "status": "[ERROR] Validation Failed",
                    "clear_inputs": False,
                }

        output += "[RUNNING] Starting ingestion...\n"

        # Run ingestion
        result = await ingest_book(
            slug=slug,
            file_path=str(file_path),
            title=title,
            author=author or None,
            split_pattern=pattern,
            force_update=force_update,
        )

        output += "\n[SUCCESS] Book ingested:\n"
        output += f"- Slug: {result['slug']}\n"
        output += f"- Title: {result['title']}\n"
        output += f"- Chapters: {result['chapters']}\n"
        output += f"- Chunks: {result['chunks']}\n"
        output += f"- Search indexed: {result['search_indexed']}\n\n"

        # Analyze chunks to verify chapter detection
        output += "Analyzing indexed chunks...\n"
        chunk_info = extract_chapter_info_from_chunks(slug)

        chapter_detail = ""
        if chunk_info["status"] == "success":
            output += f"- Total chapters detected: {chunk_info['total_chapters']}\n"
            output += f"- Total chunks indexed: {chunk_info['total_chunks']}\n"
            output += f"- Chapter range: {chunk_info['chapter_range']}\n"
            output += f"- First chunk ID: {chunk_info['first_chunk']}\n"
            output += f"- Last chunk ID: {chunk_info['last_chunk']}\n\n"

            if chunk_info["total_chapters"] == result["chapters"]:
                output += "[OK] Chapter count matches! Ingestion successful."
                chapter_detail = f"Chapters: {', '.join(chunk_info['chapters'])}"
            else:
                output += "[WARNING] Chapter count mismatch!\n"
                output += f"Expected: {result['chapters']}, Found in index: {chunk_info['total_chapters']}"
                chapter_detail = f"Mismatch: {chunk_info['total_chapters']} chapters"
        else:
            output += f"[ERROR] Error analyzing chunks: {chunk_info['message']}"
            chapter_detail = "Analysis failed"

        return {
            "output": output,
            "status": f"[COMPLETE] Ingestion Complete ({result['chapters']} chapters, {result['chunks']} chunks)",
            "chapter_detail": chapter_detail,
            "clear_inputs": True,
        }

    except Exception as e:
        return {
            "output": f"[ERROR] Error during ingestion: {str(e)}",
            "status": "[ERROR] Ingestion Failed",
            "clear_inputs": False,
        }


def create_ingest_interface():
    """Create the book ingestion tab interface."""
    from datetime import datetime

    with gr.Column():
        gr.Markdown("### Upload and Index a New Book")

        with gr.Row():
            with gr.Column(scale=2):
                file_upload = gr.File(
                    label="Upload Book File (.txt or .pdf)", file_types=[".txt", ".pdf"]
                )

                title_input = gr.Textbox(
                    label="Book Title", placeholder="The Meditations", info="Required"
                )

                author_input = gr.Textbox(
                    label="Author", placeholder="Marcus Aurelius", info="Optional"
                )

                slug_input = gr.Textbox(
                    label="Book Slug (unique identifier)",
                    placeholder="mma",
                    info="2-20 chars, lowercase, letters/numbers/-/_ only",
                    max_lines=1,
                )

                skip_chapters_check = gr.Checkbox(
                    label="Skip chapter detection (use auto-chunking)",
                    value=False,
                    info="Enable if book has no clear chapters or complex structure",
                )

                chapter_example_input = gr.Textbox(
                    label="Chapter Pattern Example",
                    placeholder="e.g., CHAPTER I. or II. or BOOK II",
                    info="Enter any chapter heading from your book, then test pattern. Examples: 'CHAPTER I.', 'BOOK II', 'II.'",
                    lines=1,
                    visible=True,
                )

                test_pattern_btn = gr.Button("Test Pattern", size="sm", visible=True)

                pattern_test_output = gr.Textbox(
                    label="Pattern Test Results",
                    lines=6,
                    interactive=False,
                    visible=True,
                )

                nested_structure_note = gr.Markdown(
                    """
                **Note:** For nested structures (PART > CHAPTER), use the higher level pattern (e.g., `PART I.` instead of `CHAPTER I.`)
                """,
                    visible=True,
                )

                force_update_check = gr.Checkbox(
                    label="Force update if slug exists",
                    value=False,
                    info="Overwrite existing book",
                )

                ingest_btn = gr.Button("Ingest Book", variant="primary", size="lg")

            with gr.Column(scale=1):
                gr.Markdown("### Current Library")

                library_timestamp = gr.Textbox(
                    value=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    lines=1,
                    interactive=False,
                    show_label=False,
                )

                book_list_display = gr.Dataframe(
                    headers=["Slug", "Title", "Author", "Chunks", "Added"],
                    datatype=["str", "str", "str", "number", "str"],
                    interactive=False,
                    wrap=True,
                    column_widths=["15%", "25%", "20%", "12%", "28%"],
                    max_height=800,
                )

                gr.Markdown("#### Delete Book")

                delete_slug_input = gr.Textbox(
                    label="Book Slug to Delete",
                    placeholder="Enter slug (e.g., mma)",
                    lines=1,
                )

                delete_output = gr.Textbox(
                    label="Delete Status", lines=4, interactive=False
                )

                delete_btn = gr.Button(
                    "Confirm Delete", variant="stop", size="sm", visible=False
                )

        # Status indicator
        status_display = gr.Textbox(
            label="Status", value="Ready", lines=1, interactive=False
        )

        ingest_output = gr.Textbox(label="Ingestion Log", lines=12, interactive=False)

        chapter_info = gr.Textbox(
            label="Chapter Verification", lines=2, interactive=False
        )

        # Event handlers

        # Toggle chapter pattern fields visibility based on skip_chapters checkbox
        def toggle_chapter_fields(skip_chapters):
            visible = not skip_chapters
            return (
                gr.update(visible=visible),  # chapter_example_input
                gr.update(visible=visible),  # test_pattern_btn
                gr.update(visible=visible),  # pattern_test_output
                gr.update(visible=visible),  # nested_structure_note
            )

        skip_chapters_check.change(
            toggle_chapter_fields,
            [skip_chapters_check],
            [
                chapter_example_input,
                test_pattern_btn,
                pattern_test_output,
                nested_structure_note,
            ],
        )

        test_pattern_btn.click(
            test_chapter_pattern,
            [file_upload, chapter_example_input],
            pattern_test_output,
        )

        async def handle_ingest(
            file, title, author, slug, skip_chap, chapter_ex, force
        ):
            result = await ingest_new_book(
                file, title, author, slug, skip_chap, chapter_ex, force
            )

            # Refresh library list with timestamp
            new_list = format_book_list(get_available_books())
            new_timestamp = (
                f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Clear inputs if successful
            if result["clear_inputs"]:
                return (
                    result["output"],
                    result["status"],
                    result.get("chapter_detail", ""),
                    None,  # Clear file
                    "",  # Clear title
                    "",  # Clear author
                    "",  # Clear slug
                    "",  # Clear chapter example
                    "",  # Clear pattern test
                    new_list,
                    new_timestamp,
                )
            else:
                return (
                    result["output"],
                    result["status"],
                    result.get("chapter_detail", ""),
                    gr.update(),  # Keep file
                    gr.update(),  # Keep title
                    gr.update(),  # Keep author
                    gr.update(),  # Keep slug
                    gr.update(),  # Keep chapter example
                    gr.update(),  # Keep pattern test
                    new_list,
                    new_timestamp,
                )

        ingest_btn.click(
            handle_ingest,
            [
                file_upload,
                title_input,
                author_input,
                slug_input,
                skip_chapters_check,
                chapter_example_input,
                force_update_check,
            ],
            [
                ingest_output,
                status_display,
                chapter_info,
                file_upload,
                title_input,
                author_input,
                slug_input,
                chapter_example_input,
                pattern_test_output,
                book_list_display,
                library_timestamp,
            ],
        )

        # Delete book handler with confirmation state
        delete_pending_slug = gr.State(None)

        def request_delete_confirmation(slug):
            """First step: show confirmation message"""
            slug = slug.strip().lower()

            if not slug:
                return (
                    "[ERROR] Please enter a book slug",
                    None,  # No pending slug
                    gr.update(visible=False),  # Hide confirm button
                )

            # Get book info
            books = get_available_books()
            book_info = next((b for b in books if b[0] == slug), None)

            if not book_info:
                return (
                    f"[ERROR] Book '{slug}' not found",
                    None,
                    gr.update(visible=False),
                )

            book_slug, book_title, book_author, num_chunks, _ = book_info
            author_str = f" by {book_author}" if book_author else ""

            confirm_msg = (
                f"[CONFIRM?] Delete '{book_title}'{author_str}? ({num_chunks} chunks)\n"
            )
            confirm_msg += "This action cannot be undone.\n\n"
            confirm_msg += "Click 'Confirm Delete' button below to proceed."

            return (
                confirm_msg,
                slug,  # Store slug for confirmation
                gr.update(visible=True),  # Show confirm button
            )

        def confirm_delete(pending_slug):
            """Second step: actually delete after confirmation"""
            if not pending_slug:
                return (
                    "[ERROR] No deletion pending",
                    gr.update(),
                    gr.update(),
                    "",
                    None,
                    gr.update(visible=False),
                )

            output = f"Deleting book '{pending_slug}'...\n\n"
            success, message, chunks_deleted = delete_book(pending_slug)

            # Always refresh book list after deletion attempt
            new_list = format_book_list(get_available_books())
            new_timestamp = (
                f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            return (
                output + message,
                new_list,
                new_timestamp,
                "",  # Clear slug input
                None,  # Clear pending slug
                gr.update(visible=False),  # Hide confirm button
            )

        delete_slug_input.change(
            request_delete_confirmation,
            [delete_slug_input],
            [delete_output, delete_pending_slug, delete_btn],
        )

        delete_btn.click(
            confirm_delete,
            [delete_pending_slug],
            [
                delete_output,
                book_list_display,
                library_timestamp,
                delete_slug_input,
                delete_pending_slug,
                delete_btn,
            ],
        )

    return book_list_display
