# Day 3 — PostgreSQL Migration Notes

## 1. Database

- Database: Neon PostgreSQL
- Connection: Verified successfully
- Tables: `documents` and `pages`
- Records loaded: 20 documents and 20 pages
- SQLAlchemy asynchronous database connection configured.

## 2. Alembic Migration Verification

Migration history:

- `40bec2f4cdc3`: Create documents and pages tables
- `d03_integer_ids`: Convert document and page IDs to integers
- `5bf755981045`: Add GIN index for document metadata
- `c71a9d3e2f40`: Add typed `kural_no` column and B-tree index

Downgrade verification:

- Ran: `uv run alembic downgrade -1`
- Result: `d03_integer_ids`

Upgrade verification:

- Ran: `uv run alembic upgrade head`
- Result: `c71a9d3e2f40 (head)`

## 3. Loader Idempotency

Loader verification:

- Records: 20
- Inserted: 0
- Updated: 0
- Unchanged: 20
- Deleted: 0

Modified-record verification:

- Changed one record's `theme` value.
- Loader output: Updated 1 record and left 19 unchanged.
- Restored the original JSON file.
- Ran the loader again until all 20 records were unchanged.

This confirms that rerunning the loader does not create duplicate records and that modified records are detected.

## 4. Stretch Task 1 — Loader Prune Option

- Added the `--prune` command-line option.
- Normal loader execution does not delete existing records.
- With `--prune`, records absent from the input JSON can be removed.
- Pruning is restricted to Kural records from the configured source.
- The loader reports the number of deleted records.

The normal loader run reported `Deleted: 0`.

## 5. Stretch Task 2 — Typed Kural Number

Added a dedicated integer `kural_no` column to the `documents` table.

Migration operations:

- Added the nullable integer column.
- Backfilled values from the existing JSONB `metadata` field.
- Created the B-tree index `ix_documents_kural_no`.

Database verification:

- Total Kural records: 20
- Populated `kural_no` values: 20
- Minimum Kural number: 1
- Maximum Kural number: 20
- B-tree index: Verified.

Updated the data loader to populate the typed column and updated the repository filter to use `Document.kural_no` instead of extracting the value from JSONB metadata.

Added integration tests for:

- Backfilled Kural numbers.
- Filtering using the typed integer column.
- Existence of the B-tree index.

## 6. API and Tests

- API reads from PostgreSQL using asynchronous SQLAlchemy sessions.
- Health and readiness endpoints implemented.
- Document listing, searching, filtering and statistics implemented.
- Kural number filtering uses the typed integer column.
- Unit tests: 16 passed.
- Integration tests: 6 skipped because `TEST_DATABASE_URL` is not configured in the test environment.

## 7. GIN Index Query Plan

Query:

```sql
SELECT id, external_id
FROM documents
WHERE metadata @> CAST(:filter AS jsonb);
```

Filter:

```json
{"kural_no": 1}
```

Normal query plan:

- PostgreSQL selected Seq Scan.
- 1 row returned.
- 19 rows removed by filter.
- Execution time: 0.041 ms.

With `enable_seqscan = off`:

- PostgreSQL selected Bitmap Heap Scan.
- Bitmap Index Scan used `ix_documents_metadata_gin`.
- 1 row returned.
- Execution time: 0.076 ms.

## 8. Explanation

PostgreSQL selected a sequential scan for the normal query because the table contains only 20 records. Scanning a small table can be cheaper than using an index.

When sequential scans were disabled, PostgreSQL used the GIN index through a Bitmap Index Scan. This confirms that the JSONB GIN index is available and usable for containment queries.

The additional B-tree index on `kural_no` supports efficient filtering using the dedicated integer column.
## D03 Stretch Task 4 — Connection Pool Monitoring

### Implementation
- Added a connection-pool status log during FastAPI application startup.
- Added a connection-pool status log after the 50th HTTP request.
- Used SQLAlchemy `engine.pool.status()` to inspect the pool.

### Verification
- Started the API using Uvicorn with the application factory.
- Sent 50 consecutive GET requests to `/health` using an async httpx client.
- All 50 requests returned HTTP 200 OK.
- Both startup and after-50-request pool logs were observed.

### Observed Pool Status

| Metric | Startup | After 50 requests |
|---|---:|---:|
| Pool size | 5 | 5 |
| Connections in pool | 0 | 0 |
| Current overflow | -5 | -5 |
| Checked-out connections | 0 | 0 |

### Explanation
- Pool size 5: configured base connection pool capacity.
- Connections in pool 0: no idle database connections existed.
- Current overflow -5: no connections had been created; this is the initial pool overflow calculation.
- Checked-out connections 0: no database connections were currently in use.

Note: The 50 requests targeted the `/health` endpoint, which did not acquire database connections. Therefore, this test verifies pool-status logging, not database connection reuse under database-backed traffic.



---

# Day 4 – Docker Compose Verification Notes

## 1. Stack startup

Started the complete stack using:

```powershell
docker compose up -d
```

Services verified:
- PostgreSQL (`db`) – healthy
- Redis (`redis`) – healthy
- Migration and data loader (`migrate`) – exited successfully
- API (`api`) – healthy

Database loader result:
- Records: 20
- Inserted: 20
- Updated: 0
- Unchanged: 0
- Deleted: 0

## 2. API health and readiness

With all services running:
- `/health` returned `status: ok`
- `/ready` returned `ready`

## 3. Database outage test

Stopped PostgreSQL:

```powershell
docker compose stop db
```

Results:
- `/health` continued returning `status: ok`
- `/ready` returned HTTP 503
- Database readiness check returned `false`

## 4. Database recovery test

Restarted PostgreSQL:

```powershell
docker compose start db
```

Waited until PostgreSQL became healthy.

Results:
- `/health` returned `status: ok`
- `/ready` returned `ready`

## 5. Port mapping

The API is accessible on host port 8000:

```text
0.0.0.0:8000 -> 8000/tcp
```

Verified using:

```powershell
docker compose port api 8000
```

## 6. Summary

The Docker Compose stack starts successfully. Database migrations and sample data loading complete successfully. The API remains alive when PostgreSQL is stopped, readiness correctly returns HTTP 503 during the outage, and readiness recovers after PostgreSQL restarts.

## 7. Testing and coverage

### Unit tests
- Command: `uv run poe test`
- Result: 19 unit tests passed.
- Unit-only coverage: 65%.

### Integration tests
- Command: `uv run poe test-integration`
- Result: 8 integration tests passed.
- A uniquely named temporary PostgreSQL database was created and migrated.
- Automatic cleanup was verified; no temporary test databases remained.

### Combined tests and coverage
- Command: `uv run poe cov`
- Result: 27 tests passed (19 unit and 8 integration).
- Combined coverage: 74%.

### Lint and formatting
- Command: `uv run poe lint`
- Ruff checks passed.
- 49 files passed the formatting check.

### Coverage observations
- `database.py` and `store.py` had no executed lines in the coverage report.
- Combined coverage is recorded as measured: 74%.

## 8. Day 4 verification summary
- Multi-stage Docker image built successfully.
- Runtime uses the non-root `app` user.
- Docker image size: approximately 71.1 MiB.
- Docker Compose services started and passed health checks.
- Migrations and sample data loading completed successfully.
- `/health` remained available during the database outage.
- `/ready` returned HTTP 503 during the outage and recovered after PostgreSQL restarted.
- Unit tests: 19 passed.
- Integration tests: 8 passed.
- Combined tests: 27 passed.
- Ruff lint and formatting checks passed.
- Temporary integration-test database cleanup was verified.

## 9. Final Docker verification evidence

### Docker image
- Image: `kuralgpt-api:day4`
- Image ID: `sha256:04458b96e1ee16733462383c0f0a5a0c5180154b6ad3dc3f6caa904bebcaa94b`
- Image size: 74,609,387 bytes (approximately 71.1 MiB).
- Runtime user: `app` (non-root).

### Final Docker Compose verification
- `db`: healthy.
- `redis`: healthy.
- `migrate`: exited with code 0.
- `api`: healthy.
- API host port: 8000.
- `/health`: `ok`.
- `/ready`: `ready`.

### Migration and sample data
- Alembic migrations completed successfully.
- Database loading completed successfully.
- Records: 20.
- Inserted: 20.
- Updated: 0.
- Unchanged: 0.
- Deleted: 0.

### Build cache
- The final rebuild reused cached Docker layers.
- Dependency installation and image export completed successfully.

### Fresh-clone verification
- Cloned the committed repository into a separate directory.
- Built the API and migration images successfully from the clone.
- PostgreSQL and Redis became healthy.
- Migrations and sample data loading completed successfully (exit code 0).
- API became healthy.
- `/health`: `ok`.
- `/ready`: `ready`.
- Used separate host ports 5434 (PostgreSQL), 6380 (Redis), and 8001 (API) to avoid conflicts with the original stack.
