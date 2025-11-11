"""
Chat interface component.
"""

import gradio as gr
import asyncio
from src.ui.utils import get_available_books, format_book_list
from src.monitoring.metrics import metrics_collector


# Store query_id for each chat turn (message index -> query_id)
query_id_map = {}


async def respond(message, chat_history, selected_book, ui):
    """Handle chat interactions."""
    if not message.strip():
        yield chat_history, message, gr.update(visible=False)
        return

    # Add user message with loading indicator for bot
    chat_history.append([message, "Thinking..."])

    # Keep message in textbox during processing
    yield chat_history, message, gr.update(visible=False)

    # Get bot response
    bot_response, query_id = await ui.chat(message, chat_history[:-1], selected_book)

    # Update with actual response
    chat_history[-1][1] = bot_response

    # Store query_id for this interaction
    if query_id:
        query_id_map[len(chat_history) - 1] = query_id

    # Clear textbox and show feedback buttons
    yield chat_history, "", gr.update(visible=True, value=None)


def submit_feedback(rating, chat_history):
    """Submit user feedback for the last bot response."""
    if not chat_history or rating is None:
        return gr.update(visible=False)

    # Get query_id for last message
    last_idx = len(chat_history) - 1
    query_id = query_id_map.get(last_idx)

    if query_id:
        metrics_collector.update_user_feedback(query_id, rating)
        return gr.update(visible=False, value="Thanks for your feedback!")

    return gr.update(visible=False)


def create_chat_interface(ui):
    """Create the chat tab interface."""

    with gr.Column():
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### Chat with Books")

                book_dropdown = gr.Dropdown(
                    choices=[("Select a book...", "none")]
                    + [
                        (f"{title}", slug)
                        for slug, title, _, _, _ in get_available_books()
                    ],
                    value="none",
                    label="Select Book (optional)",
                    info="Auto-injects book title into queries",
                )

                chatbot = gr.Chatbot(
                    height=450, show_label=False, avatar_images=(None, None)
                )

                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask about a book...", show_label=False, scale=9
                    )
                    send_btn = gr.Button("Send", scale=1, variant="primary")

                with gr.Row():
                    clear_btn = gr.Button("Clear Conversation")

                # Feedback section - compact single row
                with gr.Row(visible=False) as feedback_row:
                    with gr.Column(scale=1):
                        gr.Markdown("**Rate:**")
                    with gr.Column(scale=6):
                        rating_radio = gr.Radio(
                            choices=[
                                ("★", 1),
                                ("★★", 2),
                                ("★★★", 3),
                                ("★★★★", 4),
                                ("★★★★★", 5),
                            ],
                            label="",
                            show_label=False,
                        )
                    with gr.Column(scale=1):
                        submit_rating_btn = gr.Button(
                            "Submit", variant="primary", size="sm"
                        )

                feedback_status = gr.Textbox(visible=False, show_label=False)

                gr.Markdown(
                    """
                    ### Tips
                    - **Book Selection**: Use dropdown or mention book title in your query
                    - **Search Examples**: "Find passages about virtue", "What does the author say about courage?"
                    - **Chapter Context**: Ask about specific chapters or broad themes
                    - **Hybrid Search**: Uses both keyword matching (BM25) and semantic search
                    - **Rate Responses**: Help improve quality by rating answers
                    """
                )

            with gr.Column(scale=1, min_width=300):
                gr.Markdown("### Library")

                book_list = gr.Dataframe(
                    headers=["Slug", "Title", "Author", "Chunks", "Added"],
                    datatype=["str", "str", "str", "number", "str"],
                    interactive=False,
                    wrap=True,
                    column_widths=["15%", "25%", "20%", "12%", "28%"],
                    max_height=800,
                )

        # Event handlers - wrap to pass ui
        async def handle_submit(msg_text, history, book_sel):
            async for result_history, result_msg, feedback_update in respond(
                msg_text, history, book_sel, ui
            ):
                yield result_history, result_msg, feedback_update

        def handle_rating(rating, history):
            status = submit_feedback(rating, history)
            return status, gr.update(visible=False)

        msg.submit(
            handle_submit, [msg, chatbot, book_dropdown], [chatbot, msg, feedback_row]
        )
        send_btn.click(
            handle_submit, [msg, chatbot, book_dropdown], [chatbot, msg, feedback_row]
        )
        clear_btn.click(
            lambda: ([], gr.update(visible=False)), None, [chatbot, feedback_row]
        )

        submit_rating_btn.click(
            handle_rating, [rating_radio, chatbot], [feedback_status, feedback_row]
        )

        # Load book list on page load
        def load_book_list():
            return format_book_list(get_available_books())

    return book_dropdown, book_list, load_book_list
