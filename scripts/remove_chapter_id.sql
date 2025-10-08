-- Remove serial id from chapter_summaries, use composite primary key instead

BEGIN;

-- Create new table with composite primary key
CREATE TABLE chapter_summaries_new (
    book_id INT NOT NULL,
    chapter_id INT NOT NULL,
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (book_id, chapter_id),
    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
);

-- Migrate data
INSERT INTO chapter_summaries_new (book_id, chapter_id, summary, created_at)
SELECT book_id, chapter_id, summary, created_at
FROM chapter_summaries;

-- Drop old table and rename
DROP TABLE chapter_summaries;
ALTER TABLE chapter_summaries_new RENAME TO chapter_summaries;

COMMIT;
