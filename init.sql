-- Create tables in the booksdb database
-- This runs only on first Postgres container startup
-- The database 'booksdb' is already created by POSTGRES_DB environment variable

CREATE TABLE IF NOT EXISTS books (
    book_id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    num_chunks INT,
    num_chars INT,
    added_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chapter_summaries (
    book_id INT NOT NULL,
    chapter_id INT NOT NULL,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (book_id, chapter_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS book_summaries (
    book_id INT PRIMARY KEY,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
);

-- Metrics tables for monitoring
CREATE TABLE IF NOT EXISTS query_metrics (
    query_id VARCHAR(100) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    query TEXT NOT NULL,
    response TEXT,
    book_slug VARCHAR(50),
    latency_ms FLOAT NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    tool_calls TEXT[],
    num_results INTEGER,
    llm_relevance_score VARCHAR(20),
    llm_reasoning TEXT,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    user_comment TEXT,
    retry_attempted BOOLEAN DEFAULT FALSE,
    original_query TEXT,
    rephrased_query TEXT,
    retry_results INTEGER,
    fallback_to_context BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_metrics_timestamp ON query_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_query_metrics_book_slug ON query_metrics(book_slug);
CREATE INDEX IF NOT EXISTS idx_query_metrics_success ON query_metrics(success);