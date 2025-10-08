# Book Workflows

Simple Python scripts for book ingestion and querying.

## Available Scripts

### 1. book_ingest.py
Ingest a book into the system.

**Pipeline**: validate -> parse -> summarize -> store -> build_indexes -> verify

Builds both BM25 (keyword) and Vector (semantic) search indexes in Qdrant.

**Usage**:
```python
import asyncio
from src.flows.book_ingest import ingest_book

result = asyncio.run(ingest_book(
    slug="ody",
    file_path="DATA/the_odyssey.txt",
    title="The Odyssey",
    author="Homer",
    split_pattern=r"^(?:BOOK [IVXLCDM]+)\s*\n",
    force_update=False
))
```

**Parameters**:
- `slug`: Short identifier (e.g., "ody", "aiw")
- `file_path`: Path to book file
- `title`: Book title
- `author`: Book author (optional)
- `split_pattern`: Regex to split chapters (optional)
- `max_tokens`: Max tokens per chunk (default: 500)
- `overlap`: Token overlap (default: 100)
- `force_update`: Delete and re-ingest if exists (default: False)

**Run directly**:
```bash
uv run python -m src.flows.book_ingest
```

### 2. book_query.py
Query book content with hybrid search and summaries.

Uses FusionRetriever for weighted hybrid search (BM25 + Vector embeddings).

**Usage**:
```python
from src.flows.book_query import query_book

# Get all summaries
result = query_book(
    book_identifier="mma",
    include_chapters=True,
    include_book_summary=True
)

# Search with hybrid retrieval + summaries
result = query_book(
    book_identifier="ody",
    query="odysseus journey home",
    include_chapters=False,
    include_book_summary=True
)
print(f"Found {result['search']['num_results']} chunks")
print(f"Chunk IDs: {result['search']['chunk_ids']}")
```

**Parameters**:
- `book_identifier`: Book slug (str) or book_id (int)
- `query`: Search query (optional)
- `include_chapters`: Include chapter summaries (default: True)
- `include_book_summary`: Include book summary (default: True)
- `search_limit`: Max search results (default: 5)

**Run directly**:
```bash
uv run python -m src.flows.book_query
```

## Database

Services required:
- PostgreSQL (books metadata and summaries)
- Qdrant (vector search - optional)

Start services:
```bash
make start
```

Stop services:
```bash
make down
```

## Examples

### Ingest a new book
```bash
python << 'EOF'
import asyncio
from src.flows.book_ingest import ingest_book

result = asyncio.run(ingest_book(
    slug="sha",
    file_path="DATA/sherlock_holmes.txt",
    title="Sherlock Holmes",
    author="Arthur Conan Doyle",
    force_update=False
))
print(result)
EOF
```

### Query book summaries
```bash
python << 'EOF'
from src.flows.book_query import query_book

result = query_book("mma", include_chapters=True)
print(f"Found {result['chapters']['num_chapters']} chapters")
print(f"Book summary: {result['book_summary']['summary'][:200]}...")
EOF
```

## Search Details

### Hybrid Search
The ingestion pipeline builds two indexes:
1. **BM25**: Keyword-based search using term frequency
2. **Vector**: Semantic search using sentence-transformers (BAAI/bge-small-en)

Query uses weighted fusion (alpha=0.7):
- 70% weight on semantic similarity
- 30% weight on keyword matching

### Customization
Adjust search parameters in `src/search/hybrid.py`:
- `alpha`: Weight between BM25 and vector (0.0 = all BM25, 1.0 = all vector)
- `transformer`: Change embedding model
- `k`, `c`: RRF fusion parameters

## TODO

- Add book management scripts (list, update, delete)
- Add batch ingestion script
- Add filtering by book_id in search results
