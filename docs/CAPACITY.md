# KuralGPT Capacity Report

<!-- generated:start -->

## Generated Measurements

| Metric | Measured / Estimated Value |
|---|---:|
| Current downloaded files | 4.24 MB |
| Current Kural records | 1,330 |
| Current PDF pages | 0 |
| Full corpus planning target | 3,000 PDF pages |
| Estimated text tokens (planning assumption) | 133,000 |
| Estimated chunks at 500 tokens each | 266 |
| Vector dimensions | 1,024 |
| Estimated raw vector storage (float32) | 1.04 MB |
| Example embedding budget | $0.20 (approximately ₹19.00) |

## What I Conclude

1. **Is embedding cost a problem?**

   The example embedding budget is approximately $0.20 (₹19.00). This is relatively small for the planning estimate. However, the actual embedding provider price and token count must be verified before deployment.

2. **Do vectors and text fit in free PostgreSQL?**

   The estimated raw vector storage is 1.04 MB, and the downloaded source files occupy 4.24 MB. These values should be compared with the actual database storage allowance. Additional space is required for database indexes, metadata, text records and row overhead.

3. **Which number is least certain?**

   The estimated token count and chunk count are planning assumptions. Actual extracted text tokens and chunk counts should be measured after processing the final corpus.

4. **What changes if the corpus grows 10 times?**

   Text, vector and index storage requirements will increase substantially. Database usage, embedding costs and available storage should be measured again before scaling.

<!-- generated:end -->

---

## Actual Database Capacity – Neon

**Database measurement date:** 27 November 2026

The database size was measured using:

```sql
SELECT pg_database_size(current_database());
```

### Actual Database Measurements

| Metric | Actual Value |
|---|---:|
| Database provider | Neon |
| Plan | Free |
| PostgreSQL storage allowance | 1 GB per project (previously verified) |
| Current database size | 15.39 MB |
| Database size in bytes | 15,392,768 bytes |
| Approximate remaining storage | 984.61 MB |
| Approximate storage used | 1.54% |
| Approximate storage remaining | 98.46% |

## Capacity Conclusion

The current PostgreSQL database occupies approximately **15.39 MB**, which is comfortably within the previously verified 1 GB Neon Free Plan storage allowance.

Approximately **984.61 MB (98.46%)** of the storage allowance remains available.

Actual storage consumption also depends on:

- Extracted document text and Kural records.
- Vector embeddings.
- Database indexes.
- Structured metadata.
- Database overhead.

These measurements represent database usage at the time of checking. Storage consumption may increase as more documents are processed and the project grows.

**Final observation:** The current database storage is sufficient for the project's present data. Actual capacity should be monitored as corpus extraction, metadata storage and future vector integration progress.
