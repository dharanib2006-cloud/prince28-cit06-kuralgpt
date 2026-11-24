# KuralGPT Dataset

## 1. Dataset Overview

The initial KuralGPT corpus contains all 1,330 Thirukkural couplets authored by Thiruvalluvar.

**Source repository:** https://github.com/tk120404/thirukkural

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
- Project Madurai sources and additional Tamil classics have not yet been collected.
- The full corpus target is to include all available Thirukkural commentaries and five additional Tamil classics from Project Madurai, estimated at approximately 3,000+ pages.

## 9. Usage and Privacy

- Every Kural answer should link back to its original source.
- The dataset collection process does not require personal user data.
- The system should avoid generating unsupported or invented Kural text.

## 10. Current Status

The initial target of all 1,330 Kurals has been achieved.

The dataset includes three Tamil commentary fields, exceeding the initial requirement of two. The repository's Apache-2.0 licence file has been downloaded and inspected. Separate commentary rights verification remains open.

<!-- generated:start -->
### Generated measurements

- Kural records detected: **1,330**
- Files measured: **5**
- Total downloaded size: **2.31 MB** (0.0023 GB)
- PDF files: **0**
- PDF pages counted: **0**

| File | Size (bytes) | PDF pages | Notes |
|---|---:|---:|---|
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-detail-9c7ff7d8.json` | 50,437 | 0 | - |
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-LICENSE-7bbeecd6.txt` | 11,357 | 0 | - |
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-README-f0127575.md` | 4,655 | 0 | - |
| `data/raw/github-tk120404-thirukkural/github-tk120404-thirukkural-thirukkural-03688010.json` | 2,349,854 | 0 | - |
| `data/raw/github-tk120404-thirukkural-tree/github-tk120404-thirukkural-tree-master-c042b115.json` | 1,305 | 0 | - |
| **Total** | **2,417,608** | **0** | - |
<!-- generated:end -->
