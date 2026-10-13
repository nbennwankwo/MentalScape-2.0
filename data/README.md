# Data folder

Nothing in this folder is committed to git except this file and the small tables in `reference/`.

| Folder | Holds | Committed |
|---|---|---|
| `raw/` | Source files exactly as published, organised by source and release month | no |
| `interim/` | Working outputs such as profiles and extracted CSVs | no |
| `processed/` | Analysis ready extracts produced by the pipeline | no |
| `reference/` | Small derived tables such as the MHSDS measure catalogue and change log events | yes |

## Getting the raw data

Phase 1 adds an automated download. Until then, place MHSDS main data files (CSV or the published zip) in `raw/mhsds_monthly/` and run

```
make profile
make changelog
```

## Reference tables

| File | One row per |
|---|---|
| `mhsds_release_summary.csv` | release month, with its shape, format and change counts |
| `mhsds_measure_catalogue.csv` | measure ID, with first and last release seen and its name history |
| `mhsds_measure_events.csv` | measure added, removed or renamed between two releases |
| `mhsds_breakdown_events.csv` | breakdown added or removed between two releases |
| `mhsds_geography_events.csv` | organisation or area code added, removed or renamed |
| `mhsds_england_step_changes.csv` | sharp month on month jump in an England value, labelled one off or recurring |
