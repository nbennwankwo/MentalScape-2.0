# ADR 0009 Keep raw source files as GitHub Release assets

- **Status** Accepted
- **Date** 2026-10-22
- **Decided by** Kemi Ben-Nwankwo

## Context

The pipeline downloads NHS England files every month. Raw files must never go into git, but they still need a permanent home so that any past warehouse build can be repeated exactly, even if NHS England later moves or replaces a file. The full backfill from July 2022 covers several hundred files.

## Decision

Every downloaded file is stored as an asset on a single GitHub Release called `data-mhsds-monthly`. Each asset gets a name built from its kind, reporting month, version, revision and the first characters of its checksum, so two different files can never collide. Large CSV files are gzipped before upload. A `manifest.csv` asset lists every file with its source URL, original name, checksum, size and download date, and is the source of truth for what has been collected.

## Alternatives considered

- **GitHub Actions artifacts.** Free, but deleted after 90 days.
- **A cloud storage bucket.** Closest to industry practice, but needs an account and may cost money.
- **Git LFS.** Small free bandwidth allowance and mixes data into the code history.

## Consequences

Raw files are free to store, public and permanent. Redistribution is allowed under the Open Government Licence, so the release notes carry the attribution. A single release can hold up to 1,000 assets, which is enough for many years at the current rate, and a second release can be added later if needed.
