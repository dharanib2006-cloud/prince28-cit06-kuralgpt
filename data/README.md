# KuralGPT Sample Data

## Source

The sample Thirukkural records in `sample_records.json` are derived from:

- Repository: https://github.com/tk120404/thirukkural
- Original data file: `thirukkural.json`
- Chapter metadata file: `detail.json`
- Source licence: Apache License 2.0

## Fields

| KuralGPT field | Source field |
|---|---|
| `id` | Generated from the Kural number |
| `kural_no` | `Number` |
| `paal` | Section name in `detail.json` |
| `adhikaram` | Chapter name in `detail.json` |
| `couplet_tamil` | `Line1` and `Line2` |
| `commentary_tamil` | `mv` |
| `meaning_english` | `Translation` |

`meaning_tamil` and `theme` are currently `null`. Simple Tamil explanations and themes will be added only after verification.

## Attribution

The original dataset is provided by the contributors of the tk120404/thirukkural repository under the Apache License 2.0. The KuralGPT sample records are derived from that dataset.

The upstream licence is preserved separately with this project.
