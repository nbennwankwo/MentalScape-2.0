# Changelog

Notable changes to MentalScape 2.0. Dates are UK dates.

## Unreleased, Phase 1

- Decision records 0002 to 0007 accepted, and 0009 and 0010 added
- Automated MHSDS ingest in `src/mentalscape/ingest`, with a classifier built from every card title published since 2022
- `Ingest MHSDS` GitHub Actions workflow publishing raw files and a checksummed manifest to the `data-mhsds-monthly` release
- Discovery moved to a browser step after NHS England's pages were found to challenge cloud servers (ADR 0011), with the catalogue committed as `data/reference/mhsds_catalogue.csv`
- Pipeline guide in `docs/data/pipeline.md`

## 0.1.0, 13 October 2026, Phase 0 foundations

- New repository, separate from the MentalScape 1.0 dissertation folder
- Project charter, decision maker personas, target architecture, roadmap, data source register, data governance and ways of working
- Decision records 0001 to 0008
- Audit of MentalScape 1.0
- MHSDS release profiler and change log builder in `src/mentalscape/profiling`, with tests
- MHSDS change log covering all 50 monthly releases from July 2022 to August 2026, with reference tables in `data/reference`
- Interview guide for planners
- Tooling with uv, ruff, pytest, pre-commit and GitHub Actions CI
