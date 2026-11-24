# KuralGPT Capacity Report

<!-- generated:start -->
### Generated measurements

- Current downloaded files: **4.24 MB**
- Current Kural records: **1,330**
- Current PDF pages: **0**
- Full corpus planning target: **3,000 PDF pages**
- Estimated text tokens (planning assumption): **133,000**
- Estimated chunks at 500 tokens each: **266**
- Vector dimensions: **1,024**
- Estimated raw vector storage (float32): **1.04 MB**
- Example embedding budget: **$0.20 (INR 19.00)**

### What I conclude

1. **Is embedding cost a problem?** The example budget is $0.20 (approximately INR 19.00); confirm the actual provider price and token count before deployment.

2. **Do vectors and text fit in free Postgres?** Compare the estimated 1.04 MB of raw vectors plus 4.24 MB of source files with the storage limit shown in your actual database dashboard. Database indexes and row overhead are not included.

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
