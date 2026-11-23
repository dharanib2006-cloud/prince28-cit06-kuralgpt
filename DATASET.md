# KuralGPT Dataset

## 1. Dataset overview

The initial KuralGPT corpus contains all 1,330 Thirukkural couplets authored by Thiruvalluvar.

**Source repository:** https://github.com/tk120404/thirukkural

**Pinned commit:** `cf3ff6c5a73c23b4092913156830457caab65fd4`

## 2. Downloaded files

| File | Description |
|---|---|
| `thirukkural.json` | All 1,330 kurals and their text fields |
| `detail.json` | Paal, Iyal and Adhigaram hierarchy |

The downloaded files are stored under `data/raw/`.

## 3. Dataset fields

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

## 4. Verification

- Total Kural records: 1,330.
- `mv` populated: 1,330 / 1,330.
- `sp` populated: 1,330 / 1,330.
- `mk` populated: 1,330 / 1,330.
- English translation and explanation fields are present.
- Repository README confirms all eleven fields are populated.
- `detail.json` provides the Paal → Iyal → Adhigaram hierarchy.
- SHA-256 hashes and download details are recorded in `data/manifest.jsonl`.

## 5. Licence and attribution status

The source repository includes an Apache License, Version 2.0 (`LICENSE`), downloaded from the pinned repository commit.

The Apache License permits reproduction, modification and distribution of the work covered by the licence, subject to its conditions.

The repository README attributes the commentary fields as follows:
- `mv`: Dr. Mu. Varadarasanar
- `sp`: Solomon Pappaiah
- `mk`: Mu. Karunanidhi

**Pending:** Independently verify the rights and reuse permissions for the three modern commentary texts. The repository licence alone does not establish that every third-party text is covered by it.

## 6. Known gaps

- Separate reuse permissions for the three commentary texts still need verification.
- Additional Project Madurai sources and other Tamil classics are not yet included in this initial corpus.

## 7. Current status

The initial 1,330-Kural data target is achieved. The dataset includes three Tamil commentary fields, exceeding the initial requirement of two. The repository's Apache-2.0 licence file has been downloaded and inspected. Separate commentary rights verification remains open.
