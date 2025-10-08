-- Migration script: text_id based schema -> slug + book_id schema
-- This script:
-- 1. Creates new tables with proper schema
-- 2. Migrates existing data
-- 3. Drops old tables
-- 4. Renames new tables to final names

BEGIN;

-- Step 1: Create new books table
CREATE TABLE IF NOT EXISTS books_new (
    book_id SERIAL PRIMARY KEY,
    slug VARCHAR(50) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author TEXT,
    num_chunks INT,
    num_chars INT,
    added_at TIMESTAMP DEFAULT NOW()
);

-- Step 2: Populate books table from existing data
-- Using text_id as slug, with placeholder titles
INSERT INTO books_new (slug, title)
SELECT DISTINCT text_id,
    CASE
        WHEN text_id = 'mma' THEN 'Meditations'
        WHEN text_id = 'aiw' THEN 'Alice in Wonderland'
        WHEN text_id = 'ody' THEN 'The Odyssey'
        ELSE text_id  -- fallback to slug if unknown
    END as title
FROM chapter_summaries
ON CONFLICT (slug) DO NOTHING;

-- Step 3: Create new chapter_summaries table
CREATE TABLE IF NOT EXISTS chapter_summaries_new (
    id SERIAL PRIMARY KEY,
    book_id INT NOT NULL,
    chapter_id INT NOT NULL,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (book_id, chapter_id),
    FOREIGN KEY (book_id) REFERENCES books_new(book_id) ON DELETE CASCADE
);

-- Step 4: Migrate chapter summaries
INSERT INTO chapter_summaries_new (book_id, chapter_id, summary, created_at)
SELECT b.book_id, cs.chapter_id, cs.summary, cs.created_at
FROM chapter_summaries cs
JOIN books_new b ON b.slug = cs.text_id;

-- Step 5: Create new book_summaries table
CREATE TABLE IF NOT EXISTS book_summaries_new (
    book_id INT PRIMARY KEY,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (book_id) REFERENCES books_new(book_id) ON DELETE CASCADE
);

-- Step 6: Migrate book summaries
INSERT INTO book_summaries_new (book_id, summary, created_at)
SELECT b.book_id, bs.summary, bs.created_at
FROM book_summaries bs
JOIN books_new b ON b.slug = bs.book_id;  -- old schema used text_id in book_id column

-- Step 7: Drop old tables
DROP TABLE IF EXISTS chapter_summaries CASCADE;
DROP TABLE IF EXISTS book_summaries CASCADE;

-- Step 8: Rename new tables
ALTER TABLE books_new RENAME TO books;
ALTER TABLE chapter_summaries_new RENAME TO chapter_summaries;
ALTER TABLE book_summaries_new RENAME TO book_summaries;

COMMIT;
