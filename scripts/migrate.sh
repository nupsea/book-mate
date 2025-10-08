#!/usr/bin/env bash
set -e

# Load .env if present
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

POSTGRES_CONTAINER=${POSTGRES_CONTAINER:-books_postgres}
PGUSER=${PG_USER:-bookuser}
PGPASSWORD=${PG_PASS:-bookpass}
DB_NAME=${DB_NAME:-booksdb}

echo "=========================================="
echo "Database Schema Migration"
echo "=========================================="
echo ""

# Backup existing data
echo "Step 1: Creating backup..."
docker exec -e PGPASSWORD=$PGPASSWORD $POSTGRES_CONTAINER \
  pg_dump -U $PGUSER -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql
echo "✓ Backup created"
echo ""

# Show current data
echo "Step 2: Current books in database:"
docker exec -e PGPASSWORD=$PGPASSWORD $POSTGRES_CONTAINER \
  psql -U $PGUSER -d $DB_NAME -c "SELECT DISTINCT text_id FROM chapter_summaries;"
echo ""

# Run migration
echo "Step 3: Running migration..."
docker exec -i -e PGPASSWORD=$PGPASSWORD $POSTGRES_CONTAINER \
  psql -U $PGUSER -d $DB_NAME < scripts/migrate_schema.sql
echo "✓ Migration completed"
echo ""

# Verify migration
echo "Step 4: Verifying new schema..."
docker exec -e PGPASSWORD=$PGPASSWORD $POSTGRES_CONTAINER \
  psql -U $PGUSER -d $DB_NAME -c "\dt"
echo ""

echo "Step 5: Books after migration:"
docker exec -e PGPASSWORD=$PGPASSWORD $POSTGRES_CONTAINER \
  psql -U $PGUSER -d $DB_NAME -c "SELECT book_id, slug, title FROM books;"
echo ""

echo "=========================================="
echo "Migration completed successfully!"
echo "=========================================="
