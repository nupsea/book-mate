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
        return chat_history, "", gr.update(visible=False)

    chat_history.append([message, None])

    bot_response, query_id = await ui.chat(message, chat_history[:-1], selected_book)

    chat_history[-1][1] = bot_response

    # Store query_id for this interaction
    if query_id:
        # Use the index of the last message as key
        query_id_map[len(chat_history) - 1] = query_id

    # Show feedback buttons after response
    return chat_history, "", gr.update(visible=True, value=None)


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
                    choices=[("Select a book...", "none")] +
                            [(f"{title}", slug) for slug, title, _, _, _ in get_available_books()],
                    value="none",
                    label="Select Book (optional)",
                    info="Auto-injects book title into queries"
                )

                chatbot = gr.Chatbot(
                    height=450,
                    show_label=False,
                    avatar_images=(None, None)
                )

                with gr.Row():
                    msg = gr.Textbox(
                        placeholder="Ask about a book...",
                        show_label=False,
                        scale=9
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
                                ("★★★★★", 5)
                            ],
                            label="",
                            show_label=False
                        )
                    with gr.Column(scale=1):
                        submit_rating_btn = gr.Button("Submit", variant="primary", size="sm")

                feedback_status = gr.Textbox(visible=False, show_label=False)

                gr.Markdown("""
                **Tips:**
                - Select a book from dropdown or mention the title directly
                - Example: "What does Marcus say about virtue?"
                - Available books listed on the right
                - Rate responses to help improve the system!
                """)

            with gr.Column(scale=1):
                gr.Markdown("### Library")

                book_list = gr.Dataframe(
                    value=format_book_list(get_available_books()),
                    headers=["Slug", "Title", "Author", "Chunks", "Added"],
                    datatype=["str", "str", "str", "number", "str"],
                    interactive=False,
                    wrap=True
                )

        # Event handlers - wrap to pass ui
        async def handle_submit(msg_text, history, book_sel):
            result_history, result_msg, feedback_update = await respond(msg_text, history, book_sel, ui)
            return result_history, result_msg, feedback_update

        def handle_rating(rating, history):
            status = submit_feedback(rating, history)
            return status, gr.update(visible=False)

        msg.submit(handle_submit, [msg, chatbot, book_dropdown], [chatbot, msg, feedback_row])
        send_btn.click(handle_submit, [msg, chatbot, book_dropdown], [chatbot, msg, feedback_row])
        clear_btn.click(lambda: ([], gr.update(visible=False)), None, [chatbot, feedback_row])

        submit_rating_btn.click(
            handle_rating,
            [rating_radio, chatbot],
            [feedback_status, feedback_row]
        )

    return book_dropdown, book_list
