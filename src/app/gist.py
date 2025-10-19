from src.content.store import PgresStore

# Example usage: Query by slug or book_id
store = PgresStore()

# Query using slug (human-readable identifier)
print(store.get_book_summary("ody"))
print("-" * 30)
# Query using book_id (if you know it)
print(store.get_book_summary(1))
print("-" * 30)

# Get chapter summaries
chapters = store.get_all_chapter_summaries("mma")
for chapter_id, summary in chapters:
    print(f"Chapter {chapter_id}: {summary[:170]}...")
