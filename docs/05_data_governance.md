# Data governance

## What data this project holds

Only published, aggregate statistics released under the Open Government Licence. No patient level or identifiable data is held, processed or requested by this repository.

## Rules

1. **No data in git.** Source files are downloaded by the pipeline and kept out of version control. Only small derived reference tables, such as the measure catalogue, are committed.
2. **Suppression is respected.** Values published as an asterisk stay unknown. They are never back calculated from totals or neighbouring cells.
3. **Small numbers are not re-identified.** No output combines breakdowns in a way that could reveal a suppressed value.
4. **Caveats travel with numbers.** Dashboards and the GenAI analyst show data quality warnings, such as NHS England's notice that MHS148 is overstated by 25 to 30 percent, wherever the affected measure appears.
5. **Provenance is recorded.** Every loaded file has its source URL, release version, download date and checksum stored in the manifest.
6. **Secrets stay out of the repository.** Keys live in a local `.env` file or in GitHub Actions secrets, never in code.

## If patient level data is ever granted

Any record level data would live only in the environment the data sharing agreement names, never in this repository or on a personal laptop, and would follow the agreement's rules on storage, access and deletion. The public repository would only ever contain code and aggregate outputs that pass disclosure control.

## Licence attribution

Contains public sector information licensed under the Open Government Licence v3.0. Source NHS England and the Office for National Statistics.
