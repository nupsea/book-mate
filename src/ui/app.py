"""
Main Gradio application for Book Mate.
"""

import gradio as gr
import asyncio
import os
from src.mcp_client.agent import BookMateAgent
from src.ui.chat import create_chat_interface
from src.ui.ingest import create_ingest_interface
from src.ui.monitoring import create_monitoring_interface
from src.monitoring.tracer import init_phoenix_tracing

# Initialize Phoenix tracing once at module load
init_phoenix_tracing()


class BookMateUI:
    """Main UI controller managing the MCP agent."""

    def __init__(self):
        self.agent = None
        self.api_key = os.getenv("OPENAI_API_KEY") or ""
        self.model = "gpt-4o-mini"  # Default model

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

    async def set_model(self, model: str):
        """Set the OpenAI model and reinitialize agent if needed."""
        if model != self.model:
            print(f"Changing model from {self.model} to {model}")
            self.model = model
            # Properly cleanup old agent before resetting
            if self.agent:
                try:
                    await self.agent.close()
                    print("Old agent cleaned up successfully")
                except Exception as e:
                    print(f"Warning: Error cleaning up old agent: {e}")
            # Reset agent to reinitialize with new model
            self.agent = None

    async def init_agent(self):
        """Initialize the MCP agent connection."""
        if self.agent is None:
            print(f"Initializing agent with model: {self.model}")
            self.agent = BookMateAgent(self.api_key, self.model)
            try:
                await self.agent.connect_to_mcp_server()
                print("Agent initialized and connected to MCP Server")
            except Exception as e:
                print(f"Error initializing agent: {e}")
                self.agent = None
                raise

    async def chat(
        self, message: str, history: list, selected_book: str = None
    ) -> tuple[str, str]:
        """
        Handle chat messages with the agent.

        Args:
            message: User message
            history: Gradio chat history format
            selected_book: Selected book slug (optional)

        Returns:
            (agent_response, query_id)
        """
        # Initialize agent with retry logic
        max_retries = 2
        for attempt in range(max_retries):
            if self.agent is None:
                try:
                    await self.init_agent()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        return f"Failed to initialize agent: {str(e)}", None
                    print(f"Init attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(2)

        # Auto-inject book title if selected
        print(f"\n[UI] Original message: {message}")
        print(f"[UI] Selected book slug from dropdown: {selected_book}")

        if selected_book and selected_book != "none":
            # Get book title from slug
            from src.content.store import PgresStore

            try:
                store = PgresStore()
                with store.conn.cursor() as cur:
                    cur.execute(
                        "SELECT title FROM books WHERE slug = %s", (selected_book,)
                    )
                    result = cur.fetchone()
                    if result:
                        book_title = result[0]
                        print(
                            f"[UI] Found book title for slug '{selected_book}': {book_title}"
                        )
                        # Only inject if not already mentioned
                        if book_title.lower() not in message.lower():
                            message = f"{message} (for the book '{book_title}')"
                            print(f"[UI] Injected title into message: {message}")
                        else:
                            print("[UI] Title already in message, not injecting")
            except Exception as e:
                print(f"[WARN] Could not get book title: {e}")
        else:
            print("[UI] No book selected from dropdown")

        # Convert Gradio history to OpenAI format
        conversation_history = []
        for user_msg, bot_msg in history:
            conversation_history.append({"role": "user", "content": user_msg})
            if bot_msg:
                conversation_history.append({"role": "assistant", "content": bot_msg})

        try:
            response, _, query_id = await self.agent.chat(message, conversation_history)
            return response, query_id
        except Exception as e:
            print(f"Chat error: {e}")
            # Reset agent on error
            self.agent = None
            return f"Error: {str(e)}. Connection reset, please try again.", None

    async def cleanup(self):
        """Clean up agent resources."""
        if self.agent:
            await self.agent.close()
            self.agent = None


def create_app():
    """Create the main Gradio application."""
    from src.ui.utils import get_available_books, format_book_list

    ui = BookMateUI()

    with gr.Blocks(title="Book Mate", theme=gr.themes.Base()) as app:
        gr.Markdown("# Book Mate - AI Book Assistant")

        with gr.Tabs() as tabs:
            # Tab 1: Chat Interface
            with gr.Tab("Chat", id=0):
                dropdown, book_list, load_book_list = create_chat_interface(ui)

            # Tab 2: Add New Book
            with gr.Tab("Add Book", id=1):
                ingest_book_list = create_ingest_interface()

            # Tab 3: Monitoring
            with gr.Tab("Monitoring", id=2):
                create_monitoring_interface()

        # Auto-refresh book lists when switching tabs
        def refresh_on_tab_change(evt: gr.SelectData):
            # Always fetch fresh data from database (source of truth)
            books = get_available_books()
            new_list = format_book_list(books)
            # Show only titles in dropdown, not slugs
            new_choices = [("Select a book...", "none")] + [
                (f"{title}", slug) for slug, title, _, _, _ in books
            ]

            print(
                f"[DEBUG] Tab switched to: {evt.value}, refreshing with {len(books)} books"
            )

            if evt.value == 0 or evt.index == 0:
                # Switching to Chat tab - refresh chat book list and dropdown
                return new_list, gr.update(choices=new_choices), gr.update()
            elif evt.value == 1 or evt.index == 1:
                # Switching to Add Book tab - refresh ingest book list
                return gr.update(), gr.update(), new_list

            # Refresh both to be safe
            return new_list, gr.update(choices=new_choices), new_list

        tabs.select(
            refresh_on_tab_change, None, [book_list, dropdown, ingest_book_list]
        )

        # Load book lists on startup
        def load_ingest_list():
            return format_book_list(get_available_books())

        app.load(load_book_list, None, book_list)
        app.load(load_ingest_list, None, ingest_book_list)

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)
