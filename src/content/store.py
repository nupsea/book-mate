import os
import psycopg2
from psycopg2.extras import execute_values

from dotenv import load_dotenv

load_dotenv()  # reads .env

DB_CONFIG = {
    "dbname": os.getenv("PG_DB", "booksdb"),
    "user": os.getenv("PG_USER", "bookuser"),
    "password": os.getenv("PG_PASS", "bookpass"),
    "host": os.getenv("PG_HOST", "localhost"),
    "port": os.getenv("PG_PORT", 5432),
}


class PgresStore:

    def __init__(self, conn=None) -> None:
        self.conn = conn or psycopg2.connect(**DB_CONFIG)

    def _resolve_book_id(self, book_identifier: int | str) -> int | None:
        """
        Resolve book_id from either:
        - book_id (int): returns as-is
        - slug (str): looks up book_id from books table
        - title (str): fallback to case-insensitive title match
        Returns None if not found.
        """
        if isinstance(book_identifier, int):
            return book_identifier

        # Try exact slug match first
        with self.conn.cursor() as cur:
            cur.execute("SELECT book_id FROM books WHERE slug = %s", (book_identifier,))
            row = cur.fetchone()
            if row:
                return row[0]

            # Fallback: try case-insensitive title match
            cur.execute("SELECT book_id FROM books WHERE LOWER(title) = LOWER(%s)", (book_identifier,))
            row = cur.fetchone()
            return row[0] if row else None

    def book_exists(self, slug: str) -> bool:
        """Check if a book with given slug exists."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM books WHERE slug = %s", (slug,))
            return cur.fetchone() is not None

    def summaries_exist(self, book_identifier: int | str) -> bool:
        """Check if summaries exist for a book."""
        book_id = self._resolve_book_id(book_identifier)
        if not book_id:
            return False

        with self.conn.cursor() as cur:
            # Check if book summary exists
            cur.execute("SELECT 1 FROM book_summaries WHERE book_id = %s", (book_id,))
            return cur.fetchone() is not None

    def delete_book(self, book_identifier: int | str) -> bool:
        """
        Delete a book and all related data (summaries).
        Foreign key CASCADE will automatically delete chapter_summaries and book_summaries.
        Returns True if book was deleted, False if not found.
        """
        book_id = self._resolve_book_id(book_identifier)
        if not book_id:
            return False

        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM books WHERE book_id = %s", (book_id,))
            deleted = cur.rowcount > 0
        self.conn.commit()
        return deleted

    def store_book_metadata(
        self,
        slug: str,
        title: str,
        author: str = None,
        num_chunks: int = None,
        num_chars: int = None,
    ) -> int:
        """
        Insert or update book metadata. Returns book_id.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO books (slug, title, author, num_chunks, num_chars)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE
                SET title = excluded.title,
                    author = excluded.author,
                    num_chunks = excluded.num_chunks,
                    num_chars = excluded.num_chars
                RETURNING book_id
            """,
                (slug, title, author, num_chunks, num_chars),
            )
            book_id = cur.fetchone()[0]
        self.conn.commit()
        return book_id

    def store_summaries(
        self, book_identifier: int | str, chapter_summaries: list, book_summary: str
    ):
        """
        Store chapter and book summaries.
        book_identifier can be either book_id (int) or slug (str).
        """
        book_id = self._resolve_book_id(book_identifier)
        if not book_id:
            raise ValueError(f"Book not found: {book_identifier}")

        with self.conn.cursor() as cur:
            # Insert chapters
            rows = [(book_id, c["chapter_id"], c["summary"]) for c in chapter_summaries]
            execute_values(
                cur,
                """
                INSERT INTO chapter_summaries (book_id, chapter_id, summary)
                VALUES %s
                ON CONFLICT (book_id, chapter_id) DO UPDATE SET summary = excluded.summary
            """,
                rows,
            )

            # Insert book summary
            cur.execute(
                """
                INSERT INTO book_summaries (book_id, summary)
                VALUES (%s, %s)
                ON CONFLICT (book_id) DO UPDATE SET summary = excluded.summary
            """,
                (book_id, book_summary),
            )

        self.conn.commit()

    def get_chapter_summary(
        self, book_identifier: int | str, chapter_id: int
    ) -> str | None:
        """
        Fetch one chapter summary from DB.
        book_identifier can be either book_id (int) or slug (str).
        """
        book_id = self._resolve_book_id(book_identifier)
        if not book_id:
            return None

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT summary
                FROM chapter_summaries
                WHERE book_id = %s AND chapter_id = %s
                """,
                (book_id, chapter_id),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def get_all_chapter_summaries(
        self, book_identifier: int | str
    ) -> list[tuple[int, str]]:
        """
        Fetch all chapter summaries for a book, ordered by chapter_id.
        book_identifier can be either book_id (int) or slug (str).
        """
        book_id = self._resolve_book_id(book_identifier)
        if not book_id:
            return []

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT chapter_id, summary
                FROM chapter_summaries
                WHERE book_id = %s
                ORDER BY chapter_id
                """,
                (book_id,),
            )
            rows = cur.fetchall()
        return rows

    def get_book_summary(self, book_identifier: int | str) -> str | None:
        """
        Fetch the overall book summary.
        book_identifier can be either book_id (int) or slug (str).
        """
        book_id = self._resolve_book_id(book_identifier)
        if not book_id:
            return None

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT summary
                FROM book_summaries
                WHERE book_id = %s
                """,
                (book_id,),
            )
            row = cur.fetchone()
        return row[0] if row else None
