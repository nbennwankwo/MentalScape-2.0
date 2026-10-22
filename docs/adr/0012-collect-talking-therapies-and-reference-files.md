# ADR 0012 Collect NHS Talking Therapies and the reference files

- **Status** Proposed
- **Date** 2026-10-22
- **Proposed by** Claude, for Kemi Ben-Nwankwo to accept

## Context

Phase 1 needs three more kinds of source next to MHSDS.

1. **NHS Talking Therapies monthly statistics.** These are published by NHS England in the same way as MHSDS, with release pages and download cards, and the same bot challenge on the pages (ADR 0011). The publication was renamed from IAPT in May 2023, and the older releases stay on a separate series page with different file names and version words. Before May 2023 each release carried a Final month and a Primary month. Until October 2023 it carried a Performance month and a Provisional month.
2. **Reference files at fixed addresses.** The English Indices of Deprivation 2025, ONS LSOA population estimates and ONS geography lookups are single files on gov.uk, ons.gov.uk and the ONS Open Geography Portal.
3. **Population on the April 2026 ICB boundaries.** ONS had not yet published estimates on the new boundaries.

Also, workflow artifacts cannot be downloaded from the development sandbox, but release assets can, and changes to collectors need to be tried on real files before they are merged.

## Decision

1. **One engine for NHS England series.** Everything shared by MHSDS and NHS Talking Therapies lives in `mentalscape.ingest.series`. Each series supplies a classifier, a catalogue and an asset prefix. The browser script walks every series page of a publication, including the IAPT page.
2. **Talking Therapies versions.** Final and Performance are wanted. Primary and Provisional are treated as the same thing, an early version replaced a month later, and are not collected. The activity file is the main file, and the data quality file is collected for later caveats.
3. **Reference files are registered, not discovered.** Each one is listed under `reference_files` in `config/sources.yaml` with an id, an edition and a URL, and collected into a `data-reference` release. A new edition is a new entry, so old builds stay repeatable. The collector rejects a file that looks like an error page or lacks the expected header.
4. **Population and deprivation are built up from LSOAs.** LSOA estimates and LSOA deprivation scores are added up to Sub ICB, ICB and local authority using each ONS lookup edition, which is how ONS builds its own health geography estimates. This gives figures on the April 2026 boundaries now, and they can be compared with ONS's own once published.
5. **Local authority changes come from ONS lookups only.** The April 2023 successors are derived by joining ONS district and county lookups. Nothing is typed by hand. Suppressed values are never added up to bridge a change.
6. **A staging release for trials.** Pull request runs of the ingest workflows publish to a `data-staging` prerelease, marked as trial only. The warehouse never reads it, and production releases are written only from `main`.

## Alternatives considered

- **Use the 13 month time series files instead of monthly activity files.** Fewer downloads, but each file restates earlier months, which hides revisions and breaks the one file per month rule of ADR 0003.
- **A third party mirror of NHS England's pages.** One exists, but using it would get around NHS England's bot challenge by another route, which ADR 0011 rules out.
- **Wait for ONS population on the new ICB boundaries.** Would leave every April 2026 rate without a denominator for months.

## Consequences

Every Phase 1 source is collected the same way, with checksums and a manifest. Talking Therapies needs the same short monthly browser step as MHSDS. Population figures for 2025 and 2026 use the latest ONS estimates, mid-2024, until ONS publishes more, and the warehouse says so wherever they are used.
