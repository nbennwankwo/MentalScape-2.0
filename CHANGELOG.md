# Changelog

Notable changes to MentalScape 2.0. Dates are UK dates.

## Unreleased, Phase 1

- Decision records 0002 to 0007 accepted, 0009 to 0011 added and accepted, and 0012 and 0013 proposed
- Automated MHSDS ingest in `src/mentalscape/ingest`, with a classifier built from every card title published since 2022
- `Ingest MHSDS` GitHub Actions workflow publishing raw files and a checksummed manifest to the `data-mhsds-monthly` release
- Discovery moved to a browser step after NHS England's pages were found to challenge cloud servers (ADR 0011), with the catalogue committed as `data/reference/mhsds_catalogue.csv`
- Pipeline guide in `docs/data/pipeline.md`
- Fetch and load steps in `src/mentalscape/warehouse`, loading the preferred file of every month into a raw schema on DuckDB or PostgreSQL
- dbt project in `warehouse/` with staging, intermediate and mart models, a dated Sub ICB to ICB membership table and data tests drawn from the change log
- Date parsing for all five date styles NHS England has used, found when every End of Year Final file was loaded
- Fallback for the March 2026 final file, which gives 23 Sub ICBs only their post merger names, labelled as carried forward
- Known measures seed written by `make changelog`, with a warning for measure IDs the change log has not seen
- Synthetic fixture that reproduces the real traps, built and tested on PostgreSQL 16 in CI on every pull request
- Ingest code shared by NHS England series in `mentalscape.ingest.series`, with NHS Talking Therapies collected from both its current and its IAPT series pages
- `Ingest NHS Talking Therapies` and `Ingest reference files` workflows, publishing to the `data-talking-therapies-monthly` and `data-reference` releases
- Reference files registered under `reference_files` in `config/sources.yaml`, covering IoD 2025, ONS LSOA population estimates and ten ONS geography lookups
- Pull request trial runs publish to a separate `data-staging` prerelease
- Loader for any source and layout, including Excel workbooks with title rows and one sheet per year
- Warehouse models for NHS Talking Therapies, with NHS England's commissioning hubs set apart from Sub ICBs
- Population by single year of age and sex, and monthly denominators by age band, built up from LSOAs on each ONS boundary edition
- Indices of Deprivation 2025 for every LSOA, and summaries for every Sub ICB, ICB and local authority
- April 2023 local authority successors derived from ONS lookups, and a check of every Sub ICB's ICB against ONS
- `Build warehouse` workflow that rebuilds and tests everything on real data and publishes it to the `warehouse-latest` release, with a build summary

## 0.1.0, 13 October 2026, Phase 0 foundations

- New repository, separate from the MentalScape 1.0 dissertation folder
- Project charter, decision maker personas, target architecture, roadmap, data source register, data governance and ways of working
- Decision records 0001 to 0008
- Audit of MentalScape 1.0
- MHSDS release profiler and change log builder in `src/mentalscape/profiling`, with tests
- MHSDS change log covering all 50 monthly releases from July 2022 to August 2026, with reference tables in `data/reference`
- Interview guide for planners
- Tooling with uv, ruff, pytest, pre-commit and GitHub Actions CI
