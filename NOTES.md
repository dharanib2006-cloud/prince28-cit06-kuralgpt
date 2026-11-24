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

### Stretch task: Heaviest Docker layer
- Inspected the image using `docker history kuralgpt-api:day4`.
- Largest application layer: copying `/app/.venv` into the runtime image (109 MB).
- Reason: the virtual environment contains the installed Python dependencies and their supporting files.

### Stretch task: Heaviest Docker layer
- Inspected the image using `docker history kuralgpt-api:day4`.
- Largest application layer: copying `/app/.venv` into the runtime image (109 MB).
- Reason: the virtual environment contains installed Python dependencies and supporting files.

### Stretch task: HTML coverage
- Generated the HTML coverage report using `uv run pytest --cov --cov-report=html`.
- Added tests for default application settings and database pool logging after 50 requests.
- Focused API tests: 21 passed.
- Full test suite after additions: 29 passed.
- HTML report generated in `htmlcov`.

### Stretch task: Run Docker image against Neon
- Started the production-mode Docker image using the local `.env` file.
- `/ready` returned `ready`.
- Database connectivity check returned `True`.
- The API reported 20 records.
- No migrations or seed operations were run during this check.

### Stretch task: Restart API when database restarts
- Added `restart: true` under the API service's `depends_on.db` configuration.
- Validated the Compose configuration successfully.
- Ran `docker compose restart db`.
- Compose restarted the API after the database restart.
- API `/health` returned `ok`; `/ready` returned `ready`.
- Database connectivity remained healthy and 20 records were reported.


---

# Day 5 – CI/CD and Going Live

## 1. Live Deployment
- Live URL: https://kuralgpt.onrender.com
- CI run: https://github.com/dharanib2006-cloud/prince28-cit06-kuralgpt/actions/runs/44766034616
- Automatic CD run: https://github.com/dharanib2006-cloud/prince28-cit06-kuralgpt/actions/runs/44766244282
- The application was deployed after merging PR #7.
- Latest deployment was verified using the `/health` endpoint.

## 2. Smoke Test
- The CD workflow completed successfully.
- Smoke tests verified:
  - `/health`
  - `/ready`
  - `/v1/documents?limit=1`
- `/health` returned the deployed Git SHA.
- `/ready` confirmed database readiness.

## 3. Rollback and Roll-forward Drill

### Rollback
- Rolled back to commit: `febc3dd1e54a7042bc1eb9808d4ed416cc2cb9ae`
- Verified the rollback using `/health`.
- `/ready` returned `ready`.
- Database connectivity was successful.

### Roll-forward
- Rolled forward to commit: `c93e70e4fec33d75ec9dd3aa82cc4c2f6da33131`
- Verified the deployed SHA using `/health`.
- Confirmed `/ready` returned `ready`.

### Database schema consideration
The rollback workflow deploys the older application image without running database downgrade migrations. Therefore, the database remains on the newer schema while the older application version is restored.

### Timing records
- Rollback duration: Not recorded.
- Roll-forward duration: Not recorded.

## 4. Secret Storage
- Neon database connection string: GitHub Secret `DATABASE_URL` and Render environment variable `DATABASE_URL`.
- Render deploy hook: GitHub Secret `RENDER_DEPLOY_HOOK` only.
- No secret values are stored in the repository.

## 5. Monitoring
- Monitoring service: UptimeRobot.
- Monitor URL: https://stats.uptimerobot.com/OYt04cXjzo
- Monitored endpoint: `https://kuralgpt.onrender.com/health`
- Check interval: 5 minutes.
- The `/health` endpoint supports GET and HEAD requests.

## 6. First-Request Speed Improvement
- A possible future improvement is to reduce application startup time by optimizing dependency loading and initialization.
- This is a proposed improvement and has not been recorded as an implemented optimization.

## 7. Week-1 Tag
- Git tag: `week-1`
- The tag was pushed to the remote repository.

## 8. Human Approval Gate
A human approval gate is useful when deploying critical production changes that could affect users, security, or important data. It provides a final manual check before deployment and helps reduce accidental or harmful releases.

## 9. Stretch Task – Change Lead Time Measurement

Measured on 20 November 2026, from PR merge to successful live smoke test for three CD deployments.

| CD Run | PR Merge Time (IST) | Smoke Test Passed (IST) | Lead Time |
|---|---|---|---|
| #7 | 10:39:22 PM | 10:42:04 PM | 2 min 42 sec |
| #8 | 11:24:24 PM | 11:26:44 PM | 2 min 20 sec |
| #9 | 11:46:33 PM | 11:48:37 PM | 2 min 04 sec |

- Average change lead time: 2 minutes 22 seconds.
- Slowest deployment: CD run #7 (2 minutes 42 seconds).
- The smoke test was the final verification step in each deployment.
- All three CD runs completed successfully.erification step in each deployment.
- All three CD runs completed successfully.

## D06 - Collecting the Corpus

### 1. Start Target and Collection

- Start target: All 1,330 Kurals with at least 2 commentaries.
- Collected today: **5 files, 0 PDF pages, 2.31 MB** (from `DATASET.md`).
- Collection method used: Git repository downloader.
- Repository: `tk120404/thirukkural`
- Pinned commit: `cf3ff6c5a73c23b4092913156830457caab65fd4`
- Main Kural JSON contains 1,330 records.
- Commentary fields available:
  - `mv`: 1,330 / 1,330
  - `sp`: 1,330 / 1,330
  - `mk`: 1,330 / 1,330

### 2. Licence Check

| Source | Licence or terms, in my words | May I show full text in answers? |
|---|---|---|
| `tk120404/thirukkural` | Repository includes an Apache-2.0 licence. The licence file was downloaded and inspected. | Not confirmed for all commentary fields; separate third-party rights verification is pending. |
| CICT Thirukkural pages | Educational/non-commercial reproduction requires written permission and acknowledgement. | Not yet; written permission is pending. |
| Project Madurai | Texts are described as free for non-commercial use with credit. Specific source terms must be checked before use. | Not yet; additional sources have not been collected or checked. |

**Licence note:** A repository's Apache-2.0 licence does not automatically prove that every third-party commentary included in its dataset can be reused.

### 3. robots.txt

- The downloader checks `robots.txt` before fetching URLs.
- Per-host request delay and a maximum concurrency of four are implemented.
- The exact robots.txt response lines for the GitHub repository source were not recorded in my notes.
- No blocked repository files were recorded during the successful download.
- CICT robots.txt was checked for its Thirukkural paths; robots permission does not replace copyright permission.

### 4. Kill and Resume

- Repository download: 2 matching JSON files were downloaded successfully.
- Subsequent repository runs: downloaded = 0, skipped = 2.
- Manual interruption test: Started a local 10 MB download and pressed Ctrl+C after approximately 10 seconds.
- Cleanup: No incomplete `.part` files remained after interruption.
- Recovery: Restarted the same command; completed = 1, failed = 0.
- Recovered test file size: 10,485,760 bytes.
- Automated cancellation cleanup test: Passed.
- Automated delete-and-redownload test: Passed.
- Downloader unit tests: 23 passed.

### 5. Capacity

Based on `DATASET.md` and `docs/CAPACITY.md`:

- Current Kural records: 1,330.
- Current downloaded files: 5.
- Current downloaded size: 2.31 MB.
- Current PDF pages: 0.
- Current estimated tokens: 133,000 (planning assumption).
- Current estimated chunks: 266 at 500 tokens per chunk.
- Full corpus target: Approximately 3,000+ PDF pages.
- Full-corpus token count and chunk count: Not measured because the additional PDFs have not yet been collected.
- Vector dimensions: 1,024.
- Estimated current raw vector storage: 1.04 MB.
- Example embedding budget: $0.20 (approximately INR 19); actual provider cost must be checked before deployment.

**The number that surprised me most:** The initial dataset already contains all 1,330 Kurals and three populated commentary fields. However, the downloaded corpus is only 2.31 MB and has no PDF pages yet.

The main remaining challenge is collecting the additional Tamil literature and verifying reuse permissions for the commentary texts.

### 6. One Thing That Went Wrong and How I Fixed It

Initially, the Kural-counting report detected the wrong JSON file because the repository contained both a detail JSON file and the main Kural JSON file.

I corrected the counting logic to select the main Thirukkural JSON file and exclude detail and tree files. The report then correctly detected all 1,330 Kurals.

I also tested interrupted downloads and confirmed that incomplete `.part` files are cleaned up and downloads can resume successfully.

### 7. Final Verification

- Dataset report generated successfully.
- `DATASET.md` and `docs/CAPACITY.md` updated.
- Ruff lint: Passed.
- Ruff formatting: Passed; 53 files already formatted.
- Unit tests: 45 passed.
- No test failures.
