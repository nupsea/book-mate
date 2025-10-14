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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_query_metrics_timestamp ON query_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_query_metrics_book_slug ON query_metrics(book_slug);
CREATE INDEX IF NOT EXISTS idx_query_metrics_success ON query_metrics(success);
