CREATE TABLE chapter_summaries (
    text_id TEXT,
    chapter_id INT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (text_id, chapter_id)
);

CREATE TABLE book_summaries (
    book_id TEXT PRIMARY KEY,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);