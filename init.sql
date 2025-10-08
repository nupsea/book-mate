-- Create the main application database (if not present)
-- This runs only on first Postgres container startup
CREATE DATABASE IF NOT EXISTS booksdb;

-- Switch to booksdb to create metadata tables
\connect booksdb;

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