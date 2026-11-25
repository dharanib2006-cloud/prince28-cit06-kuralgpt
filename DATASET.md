# KuralGPT Dataset

## 1. Dataset Overview

The initial KuralGPT corpus contains all 1,330 Thirukkural couplets authored by Thiruvalluvar.

**Source repository:** [https://github.com/tk120404/thirukkural](https://github.com/tk120404/thirukkural)

**Pinned commit:** `cf3ff6c5a73c23b4092913156830457caab65fd4`

## 2. Product Purpose

KuralGPT is a Thirukkural value-education companion for Tamil teachers in Chennai government schools (Classes 6–10).

It helps teachers find a relevant Kural for a value or classroom situation and understand it in simple Tamil and English. The system must not invent or misquote couplets.

## 3. Downloaded Files

| File | Description |
|---|---|
| `thirukkural.json` | All 1,330 Kurals and their text fields |
| `detail.json` | Paal, Iyal and Adhigaram hierarchy |

The downloaded files are stored under `data/raw/`.

## 4. Dataset Fields

Each Kural record contains eleven fields:

| Field | Description |
|---|---|
| `Number` | Kural number (1–1330) |
| `Line1`, `Line2` | Tamil couplet lines |
| `Translation` | English translation |
| `mv` | Dr. Mu. Varadarasanar commentary |
| `sp` | Solomon Pappaiah commentary |
| `mk` | Mu. Karunanidhi commentary |
| `explanation` | English prose explanation |
| `couplet` | English verse couplet |
| `transliteration1`, `transliteration2` | Romanized Tamil lines |

## 5. Collection Method

The dataset was collected using `scripts/fetch.py`.

The downloader:
- Checks `robots.txt` before downloading.
- Limits concurrent requests to four.
- Applies a delay between requests to the same host.
- Supports resuming interrupted downloads.
- Records download details and SHA-256 hashes in `data/manifest.jsonl`.

## 6. Verification

- Total Kural records: **1,330**
- `mv` populated: **1,330 / 1,330**
- `sp` populated: **1,330 / 1,330**
- `mk` populated: **1,330 / 1,330**
- English translation and explanation fields are present.
- Repository README confirms all eleven fields are populated.
- `detail.json` provides the Paal → Iyal → Adhigaram hierarchy.
- SHA-256 hashes and download details are recorded in `data/manifest.jsonl`.

## 7. Licence and Attribution Status

The source repository includes an Apache License, Version 2.0 (`LICENSE`), downloaded from the pinned repository commit.

The Apache License permits reproduction, modification and distribution of the work covered by the licence, subject to its conditions.

The repository README attributes the commentary fields as follows:
- `mv`: Dr. Mu. Varadarasanar
- `sp`: Solomon Pappaiah
- `mk`: Mu. Karunanidhi

**Pending:** Independently verify the rights and reuse permissions for the three modern commentary texts. The repository licence alone does not establish that every third-party text is covered by it.

## 8. Known Gaps

- Separate reuse permissions for the three modern commentary texts still need verification.
- Additional Project Madurai sources and Tamil classics have not yet been collected.
- The full corpus target is to include all available Thirukkural commentaries and five additional Tamil classics from Project Madurai, estimated at approximately 3,000+ pages.

## 9. Usage and Privacy

- Every Kural answer should link back to its original source.
- The dataset collection process does not require personal user data.
- The system should avoid generating unsupported or invented Kural text.

## 10. Current Status

The initial target of all 1,330 Kurals has been achieved.

The dataset includes three Tamil commentary fields, exceeding the initial requirement of two. The repository's Apache-2.0 licence file has been downloaded and inspected. Separate commentary rights verification remains open.

The additional document parsing pipeline has also been implemented and tested. It supports HTML, JSON, Markdown, text and other supported file formats, with extracted page text and heading information stored in PostgreSQL.

**Parsing coverage: 100% of files** (20 parsed, 0 failed).

<!-- generated:start -->
### Generated measurements

- Kural records detected: **1,330**
- Files measured: **20**
- Total downloaded size: **4.24 MB** (0.0041 GB)
- PDF files: **0**
- PDF pages counted: **0**
- Successfully parsed files: **20**
- Failed files: **0**
- File parsing coverage: **100.00%**
- Successfully parsed pages: **692**
- Page parsing coverage: **Not yet measured**

| File | Size (bytes) | PDF pages | Notes |
|---|---:|---:|---|
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-detail-9c7ff7d8.json` | 50,437 | 0 | - |
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-LICENSE-7bbeecd6.txt` | 11,357 | 0 | - |
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-README-f0127575.md` | 4,655 | 0 | - |
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-thirukkural-03688010.json` | 2,349,854 | 0 | - |
| `data/raw/github-tk120404-thirukkural-tree/github-tk120404-thirukkural-tree-master-c042b115.json` | 1,305 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0002-291869e7.html` | 52,091 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0016-e486fc8d.html` | 164,292 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0022-93cb9d95.html` | 13,171 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0024-01033a52.html` | 54,208 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0025-48fe335a.html` | 70,488 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0027-9125683b.html` | 93,419 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0028-a852d112.html` | 204,029 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0029-2c0dc8d0.html` | 100,027 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0036-64d74aa8.html` | 183,340 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0038-502711e7.html` | 232,222 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0047-d9bdd85c.html` | 48,418 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0048-c414893b.html` | 47,028 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0055-869f5789.html` | 45,460 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0056-ce4cfceb.html` | 72,778 | 0 | - |
| `data/raw/project_madurai/project_madurai-pmuni0057-b743c7f2.html` | 648,456 | 0 | - |
| **Total** | **4,447,035** | **0** | - |

<!-- generated:end -->
