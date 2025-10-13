"""
Chat interface component.
"""
import gradio as gr
import asyncio
from src.ui.utils import get_available_books, format_book_list


async def respond(message, chat_history, selected_book, ui):
    """Handle chat interactions."""
    if not message.strip():
        return chat_history, ""

    chat_history.append([message, None])

    bot_response = await ui.chat(message, chat_history[:-1], selected_book)

    chat_history[-1][1] = bot_response

    return chat_history, ""


def create_chat_interface(ui):
    """Create the chat tab interface."""

    with gr.Column():
        with gr.Row():
            with gr.Column(scale=3):
                gr.Markdown("### Chat with Books")

                book_dropdown = gr.Dropdown(
                    choices=[("Select a book...", "none")] +
                            [(f"{title} ({slug})", slug) for slug, title, _, _ in get_available_books()],
                    value="none",
                    label="Select Book (optional)",
                    info="Auto-injects book identifier into queries"
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

                gr.Markdown("""
                **Tips:**
                - Select a book from dropdown or mention slug directly
                - Example: "What does Marcus say about virtue?"
                - Available books listed on the right
                """)

            with gr.Column(scale=1):
                gr.Markdown("### Library")

                book_list = gr.Textbox(
                    value=format_book_list(get_available_books()),
                    lines=20,
                    interactive=False,
                    show_label=False
                )

        # Event handlers - wrap to pass ui
        async def handle_submit(msg_text, history, book_sel):
            return await respond(msg_text, history, book_sel, ui)

        msg.submit(handle_submit, [msg, chatbot, book_dropdown], [chatbot, msg])
        send_btn.click(handle_submit, [msg, chatbot, book_dropdown], [chatbot, msg])
        clear_btn.click(lambda: [], None, chatbot)

    return book_dropdown, book_list
