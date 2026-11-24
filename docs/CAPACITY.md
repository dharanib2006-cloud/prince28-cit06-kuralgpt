# KuralGPT Capacity Report

<!-- generated:start -->
### Generated measurements

- Current downloaded files: **2.31 MB**
- Current Kural records: **1,330**
- Current PDF pages: **0**
- Full corpus planning target: **3,000 PDF pages**
- Estimated current corpus tokens (planning assumption): **133,000**
- Estimated current corpus chunks at 500 tokens each: **266**
- Full corpus target: **3,000 PDF pages** (additional text not yet collected)
- Vector dimensions: **1,024**
- Estimated raw vector storage (float32): **1.04 MB**
- Example embedding budget: **$0.20 (INR 19.00)**

### What I conclude

1. **Is embedding cost a problem?** The example budget is $0.20 (approximately INR 19.00); confirm the actual provider price and token count before deployment.

2. **Do vectors and text fit in free Postgres?** Yes, the current Neon Free Plan uses 32.27 MB out of its 1 GB storage allowance, leaving approximately 0.97 GB. The estimated raw vector storage is 1.04 MB. Actual database usage will also include text, indexes, metadata and row overhead. The downloaded source files are separate from database storage unless loaded into the database.

3. **Which number is least certain?** The token and chunk estimate is rough; measure actual extracted text tokens and chunk counts from the final corpus.

4. **What changes if the corpus grows 10 times?** Text, vectors and index storage will grow substantially. Re-measure actual usage, embedding cost and database limits before scaling.
<!-- generated:end -->

## Actual Database Capacity - Neon

The following figures were checked in the Neon dashboard on 24 November 2026.

| Metric | Actual value |
|---|---:|
| Plan | Free |
| Postgres storage allowance | 1 GB per project |
| Current Postgres storage used | 32.27 MB |
| Approximate remaining storage | 0.97 GB |
| Compute allowance | 100 hours |
| Network transfer allowance | 5 GB |
| Current compute usage | 1.04 CU-hours |
| Current network transfer | 247.31 kB |

### Capacity Conclusion

The current database usage of 32.27 MB is comfortably within the 1 GB Free Plan storage allowance. The estimated raw vector storage is 1.04 MB, but actual database growth will also depend on text, indexes, metadata and row overhead.

These figures represent the dashboard usage at the time of checking and may change as the project grows.
