# KuralGPT Ingestion Report

<!-- generated:start -->
## Generated Ingestion Measurements

- Report generated: **2026-11-27T23:02:53+05:30**
- Source documents: **20**
- Parsed pages: **715**
- Unresolved latest failed sources: **1**
- Recorded extraction calls: **288**
- Recorded extraction input tokens: **305,344**
- Recorded extraction output tokens: **100,194**
- Total recorded extraction tokens: **405,538**

### Token measurement note

Token counts are summed from recorded LLM extraction calls in the database. They include repeated calls and retries, so they measure provider usage rather than the unique token size of the corpus. Compare them with the planning estimate in `docs/CAPACITY.md` with this difference in scope in mind.

<!-- generated:end -->

## What I learnt

- I learned how Redis and ARQ allow the API to queue document-ingestion jobs while a separate background worker processes them.
- I learned why interrupted jobs may need to wait for their locks to expire, and how restarting the worker allows those jobs to be retried.
- I learned that using deterministic document IDs prevents duplicate database records, while metadata validation helps reject information that cannot be supported by the source document.
