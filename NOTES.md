# Day 3 — PostgreSQL Migration Notes

## 1. Database
- Database: Neon PostgreSQL
- Connection: Verified successfully
- Tables: documents and pages
- Records loaded: 20 documents and 20 pages

## 2. Alembic migration verification

Migration history:
- 40bec2f4cdc3: Create documents and pages tables
- d03_integer_ids: Convert document and page IDs to integers
- 5bf755981045: Add GIN index for document metadata

Downgrade verification:
- Ran: uv run alembic downgrade -1
- Result: d03_integer_ids

Upgrade verification:
- Ran: uv run alembic upgrade head
- Result: 5bf755981045 (head)

## 3. Loader idempotency

Second loader run:
- Records: 20
- Inserted: 0
- Updated: 0
- Unchanged: 20

This confirms that rerunning the loader does not create duplicate records when the data has not changed.

## 4. API and tests

- API reads from PostgreSQL using asynchronous SQLAlchemy sessions.
- Health and readiness endpoints implemented.
- Document listing, searching, filtering and statistics implemented.
- Unit tests: 16 passed.

## 5. GIN index query plan

Query:
SELECT id, external_id
FROM documents
WHERE metadata @> CAST(:filter AS jsonb);

Filter:
{"kural_no": 1}

Normal query plan:
- PostgreSQL selected Seq Scan.
- 1 row returned.
- 19 rows removed by filter.
- Execution time: 0.041 ms.

With enable_seqscan = off:
- PostgreSQL selected Bitmap Heap Scan.
- Bitmap Index Scan used ix_documents_metadata_gin.
- 1 row returned.
- Execution time: 0.076 ms.

## 6. Explanation

PostgreSQL selected a sequential scan for the normal query because the table contains only 20 records. Scanning a small table can be cheaper than using an index.

When sequential scans were disabled, PostgreSQL used the GIN index through a Bitmap Index Scan. This confirms that the JSONB GIN index is available and usable for containment queries.
