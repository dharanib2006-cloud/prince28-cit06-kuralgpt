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

### Full Corpus Parsing and Failure Report

- Total available files: 5
- Successfully parsed: 5
- Failed files: 0
- Total pages parsed: 436
- Second run: 5 files already parsed
- Newly processed on second run: 0
- Duplicate pages created: 0
- Parse failures recorded: 0

**Result:** All 5 available files were parsed successfully. The second run confirmed idempotency because previously parsed files were skipped.

**Known limitation:** The local corpus contains only 5 supported files, rather than the expected 364 files. Therefore, the full 364-file target could not be tested.

**Failure handling:** No failures occurred, so no retry was necessary. No failures out of 5 files.



---

## D06 Continuation – Project Madurai HTML Collection (24 November 2026)

### 1. Download Results

Collected 15 HTML source files from Project Madurai.

| Status | Count |
|---|---:|
| Completed | 15 |
| Blocked | 0 |
| Failed | 0 |
| Too large | 0 |
| Skipped | 0 |

All 15 files were downloaded successfully.

### 2. Encoding Issue and Fix

During Unicode verification, one HTML file was found to use UTF-16 LE encoding instead of UTF-8:

- `project_madurai-pmuni0048-c414893b.html`

The parser originally supported UTF-8 only. I updated `_parse_html()` to detect UTF-16 BOM markers and decode the file correctly.

Verification:
- 14 files decoded as UTF-8.
- 1 file decoded as UTF-16 LE.
- All 15 files contained Tamil text.
- No replacement characters were found.

### 3. Parsing Results

Executed:

`uv run python scripts/parse_corpus.py --source-dir data/raw/project_madurai --limit 20`

| Metric | Result |
|---|---:|
| Files found | 15 |
| Successfully parsed | 15 |
| Failed | 0 |
| Pages added | 256 |
| Processing time | 49.1 seconds |

All 15 HTML files were parsed successfully.

### 4. Individual Page Counts

| Source file | Pages |
|---|---:|
| pmuni0002 | 6 |
| pmuni0016 | 21 |
| pmuni0022 | 2 |
| pmuni0024 | 7 |
| pmuni0025 | 11 |
| pmuni0027 | 14 |
| pmuni0028 | 24 |
| pmuni0029 | 14 |
| pmuni0036 | 21 |
| pmuni0038 | 28 |
| pmuni0047 | 7 |
| pmuni0048 | 7 |
| pmuni0055 | 6 |
| pmuni0056 | 9 |
| pmuni0057 | 79 |
| **Total** | **256** |

### 5. Idempotency Verification

Executed the parser again without the limit:

`uv run python scripts/parse_corpus.py --source-dir data/raw/project_madurai`

Results:
- Files found: 15
- Successful: 0
- Failed: 0
- Already parsed: 15
- Pages added: 0

This confirms that rerunning the parser does not create duplicate documents or pages.

### 6. Database Verification

Connected to the existing Neon PostgreSQL database and performed read-only verification.

| Metric | Database result |
|---|---:|
| Total documents | 1,350 |
| Total pages | 2,022 |
| Project Madurai documents | 15 |
| Project Madurai pages | 256 |
| Project Madurai parse failures | 0 |

All 15 documents had matching recorded and actual page counts.

New Project Madurai document IDs: 1824–1838.

### 7. Dataset and Capacity Report

Executed:

`uv run python scripts/dataset_report.py`

Results:
- Kural records detected: 1,330
- Downloaded files detected: 20
- PDF pages: 0
- `DATASET.md` regenerated successfully.
- `docs/CAPACITY.md` regenerated successfully.

Note: The PDF page count does not include the 256 pages extracted from Project Madurai HTML files. These are tracked separately.

### 8. Current Outcome

- Downloaded and verified 15 Project Madurai HTML files.
- Fixed UTF-16 LE decoding support.
- Parsed all 15 files successfully.
- Added 256 pages to the database.
- Verified zero Project Madurai parsing failures.
- Confirmed parser idempotency.
- Regenerated dataset and capacity reports.

**Result:** Project Madurai HTML collection and database ingestion completed successfully. Existing corpus records and previous project notes were preserved.

**Remaining work:** Run linting, formatting checks, and tests to verify the complete project after these changes.

### 9. Licence Reminder

The downloaded files still require source-specific reuse and copyright verification before public or commercial deployment. Successful downloading and parsing do not establish permission to redistribute the texts.


## Step 5 – Parser Comparison

### 1. Objective

Compared two parsing approaches to identify which parser extracts Tamil content more effectively from the Project Madurai HTML files.

- **Parser A:** Trafilatura
- **Parser B:** Plain HTML tag stripping

The comparison considered:

- Extracted text length
- Heading detection
- Table detection
- Parsing time
- Tamil text readability
- Preservation of poems, section headings and metadata

### 2. Running the Comparison

Selected the 10 largest HTML files from the corpus.

Command used:

```powershell
uv run python scripts/compare_parsers.py $files
```

The comparison results were written to `NOTES.md`.

### 3. Parser Comparison Results

| File | Trafilatura chars | Plain tags chars | Trafilatura headings | Plain headings | Trafilatura time (s) | Plain time (s) | Better parser and reason |
|---|---:|---:|---:|---:|---:|---:|---|
| pmuni0057-b743c7f2.html | 235855 | 234375 | 0 | 2 | 0.513 | 0.045 | Plain tags – faster and detects two headings. Heading correctness should be checked. |
| pmuni0038-502711e7.html | 90945 | 86311 | 12 | 12 | 0.262 | 0.032 | Trafilatura – preserves Tamil text, headings, acknowledgements, poem numbers and metadata in readable Markdown. |
| pmuni0028-a852d112.html | 71458 | 69490 | 0 | 2 | 0.185 | 0.020 | Trafilatura – preserves readable Tamil poems, title, author and section titles. Heading metadata was empty in inspected pages. |
| pmuni0036-64d74aa8.html | 61390 | 60830 | 0 | 2 | 0.204 | 0.008 | Trafilatura – preserves Tamil poems, title, author and poem numbers. Section headings appear in text, but heading metadata is empty. |
| pmuni0016-e486fc8d.html | 60366 | 58315 | 2 | 2 | 0.174 | 0.014 | Trafilatura – extracts more text with the same heading count and preserves readable Tamil content. |
| pmuni0029-2c0dc8d0.html | 34647 | 36532 | 4 | 4 | 0.288 | 0.004 | Plain tags – faster and extracts more characters. Extra content should be checked for unnecessary boilerplate. |
| pmuni0027-9125683b.html | 32361 | 34459 | 5 | 5 | 0.252 | 0.008 | Plain tags – faster and extracts more characters with the same heading count. |
| pmuni0056-ce4cfceb.html | 30232 | 28785 | 3 | 3 | 0.094 | 0.003 | Trafilatura – preserves Tamil poems, section labels and poem numbers, but heading metadata remains generic. |
| pmuni0025-48fe335a.html | 24569 | 26045 | 5 | 5 | 0.116 | 0.005 | Plain tags – faster and extracts more characters with the same heading count. |
| pmuni0024-01033a52.html | 19578 | 18933 | 1 | 1 | 0.086 | 0.005 | Trafilatura – extracts slightly more text and preserves the title and readable content. |

**Comparison observations:**

- Trafilatura extracted more characters in 7 out of 10 files.
- Plain tag stripping was faster in all 10 comparisons.
- All 10 comparisons reported zero detected tables.
- Character count alone does not determine extraction quality.
- The last six files were sampled rather than fully compared manually.

### 4. Original HTML and Parsed Content Inspection

Inspected four original HTML files alongside their corresponding parsed database pages.

**File 1: pmuni0038 – patiRRuppattu**

- Original HTML contains Tamil poems, acknowledgements, section headings and metadata.
- Trafilatura preserves readable Tamil text, poem numbers and metadata.
- Markdown formatting makes the extracted content easier to read.
- Some special Tamil characters and formatting artifacts need checking.

**Observation:** Trafilatura is preferred because it preserves document structure and readable Tamil content.

**File 2: pmuni0056 – tiNaimAlai nURRaimpatu**

- Original HTML contains five main sections: குறிஞ்சி, நெய்தல், பாலை, முல்லை and மருதம்.
- Parsed content preserves Tamil poems, section labels, poem numbers and introductory information.
- The final section and completion text are also present.
- Heading metadata contains a generic document-level heading path instead of individual section headings.

**Observation:** Trafilatura preserves the content well, but heading metadata needs improvement.

**File 3: pmuni0028 – aingurunUru**

- Original HTML contains the Tamil title, author details, poems and internal section titles.
- Parsed content preserves readable Tamil poems, poem numbers and section titles.
- The inspected database pages had empty heading metadata.
- The original HTML uses ordinary text and line-break tags for much of its content.

**Observation:** Trafilatura preserves the text, but heading detection does not capture the section titles in the inspected pages.

**File 4: pmuni0036 – pazamozhi nAnUru**

- Original HTML contains the Tamil title, author details, introductory information and poems.
- Parsed content preserves Tamil poems, title, author and poem numbers.
- Section headings appear in the extracted text.
- The inspected pages have empty heading metadata.
- Some numbering and formatting artifacts are visible in the extracted Markdown.

**Observation:** Trafilatura preserves readable Tamil content, but heading metadata is empty. Plain tag stripping is faster.

### 5. Quick Inspection of the Remaining Six Files

The first parsed page of each remaining file was sampled.

**File 5: pmuni0016 – nAlaTiyAr**

- Tamil title, author contribution information and poems are present.
- The extracted content includes section titles.
- Heading metadata contains two entries.

**Observation:** Trafilatura extracts more text and retains the same number of headings as plain tag stripping.

**File 6: pmuni0024 – AcarakkOvai**

- Tamil title and author details are present.
- Introductory information and Unicode instructions are also extracted.
- Heading metadata contains one entry.

**Observation:** Trafilatura extracts slightly more text, with the same heading count.

**File 7: pmuni0025 – patinenkiizkannakku noolkaL-I**

- Tamil titles and author details for multiple literary works are present.
- Introductory information and document metadata are extracted.
- Both parsers detect five headings.

**Observation:** Plain tag stripping is faster and extracts more characters. The additional text should be checked for useful content or boilerplate.

**File 8: pmuni0027 – patinenkiizkannakku noolkaL-II**

- Tamil titles and details of multiple literary works are present.
- Introductory information and document metadata are extracted.
- Both parsers detect five headings.

**Observation:** Plain tag stripping is faster and extracts more characters with the same heading count.

**File 9: pmuni0029 – patinenkiizkannakku noolkaL-III**

- Tamil titles and author details are present.
- The document contains information about multiple literary works.
- Both parsers detect four headings.

**Observation:** Plain tag stripping is faster and extracts more characters. Content quality should be checked before making a final parser decision.

**File 10: pmuni0057 – puRanAnURu**

- Parsed content contains readable Tamil poems and poem-related details.
- The inspected database page has empty heading metadata.
- The comparison script detected two headings with plain tag stripping.

**Observation:** Plain tag stripping is considerably faster and detects two headings, but their correctness needs verification.

### 6. Tables, Headings and Text Quality

- The comparison script reported zero detected tables across the 10 files.
- No actual HTML tables were identified in the inspected source portions.
- Some documents have section headings in extracted text, but these are not always captured in structured heading metadata.
- Tamil poems, titles and author details are generally preserved.
- Some formatting artifacts, escaped numbering and special characters require checking.
- Plain tag stripping is faster in all 10 measured comparisons.
- More extracted characters do not automatically mean better extraction quality.

### 7. Parser Choice

For the current Project Madurai HTML corpus, **Trafilatura is the preferred general-purpose parser**, based on the four detailed original-versus-parsed inspections.

Reasons:

1. It produces readable extracted Tamil text.
2. It preserves poems, titles, author details and document content.
3. It provides useful Markdown formatting.
4. It generally extracts more characters in the detailed inspections.

However, plain tag stripping is considerably faster and performs better on some files according to the measured character counts and heading counts.

The main improvement needed is better detection of section headings in structured heading metadata.

### 8. PDF Parser Comparison

The current corpus contains 15 Project Madurai HTML files and one Markdown file. No PDF files were available.

Therefore, PyMuPDF and pypdf could not be compared using the current corpus.

No PDF parser winner was selected because there was no PDF test data.

### 9. Final Conclusion

Trafilatura is selected as the preferred general-purpose parser for the current HTML corpus because it preserves readable Tamil content and useful document structure.

Plain tag stripping is faster and may be suitable for simpler files, but speed and character count alone are not sufficient to determine extraction quality.

The main limitation identified is inconsistent section-heading detection in structured heading metadata.

All 10 HTML files have been compared using the parser comparison script. Four files have been inspected in detail against their original HTML and parsed database content. The remaining six files have been sampled through their parsed first pages and comparison metrics.

---


# Day 7 – Parsing My Corpus

### 1. Corpus Parsing Results

- Files in the manifest: 19 actual downloaded file records (excluding 5 repository metadata records).
- Successfully parsed manifest files: 19.
- Additional database document: 1 GitHub repository-tree JSON file not listed in the manifest.
- Total parsed database documents: 20.
- Recorded parse failures: 0.
- Pages in PostgreSQL for the parsed corpus: 692.
- Parsing coverage: 100% of manifest file records.

The database contains 1,350 documents and 2,022 pages in total. The Day 7 parsed-corpus count of 692 pages includes only the HTML, JSON, Markdown and text source documents.

### 2. Failures by Reason

| Reason | Files | What I did |
|---|---:|---|
| No recorded parse failures | 0 | No parse-failure fixes were required. |

- The one I fixed: Not applicable. No file was recorded in the parse_failures table.
- An additional GitHub repository-tree JSON document was present in the database but not in the manifest. It was identified by checking its database metadata and local file path.

### 3. What I Saw When I Read My Parsed Pages

**A page where heading metadata was extracted:**
- Document: `project madurai pmuni0047 d9bdd85c`
- Page: 1
- Heading metadata:
  - `naanmaNikkaTikai of viLampinaakanaar`
  - `nAnmaNikkaTikai of viLampinAkanAr`

Another example:
- Document: `project madurai pmuni0048 c414893b`
- Page: 1
- Heading: `tirikaTukam of nallaatanaar`

**Something that came out wrong:**
- Document: `project madurai pmuni0057 b743c7f2`
- Page: 68
- Tamil poem content was readable, but structured heading metadata was empty (`[]`).
- Heading metadata was empty across all 79 pages of this document.

**A table:**
- The parser comparison detected zero tables in all 10 inspected HTML files.
- No actual HTML table was identified in the inspected source portions, so there was no table available to compare as a Markdown grid or loose text.

### 4. My Parser Choice

- For HTML, I prefer Trafilatura because it preserved readable Tamil content and extracted more characters in 7 out of 10 files.
- Plain tag extraction was faster in all 10 files, but Trafilatura preserved useful content and structure in several inspected documents.
- No PDFs were present in my current corpus, so I could not compare PyMuPDF and pypdf on actual PDF files.
- PyMuPDF and pypdf were installed, but PDF parser selection remains unverified.
- A kind of document neither parser handles perfectly: legacy HTML documents where section headings appear in the text but are not represented as structured heading metadata.

### 5. One Thing That Went Wrong Today and How I Fixed It

- The `scripts/compare_parsers.py` file was initially missing.
- I created the script and ran it against the 10 largest HTML files.
- It recorded extracted characters, heading counts, table counts and processing times for both parsers.

### 6. Day 7 Verification Summary

- Successfully parsed all 19 downloaded manifest file records.
- Identified one additional GitHub repository-tree JSON document in the database.
- Total parsed database documents: 20.
- Recorded parse failures: 0.
- Pages in the parsed corpus: 692.
- Parsing coverage of manifest file records: 100%.
- Confirmed parser idempotency.
- Compared two HTML extraction approaches on 10 files.
- Manually inspected 4 original HTML files and their parsed content.
- Inspected samples from the remaining 6 files.
- Verified that heading metadata can be empty for some legacy HTML documents.
- No PDFs were available for PDF parser comparison.

Day 7 parsing and verification are complete. The parser is idempotent, all manifest file records were parsed, and no parse failures were recorded. Trafilatura is the preferred HTML parser based on the content inspection and comparison results.

# Day 8 – LLM Gateway, Streaming API and Usage Tracking

## 1. LLM Provider Configuration

- Configured Gemini as the primary LLM provider.
- Configured Groq as the fallback provider.
- Primary model: `gemini-3.6-flash`
- Fallback model: `openai/gpt-oss-20b`
- Used HTTPX to communicate with the providers.
- Configured API keys through environment variables.
- Tested both providers successfully using the LLM ping script.

**Provider ping results:**

| Provider | Model | Result | Response time |
|---|---|---|---:|
| Gemini | gemini-3.6-flash | Success | 1.826 s |
| Groq | openai/gpt-oss-20b | Success | 0.919 s |

**Observation:** Gemini 3.8 Flash timed out during testing, so Gemini 3.6 Flash was selected as the working primary model.

## 2. Database Model and Migration

- Created the `LlmCall` database model.
- Added fields to track provider, model, request ID, prompt version, status, errors, input tokens, output tokens, latency, cost and fallback usage.
- Created the Alembic migration for the `llm_calls` table.
- Applied the migration successfully to Neon PostgreSQL.
- Verified that the migration was applied using `alembic current`.

**Observation:** LLM call information can now be stored and tracked in Neon PostgreSQL.

## 3. LLM Gateway Implementation

Implemented the LLM gateway with:

- Gemini primary provider.
- Groq fallback provider.
- Retry handling.
- Circuit breaker.
- Streaming responses.
- Token usage tracking.
- Estimated rupee cost calculation.
- Database logging of provider calls.
- FakeLLM support for testing.

**Observation:** The gateway can handle provider failures and switch to the fallback provider.

## 4. Streaming Chat API

Implemented the following API endpoints:

- `POST /v1/chat` – accepts a user question and returns a streaming response.
- `GET /v1/usage` – provides daily usage and cost summaries.
- `GET /health` – checks application health.

Created the system prompt in:

`prompts/chat_system_v1.md`

The prompt instructs KuralGPT to:

- Help teachers explore Thirukkural.
- Explain concepts in simple Tamil and English.
- Avoid inventing Thirukkural couplets.
- Admit uncertainty when information is unavailable.
- Politely decline unrelated questions.

Also created `scripts/ask.py` to test the chat gateway from the terminal.

**Observation:** The streaming chat API and CLI were tested successfully.

## 5. English vs Tamil Token Experiment

Compared token usage using the same refund-related question in English and Tamil.

| Test | Input tokens | Output tokens | Cost |
|---|---:|---:|---:|
| Baseline – Hi | 181 | 56 | ₹0.032846 |
| English refund question | 189 | 27 | ₹0.023085 |
| Tamil refund question | 197 | 18 | ₹0.020449 |

**Message token calculation:**

- English: 189 − 181 = 8 tokens
- Tamil: 197 − 181 = 16 tokens
- Tamil/English ratio: 16 ÷ 8 = 2×

**Observation:** In this experiment, the Tamil message used twice as many input tokens as the English message. Both questions were correctly identified as outside KuralGPT's Thirukkural-focused scope.

## 6. Uncertainty and Off-topic Tests

### Board examination question

**Question:** Which Thirukkural will be asked in this year's board exam?

**Result:** KuralGPT admitted that it was not sure and advised checking the official syllabus and examination guidelines.

### Off-topic question

**Question:** Who won the 2011 Cricket World Cup?

**Result:** KuralGPT declined politely because the question was outside its intended Thirukkural-focused scope.

**Observation:** Both tests behaved as expected. The model avoided unsupported predictions and maintained its intended subject focus.

## 7. Document-specific Hallucination Tests

Tested questions whose answers were available in the Week 1 project documentation.

| Question | Correct answer | KuralGPT response |
|---|---|---|
| How many records were available during the Week 1 readiness check? | 20 | I am not sure |
| What is the live application URL of KuralGPT? | https://kuralgpt.onrender.com | I am not sure |
| Which database was used for database integration? | PostgreSQL using Neon | I am not sure |
| What was the main purpose of KuralGPT? | Help teachers find suitable Thirukkural couplets and explain them in Tamil and English without inventing couplets. | Correct answer |
| How many checks passed in the Week 1 self-check? | 33/33 | I am not sure |

**Observation:** The model did not have access to the project documentation through retrieval. It admitted uncertainty for most document-specific questions instead of inventing answers. One question was answered correctly through the fallback provider.

### Invalid Kural number and hallucination prevention test

**Question:** Give Thirukkural number 1345 about using mobile phones responsibly in school, with its Tamil text and English meaning.

**Expected result:** KuralGPT should identify that Kural 1345 does not exist because the Thirukkural contains only 1,330 couplets. It should not invent Tamil text or an English translation.

**Actual result:** KuralGPT correctly stated that number 1345 does not exist and explained that mobile phones are modern devices. It suggested authentic chapters related to self-control and education.

- Provider: Gemini 3.6 Flash
- Input tokens: 207
- Output tokens: 122
- Cost: ₹0.058211
- Fallback: No

**Conclusion:** No fabricated couplet or translation was produced. The invalid-number test passed. No actual hallucinated project-specific detail was captured during these tests.

## 8. Fallback and Circuit Breaker Experiment

### Provider fallback test

- Temporarily configured an invalid Gemini model: `gemini-no-such-model`.
- Gemini returned HTTP 404.
- Groq (`openai/gpt-oss-20b`) successfully handled the requests.
- Failed Gemini calls and successful Groq fallback calls were recorded separately in Neon.

### Circuit breaker test

- After three Gemini failures, the circuit breaker opened.
- The fourth request skipped Gemini and went directly to Groq.
- After the waiting period, the half-open test attempted Gemini again.
- Gemini failed, and Groq handled the request.

### Recovery test

- Restored the primary model to `gemini-3.6-flash`.
- Gemini successfully answered the next request.
- `fallback_used` was `false`.

**Observation:** Provider fallback, circuit breaker opening, half-open retry and recovery were successfully verified using the persistent API server.

## 9. Local English and Tamil Response Tests

| Question | Input tokens | Output tokens | Total response time | Cost |
|---|---:|---:|---:|---:|
| First Kural – English | 193 | 94 | 11.917 s | ₹0.047239 |
| First Kural – Tamil | 195 | 121 | 11.104 s | ₹0.057000 |

**Observation:** Both English and Tamil questions received responses from Gemini 3.6 Flash. These timings represent total CLI response time; first-token timing was not separately measured.

## 10. Usage Report and Neon Verification

**API endpoint:** `GET /v1/usage?days=7`

Latest verified usage result:

| Metric | Result |
|---|---:|
| Provider calls recorded | 30 |
| Errors | 7 |
| Fallback calls | 8 |
| Input tokens | 4,755 |
| Output tokens | 6,652 |
| Estimated total cost | ₹0.7017 |

**Neon database verification:**

- Failed Gemini calls were recorded with `status = error`.
- Successful Groq calls were recorded with `fallback_used = true`.
- The recovered Gemini call was recorded with `status = ok` and `fallback_used = false`.

**Observation:** The updated usage endpoint successfully summarizes provider calls, errors, fallbacks, token counts and estimated rupee costs from Neon.

*Note: The cost is an estimated provider list-price calculation, not necessarily the actual amount billed.*

## 11. Testing and Code Quality

- Unit and integration tests completed.
- Final test result: **107 passed, 1 warning**.
- Ruff lint checks passed.
- Ruff formatting checks passed.
- Verified the real `/v1/usage` endpoint using Neon data.
- Verified database logging and provider fallback records.

**Final verification:**

- `uv run poe test` – 107 passed.
- `uv run poe lint` – All checks passed.
- `uv run ruff format .` – 72 files already formatted after formatting.

The remaining warning relates to optional PySocks support in urllib3 and did not affect the tests.

## 12. Render Deployment Configuration

- Opened the existing KuralGPT web service in Render.
- Configured `GEMINI_API_KEY` and `GROQ_API_KEY` as environment variables.
- Kept API keys outside the Git repository.
- Updated the Dockerfile to copy the `prompts` directory into the container.
- Render service currently shows **Live**.

**Live application URL:** https://kuralgpt.onrender.com

*Note: The service is Live, but the final public URL chat and usage endpoint verification is still pending.*

## 13. One Thing That Went Wrong and How I Fixed It

During testing, the Gemini 3.8 Flash model timed out. I tested Gemini 3.6 Flash and confirmed that it worked successfully, so I changed the primary model configuration.

During the fallback experiment, Gemini returned HTTP 404 because I temporarily configured an invalid model name. The gateway successfully switched to Groq. I also verified that the circuit breaker stopped sending requests to Gemini after repeated failures.

I restored Gemini 3.6 Flash after completing the experiment and confirmed that it responded successfully.

## 14. Day 8 Conclusion

Completed the LLM gateway with Gemini as the primary provider and Groq as the fallback provider. Implemented streaming chat, database logging, token and cost tracking, retry handling, circuit breaker and usage reporting.

Tested English and Tamil questions, uncertainty handling, off-topic questions, invalid Kural numbers, provider fallback and circuit breaker behaviour.

The local implementation and automated tests are passing. The Render service is Live, and both public chat and usage endpoints have been successfully verified.

**Next step:** Connect document retrieval so KuralGPT can answer questions using the actual project documents instead of relying only on the model's general knowledge.

## D08 - Final Deployment and Live Testing

### Deployment
- Successfully deployed KuralGPT on Render.
- Public URL: https://kuralgpt.onrender.com
- Verified the `/v1/chat` and `/v1/usage` endpoints.
- Connected the application to Neon PostgreSQL for LLM usage logging.

### LLM Integration
- Gemini configured as the primary provider.
- Groq configured as the fallback provider.
- Implemented streaming chat responses.
- Implemented token usage and estimated cost tracking.
- Tested fallback and circuit-breaker behaviour.

### Live Chat Test
- Question: "What is the first kural and what does it mean?"
- Result: Successfully received Kural 1 with Tamil and English explanations.
- Provider used: Groq (fallback).
- Model: `openai/gpt-oss-20b`
- Input tokens: 255
- Output tokens: 961
- Reported latency: 33,090 ms (33.09 seconds).
- Estimated cost: INR 0.029205.
- Fallback used: Yes.

### Usage Verification
- Total provider calls: 34
- Input tokens: 5,265
- Output tokens: 7,189
- Estimated total cost: INR 0.720595.
- Errors: 9
- Fallbacks: 10

### Observations
- Public chat API and usage tracking are working.
- Groq fallback successfully handled the live request.
- Response latency needs further optimization.
- Retrieval integration and document-grounded answers are planned for Week 3.

### D08 Outcome
Completed the LLM gateway, provider fallback, streaming API, Neon usage logging, cost tracking, experiments and Render deployment. Live API testing was successful.

## Stretch Task 1 - Latency Percentiles

Calculated latency percentiles from Neon PostgreSQL
using successful LLM calls (`status = 'ok'`).

- p50 latency: 4,312 ms (4.312 seconds)
- p95 latency: 36,432 ms (36.432 seconds)

### Day 1 Performance Target
- Target p95: under 6 seconds.
- Actual p95: 36.432 seconds.
- Status: Target not met.

### Observation
The median latency is 4.312 seconds, but the p95
latency is significantly higher at 36.432 seconds.
Further investigation and optimization are required.

## Stretch Task 2 - LLM Provider Status and Circuit Breaker

### API Endpoint
Added `GET /v1/llm/status` to display each configured LLM provider's:
- Provider name
- Model name
- Circuit-breaker state

### Automated Tests
Added two unit tests using `FakeLLM`:
- Verify provider details and initial breaker states.
- Verify that the API reflects circuit-breaker state changes.

Both tests passed.

### Live Circuit Breaker Experiment

Tested using the local API with an intentionally invalid Gemini model and Groq as fallback.

| Experiment | Observed result |
|---|---|
| Initial state | Gemini: closed; Groq: closed |
| After three Gemini failures | Gemini: open; Groq: closed |
| After 30-second cooldown | Gemini: half-open; Groq: closed |
| Recovery attempt with invalid Gemini model | Gemini failed; Groq handled the request |
| Immediate status check | Gemini: open; Groq: closed |

### Result
The status endpoint successfully displayed the circuit-breaker transitions. Groq continued serving requests when Gemini failed. The failed half-open recovery attempt correctly returned Gemini's breaker to the open state.

The original Gemini model configuration was restored after testing.

## Stretch Task 4 - Short Conversation Memory

### Implementation
Updated `ChatRequest` to support an optional `history` list.

- Each history message contains `role` and `content`.
- Allowed roles: `user` and `assistant`.
- Maximum history: 6 earlier messages.
- Each message content is limited to 4,000 characters.
- Conversation history is inserted between the system prompt and the latest user message.
- Existing streaming and non-streaming behavior is preserved.

### Automated Tests
Added tests to verify:
- History is passed in the correct order.
- Empty history is accepted.
- Six history messages are accepted.
- More than six messages are rejected.
- Invalid history roles are rejected.

Targeted chat API tests: 14 passed.
Lint and formatting checks: Passed.

### Live Conversation Experiment

Asked the first question:
"Explain Thirukkural 1."

Then asked the follow-up:
"And for children?"

The previous user and assistant messages were included in the second request.

| Metric | First request | Follow-up |
|---|---:|---:|
| Provider | Gemini | Groq |
| Input tokens | 187 | 970 |
| Output tokens | 136 | 199 |
| Latency | 7,188 ms | 5,344 ms |
| Fallback used | No | Yes |

### Observations
- Input tokens increased from 187 to 970.
- The increase of 783 tokens confirms that conversation history was included.
- Gemini failed during the follow-up request, and Groq successfully handled the fallback.
- Tamil text appeared incorrectly encoded in the displayed response and requires separate investigation.

### Result
The optional short conversation memory feature was successfully implemented and verified through a live API experiment.

## Stretch Task 3 - Local Ollama Model

### Installation and Configuration

Installed Ollama on Windows and downloaded the `llama3.2:1b` model (approximately 1.3 GB).

Verified that the Ollama API was running successfully at:

`http://localhost:11434`

Updated the `.env` configuration to use Ollama as the fallback provider:

- `LLM_FALLBACK_BASE_URL=http://localhost:11434/v1`
- `LLM_FALLBACK_MODEL=llama3.2:1b`
- `GROQ_API_KEY=ollama`

No Python code changes were required.

### Direct Ollama Test

Sent a test question:

"Explain Thirukkural in one simple sentence."

Result:
- Model: `llama3.2:1b`
- Input tokens: 37
- Output tokens: 43
- Total tokens: 80

Ollama successfully generated a response.

### KuralGPT Fallback Test

Temporarily configured an invalid Gemini model to trigger fallback.

KuralGPT successfully switched to the local Ollama model.

Observed results:
- Configured provider name: `groq`
- Actual model: `llama3.2:1b`
- Input tokens: 209
- Output tokens: 6
- Latency: 8,188 ms
- Fallback used: True
- Estimated cost: INR 0

The model returned "I am not sure."

This confirmed that KuralGPT successfully connected to Ollama through its OpenAI-compatible API.

### Gemini Comparison

After restoring the Gemini configuration, another request was attempted.

Gemini returned HTTP 429 because the available API quota was exceeded. KuralGPT successfully used Ollama as the fallback again.

A fair live speed and answer-quality comparison with Gemini could not be completed because of this quota limitation.

### Observations

- Local Ollama installation and model loading were successful.
- KuralGPT automatically switched to Ollama when Gemini failed.
- The local model generated responses without an external API usage charge.
- The tested answer quality was limited and requires further evaluation.
- Gemini comparison remains pending until API quota becomes available.

### Result

Local Ollama integration and automatic fallback were successfully verified without Python code changes.
